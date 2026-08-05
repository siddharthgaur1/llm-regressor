# Configuration reference

## Suite schema

```yaml
tests:
  - id: unique_test_id        # required, appears in every report
    input: "the user prompt"  # required, sent to both providers verbatim
    expected: "Paris"         # optional, documentation only — no check reads it
    category: factual         # optional, default "general"; used by counts_by_category()
    checks:                   # optional; a test with no checks still measures
      - type: contains        # latency, cost and self-consistency
        value: "Paris"
```

!!! note "`expected` is not an assertion"
    It is a note to whoever reads the suite later. If you want it enforced,
    add a `contains` or `semantic_similarity` check with the same string.
    This is deliberate — for open-ended prompts there is rarely one right
    answer, and a field that silently does nothing is better than one that
    pretends exact-match is meaningful.

Every key on a check other than `type` is passed through to the check
function as a parameter. Unknown keys are ignored; an unknown `type` is
skipped rather than failing the run, on the grounds that a typo in a suite is
an authoring error, not a model regression.

## Deterministic checks

No API call. Run on the candidate response only.

| Type | Parameters | Passes when |
| --- | --- | --- |
| `contains` | `value` | `value` is a substring of the response |
| `not_contains` | `value` | `value` is absent |
| `regex_match` | `pattern`, `flags` | `re.search(pattern)` matches |
| `format_match` | `pattern`, `flags` | alias of `regex_match` |
| `length_range` | `min` (0), `max` (1e9) | response length is in `[min, max]` |
| `json_valid` | — | the response parses as JSON |
| `starts_with` | `prefix` | response starts with `prefix` |
| `ends_with` | `suffix` | response ends with `suffix` |

`flags` is the name of a `re` constant, e.g. `IGNORECASE`.

```yaml
- type: format_match
  pattern: "SELECT.*FROM.*ORDER BY.*LIMIT 5"
  flags: IGNORECASE
```

## Pattern checks

| Type | Parameters | Passes when |
| --- | --- | --- |
| `no_injection_risk` | — | no dangerous SQL/code pattern is present |

Flags `DROP TABLE`, unscoped `DELETE FROM`, `TRUNCATE`, `exec(`, `eval(`,
`os.system(`, `subprocess.`, `; --`, and `xp_cmdshell`. A `DELETE FROM …
WHERE …` passes: scoped deletes are ordinary SQL.

This is a regex screen, not a security control. It catches a model that has
started emitting destructive SQL. It will not stop a determined adversary,
and you should not put it in front of anything that executes generated code.

## Embedding checks

| Type | Parameters | Score |
| --- | --- | --- |
| `semantic_similarity` | `reference`, `threshold` (0.8) | cosine similarity to `reference` |

With `sentence-transformers` installed (`pip install "llm-regressor[embeddings]"`)
this uses `all-MiniLM-L6-v2` embeddings. Without it, it silently falls back to
`difflib` lexical similarity.

!!! warning "The fallback is not a substitute"
    Lexical similarity scores paraphrases far lower than embeddings do, so the
    same suite with the same `threshold` behaves differently depending on
    which backend is installed. Install the extra, or lower the threshold and
    know why you did.

## LLM-judge checks

Each makes one API call per check, per test, per side. The judge defaults to
the baseline provider; pass `judge=` to `Regressor` to use a different one.

| Type | Parameters | Criterion |
| --- | --- | --- |
| `no_hallucination` | `threshold` (0.7) | no fabricated details |
| `tone_match` | `expected_tone` ("professional"), `threshold` | tone matches |
| `instruction_following` | `threshold` | every instruction followed |
| `coherence` | `threshold` | logically coherent and internally consistent |

The judge is asked for a bare number in `[0, 1]`; the first number in its
reply is used and clamped. An unparseable reply scores 0 — failing loudly is
better than defaulting to pass and reporting a regression that never happened.
A judge whose call errors also scores 0.

Judge checks produce **CRITICAL** below `threshold`, and **WARNING** when the
candidate stays above `threshold` but scores more than 20% below the baseline.

## Statistical checks

These are not listed in `checks:`. They run automatically over the completions
already collected.

| Name | Trigger | Severity |
| --- | --- | --- |
| `self_consistency` | `samples > 1` | WARNING when the candidate's mean pairwise similarity is more than 0.15 below the baseline's |
| `latency_regression` | always | INFO when candidate p95 > 1.5× baseline p95 |
| `cost_regression` | always | INFO when candidate mean cost > 2× baseline mean |

Latency and cost are reported, never blocking. Wall-clock latency measured
from a CI runner is too noisy to gate on.

## Providers

| Class | Extra | Notes |
| --- | --- | --- |
| `providers.Anthropic` | `anthropic` | Reads `ANTHROPIC_API_KEY`, or pass `api_key=`. |
| `providers.OpenAI` | `openai` | Also any OpenAI-compatible endpoint via `base_url=`. |
| `providers.Ollama` | `ollama` | Local models. `host=` defaults to `http://localhost:11434`. Cost is always 0. |
| `providers.LiteLLM` | `litellm` | Anything LiteLLM understands: `bedrock/`, `azure/`, `gemini/`, … |

All accept `model`, `system_prompt`, and `max_tokens` (default 1024).

A provider never raises on an API failure. It returns a `CompletionResult`
with `.error` set and an empty `.response`, so one bad call degrades a single
test rather than aborting a suite you have already paid for.

Cost figures come from a pricing table baked into each provider, and an
unrecognised model falls back to a mid-tier assumption. Treat reported cost as
an indication, not an invoice.

## Slack alerts

```python
from llm_regressor import send_slack_alert
send_slack_alert(report, report_url="https://…/report.html")
```

Requires `pip install "llm-regressor[slack]"` and `SLACK_WEBHOOK_URL` in the
environment. With the variable unset it logs a warning and returns, so it is
safe to leave in a script that also runs locally.
