# llm-regressor

Prompt changes don't fail loudly. You tighten a system prompt to fix one
customer complaint, the diff looks harmless, every unit test still passes —
and three weeks later someone notices the model stopped emitting valid JSON
for a category of input nobody thought to check.

`llm-regressor` runs a golden test suite against two configurations — an old
model and a new one, or an old prompt and a new one — and tells you what
changed. It exits non-zero on a regression, so you can put it in front of a
merge.

```bash
pip install llm-regressor[anthropic]
```

![llm-regressor catching a prompt change that broke JSON output](assets/demo.svg)

## What it checks

| Kind | Checks | Needs an API call? |
| --- | --- | --- |
| Deterministic | `contains`, `regex_match`, `json_valid`, `length_range`, … | no |
| Pattern | `no_injection_risk` | no |
| Embedding | `semantic_similarity` | no (falls back to lexical) |
| LLM judge | `no_hallucination`, `tone_match`, `coherence`, … | yes, one per check per test |
| Statistical | `self_consistency`, `latency_regression`, `cost_regression` | uses the runs already made |

## Where to start

- **[Quickstart](quickstart.md)** — first suite running in about two minutes.
- **[Worked example](example.md)** — a real prompt regression, caught end to end.
- **[GitHub Action](github-action.md)** — five lines to gate a pull request.
- **[Configuration reference](configuration.md)** — every check and parameter.
- **[Python API](api.md)** — the supported surface, and what is internal.

## The design decision worth knowing up front

Not every regression should block a merge.

- **CRITICAL** — a check failed outright. Exit code 1.
- **WARNING** — the candidate still passes, but scored more than 20% below
  the baseline, or got measurably less consistent across repeated runs.
  Visible, non-blocking.
- **INFO** — latency or cost moved. Never blocking.

A tool that fails the build every time a judge score wobbles gets disabled
within a week. The severity ladder exists so that the CRITICAL signal stays
worth paying attention to.

!!! warning "The thresholds are defaults, not calibrated values"
    The 0.7 judge threshold and the 20% drop rule are starting points. They
    have not been tuned against a human-labelled set, and nothing here tells
    you how well an LLM judge agrees with your reviewers. Treat WARNING as a
    prompt to look, not as a measurement.
