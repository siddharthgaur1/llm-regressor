# LLM Regression Testing | Detect prompt and model regressions automatically

[![PyPI](https://img.shields.io/pypi/v/llm-regressor.svg)](https://pypi.org/project/llm-regressor/)
[![CI](https://github.com/siddharthgaur/llm-regressor/actions/workflows/ci.yml/badge.svg)](https://github.com/siddharthgaur/llm-regressor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

When you swap `gpt-4o` for `gpt-4o-mini`, edit a system prompt, or change RAG context, **llm-regressor** tells you exactly what broke: factuality, format adherence, tone, latency, cost, hallucination rate. Model-agnostic, drop-in, <10 lines to integrate.

## Install

```bash
pip install llm-regressor[anthropic]   # or [openai], [litellm], [all]
```

## Quickstart

```python
from llm_regressor import Regressor, TestSuite, providers

suite = TestSuite.from_yaml("tests/my_suite.yaml")

baseline = providers.Anthropic(model="claude-sonnet-5", system_prompt="You are a helpful assistant")
candidate = providers.Anthropic(model="claude-haiku-4-5-20251001", system_prompt="You are a helpful assistant")

reg = Regressor(baseline=baseline, candidate=candidate)
report = reg.run(suite, samples=3)

report.summary()      # rich table in the terminal
report.to_html("report.html")
report.to_json("report.json")
assert report.passed  # False if any CRITICAL regression fired
```

## Test suite format

```yaml
tests:
  - id: factual_capital
    input: "What is the capital of France?"
    checks:
      - type: contains
        value: "Paris"
    category: factual

  - id: sql_generation
    input: "Write SQL to get top 5 customers by revenue"
    checks:
      - type: format_match
        pattern: "SELECT.*FROM.*ORDER BY.*LIMIT 5"
        flags: IGNORECASE
      - type: no_injection_risk
    category: code
```

More examples in `examples/`.

## Check types

| Check | Kind | What it does |
|---|---|---|
| `contains` / `not_contains` | deterministic | substring presence/absence |
| `regex_match` / `format_match` | deterministic | structural match (SQL, code, etc.) |
| `length_range` | deterministic | response length bounds |
| `json_valid` | deterministic | response parses as JSON |
| `starts_with` / `ends_with` | deterministic | prefix/suffix match |
| `no_hallucination` | LLM judge | factual accuracy score, flags if < 0.7 |
| `tone_match` | LLM judge | tone matches professional/casual/technical |
| `instruction_following` | LLM judge | did it follow every instruction |
| `coherence` | LLM judge | logically coherent |
| `no_injection_risk` | pattern | flags dangerous SQL/code patterns |
| `semantic_similarity` | embedding | cosine similarity to a reference string |
| `self_consistency` | statistical | variance across repeated runs of the same prompt (most differentiated check — set `samples=N` on `.run()`) |
| `latency_regression` | statistical | candidate p95 vs baseline p95 |
| `cost_regression` | statistical | candidate avg cost vs baseline avg cost |

## Severity

- **CRITICAL** — a deterministic check failed (wrong format, missing fact) → exit code 1
- **WARNING** — an LLM judge score dropped >20% vs baseline
- **INFO** — latency/cost moved but within tolerance
- **PASS** — no regression

## CLI

```bash
llm-regressor init                                    # scaffold tests/suite.yaml
llm-regressor run --suite tests/suite.yaml --baseline claude-sonnet-5 --candidate claude-haiku-4-5-20251001
llm-regressor run --suite tests/suite.yaml --baseline-prompt prompts/v1.txt --candidate-prompt prompts/v2.txt
llm-regressor report --input results.json --format html
```

Exits with code `1` on any CRITICAL regression — wire it into CI to gate merges. See `docs/ci_example.yml` for a PR-comment workflow.

## Providers

`providers.Anthropic`, `providers.OpenAI` (and any OpenAI-compatible endpoint via `base_url=`), `providers.Ollama` (local models), `providers.LiteLLM` (anything else). All implement `BaseProvider.complete(prompt) -> CompletionResult`.

## Development

```bash
pip install -e ".[dev,all]"
pytest --cov=llm_regressor
```

MIT licensed. See [CONTRIBUTING.md](CONTRIBUTING.md).
