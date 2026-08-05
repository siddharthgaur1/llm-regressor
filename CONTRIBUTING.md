# Contributing

## Setup

```bash
git clone https://github.com/siddharthgaur1/llm-regressor
cd llm-regressor
pip install -e ".[dev,all]"
```

## Before opening a pull request

```bash
ruff check .
pytest --cov=llm_regressor --cov-report=term-missing
```

Both run in CI on Python 3.10–3.13. The coverage gate is 90%; the suite is
currently at 100% statement and branch coverage, and there is no expectation
that you keep it there — a test that exists only to move the number is worse
than the gap it fills.

The whole suite runs in about a second and needs no API key. If a change you
make requires a network call to test, that is usually a sign the seam is in
the wrong place: providers are the only thing that should touch the network,
and they are tested by faking the vendor SDK at `sys.modules` level. See
`tests/test_providers.py`.

## Where things go

| Change | Where |
| --- | --- |
| New deterministic check | `llm_regressor/checks/deterministic.py`, registered in that file's `REGISTRY` |
| New judge or embedding check | `llm_regressor/checks/llm_judge.py`, same pattern. If the caller should compare baseline vs candidate scores, add the name to `JUDGE_CHECK_NAMES` in `core/regressor.py` |
| New statistical check | `llm_regressor/checks/statistical.py`, wired into `Regressor.run` |
| New provider | Subclass `providers.base.BaseProvider`, implement `complete` |
| Docs | `docs/`, built with `mkdocs serve` |

New checks need a row in `docs/configuration.md` and in the README table.

## The rules that are not negotiable

**A provider must not raise.** Catch the exception and return a
`CompletionResult` with `.error` set. A suite run costs real money; one bad
API call must degrade a single test, not abort everything the user has
already paid for.

**A failed judge parse scores 0, not a pass.** If the judge's reply cannot be
read as a number, that is a failure. Defaulting to pass reports a green run
that was never actually checked.

**Keep the public API stable.** The exported surface is listed in
`llm_regressor/__init__.py` and in `docs/api.md`. Anything else —
`llm_regressor.checks`, `llm_regressor.cli`, underscore names — is internal
and may change in a patch release. If you need something internal made
public, say so in the issue; that is a reasonable request, not a workaround.

## Releasing

Maintainers only.

1. Update `CHANGELOG.md`.
2. Bump `__version__` in `llm_regressor/__init__.py` and `version` in
   `pyproject.toml`. They must match the tag, or the release workflow fails
   on purpose.
3. `git tag v0.2.0 && git push --tags`.

The tag triggers build → TestPyPI → a clean install from TestPyPI → PyPI →
GitHub release. PyPI is only reached if the TestPyPI install actually worked.

### One-time setup for a new maintainer

The workflow uses [trusted publishing](https://docs.pypi.org/trusted-publishers/),
so there is no API token in the repo secrets. It needs, once:

- A pending publisher on **PyPI** and on **TestPyPI** for repository
  `siddharthgaur1/llm-regressor`, workflow `publish.yml`, environments `pypi`
  and `testpypi` respectively.
- Those two environments created in **Settings → Environments**.
- **Settings → Pages** set to "GitHub Actions" for the docs site.

Until that exists, a pushed tag will fail at the publish step. It will not
publish anything wrong; it will just stop.

## Reporting bugs

Open an issue. For a regression in check behaviour, the most useful thing you
can include is the smallest suite YAML plus the two responses that produced
the wrong verdict — with the responses pasted in, nobody needs your API key
to reproduce it.
