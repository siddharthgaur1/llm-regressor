# Changelog

All notable changes to this project are documented here.
This project follows [semantic versioning](https://semver.org/). The public
API is the surface listed in `llm_regressor/__init__.py` and `docs/api.md`;
anything else may change in a patch release.

## [Unreleased]

## [0.2.0] - 2026-09-22

### Added
- `py.typed`, so type checkers in downstream projects see the annotations.
- Reusable GitHub Action (`action.yml`) — five lines to gate a pull request,
  with a PR comment, a job summary, report artifacts, and configurable
  blocking behaviour.
- Documentation site (mkdocs-material, GitHub Pages): quickstart, worked
  example, Action reference, configuration reference, Python API.
- `examples/prompt_regression_demo.py` — a runnable end-to-end regression
  with scripted providers, no API key required.
- `Report.summary(console=...)`, so the results table can be captured or
  redirected rather than only written to stdout.
- `slack` extra for `send_slack_alert`.
- `Check`, `TestCase` and `send_slack_alert` exported from the top level.
  They were already usable; they were not documented as supported.
- Issue templates for bugs, check-type proposals and provider requests.
- Ruff linting, a `build` + `twine check` CI job, and Python 3.13 in the
  test matrix.

### Fixed
- `send_slack_alert` required `httpx`, which was only in the `dev` extra —
  so `pip install llm-regressor[all]`, as its own docstring instructed,
  produced an `ImportError` at the point of use.
- `llm-regressor report --format html` aborted with a jinja2 `UndefinedError`
  on any results JSON missing the stats keys. Missing stats now render as 0.
- `no_injection_risk` outcomes serialised to JSON as `1.0`/`0.0` instead of
  `true`/`false`, because it lives in the judge registry but takes the
  deterministic code path.
- The embedding-backed checks (`semantic_similarity`, `self_consistency`)
  silently changed scoring depending on whether `sentence-transformers` was
  installed. Behaviour is unchanged — this is documented as a limitation
  rather than fixed — but both branches are now covered by tests instead of
  by whatever the environment happened to have.

### Changed
- Release workflow now runs build → TestPyPI → clean install from TestPyPI →
  PyPI → GitHub release, and refuses to publish when the git tag disagrees
  with `__version__`.
- Tests: 14 → 118, coverage 57% → 100% statement and branch, suite runtime
  148s → ~2s (it was loading a real embedding model).

## Baseline snapshot (2026-08-04, portfolio hygiene pass)

- Merged `llm-regression-detector`'s per-category pass-rate breakdown
  (`Report.counts_by_category()`) and Slack alerting (`core/alerting.py`) into
  this repo, since this repo's pip-installable, provider-agnostic framing is
  the stronger home for both.
- 14 tests passing (`pytest --cov=llm_regressor`), including 3 new tests for
  the merged functionality.
- Fixed CI: `httpx` (needed by the new alerting tests) was missing from the
  `dev` extras that CI installs — added.
