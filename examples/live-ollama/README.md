# Live run: prompt change on llama3.2 (Ollama, CPU)

The [worked example](../../docs/example.md) replays scripted responses. This
directory is the same scenario run against a real model, end to end through
the CLI, with nothing edited after the fact.

- **Model:** `llama3.2:latest` (3B), local Ollama, reached through the CLI's
  LiteLLM route as `ollama/llama3.2`. Free, no key.
- **Hardware:** CPU only (Windows 11, 12 logical cores, shared with an
  unrelated process during the run).
- **Date:** 2026-09-13. **Wall time:** 354s.
- **Size:** 3 tests × 3 samples × 2 sides = 18 completions (9 per side).
- **Change under test:** `prompts/v1.txt` → `prompts/v2.txt`, which adds one
  sentence: "Be warm and personable."

## Command

From the repo root, with Ollama running and `llama3.2` pulled:

```bash
pip install -e ".[litellm]"
llm-regressor run \
  --suite examples/live-ollama/support_suite.yaml \
  --baseline ollama/llama3.2 \
  --baseline-prompt examples/live-ollama/prompts/v1.txt \
  --candidate-prompt examples/live-ollama/prompts/v2.txt \
  --samples 3 \
  --out examples/live-ollama/report.json \
  --html examples/live-ollama/report.html
```

Exit code was `0`.

## Result

Verbatim terminal output: [`transcript.txt`](transcript.txt). Full responses
and per-check detail: [`report.json`](report.json), [`report.html`](report.html).

```text
Regressions: 0 CRITICAL, 1 WARNING, 0 INFO
Overall: PASSED
```

| Test | Severity | self_consistency baseline → candidate |
|---|---|---|
| refund_request | WARNING | 0.420 → 0.269 |
| escalation | PASS | 0.269 → 0.136 |
| order_status | PASS | 0.391 → 0.266 |

Average latency 13,976ms baseline vs 18,406ms candidate; p95 22,732ms vs
23,207ms (under the 1.5× threshold).

## What this run does and does not show

- **The scripted regression did not reproduce.** No `json_valid`,
  `contains` or `not_contains` check failed on either side, so on this model
  this prompt edit did not drop the JSON wrapper. That is one small model on
  one day, not evidence that the failure mode is rare.
- **The deterministic checks missed a real behaviour change.** The recorded
  `order_status` candidate response stops answering ("I don't have access to
  real-time order information…") but still emits `"order_id": 9982`, so it
  passed. The suite checks shape and the id, not whether the question was
  answered — the kind of gap an `instruction_following` judge check is for.
- **The WARNING rule** is candidate consistency more than 0.15 below baseline.
  `refund_request` dropped 0.151 and fired; `escalation` dropped 0.133 and
  did not. Both are close to the line.
- **Similarity here is lexical.** `sentence-transformers` was not installed, so
  `self_consistency` used `difflib` ratios (see Limitations in the main
  README). The same run with `[embeddings]` installed would score differently.
- **Sampling was not pinned.** No temperature or seed is passed by the CLI, so
  a rerun will produce different responses and possibly different severities.
