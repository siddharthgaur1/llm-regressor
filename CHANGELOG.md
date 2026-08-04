# Changelog

## [Unreleased]

Baseline snapshot as of the portfolio hygiene pass (2026-08-04):

- Merged `llm-regression-detector`'s per-category pass-rate breakdown (`Report.counts_by_category()`) and Slack alerting (`core/alerting.py`) into this repo, since this repo's pip-installable, provider-agnostic framing is the stronger home for both.
- 14 tests passing (`pytest --cov=llm_regressor`), including 3 new tests for the merged functionality.
- Fixed CI: `httpx` (needed by the new alerting tests) was missing from the `dev` extras that CI installs — added.
