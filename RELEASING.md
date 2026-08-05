# Releasing

The `v0.1.0` tag has been pushed and the workflow ran. It failed at the
TestPyPI step with `invalid-publisher`, which is the expected result until the
one-time setup below is done. **Nothing was published** — the pipeline is
ordered TestPyPI → verify → PyPI, so a TestPyPI failure stops it before PyPI is
ever contacted. That is the gate working, not a bug.

## One-time setup (maintainer, ~5 minutes)

Trusted publishing means no API token is ever stored in this repository. It
needs a *pending publisher* registered on each index before the first upload,
because there is no project there yet to attach permissions to.

### 1. TestPyPI

<https://test.pypi.org/manage/account/publishing/> → "Add a new pending publisher"

| Field | Value |
| --- | --- |
| PyPI Project Name | `llm-regressor` |
| Owner | `siddharthgaur1` |
| Repository name | `llm-regressor` |
| Workflow name | `publish.yml` |
| Environment name | `testpypi` |

### 2. PyPI

<https://pypi.org/manage/account/publishing/> → same, with:

| Field | Value |
| --- | --- |
| Environment name | `pypi` |

These values are not guesses — they are the OIDC claims the failed run actually
presented:

```
repository:       siddharthgaur1/llm-regressor
repository_owner:  siddharthgaur1
workflow_ref:      siddharthgaur1/llm-regressor/.github/workflows/publish.yml@refs/tags/v0.1.0
environment:       testpypi
```

### 3. GitHub environments

Settings → Environments → create `testpypi` and `pypi` if they do not exist.
No secrets go in them; they exist so the OIDC `environment` claim matches.

## Then re-run the release

The tag already exists, so re-running the existing workflow run is enough:

```bash
gh run list --repo siddharthgaur1/llm-regressor --workflow=publish.yml
gh run rerun <run-id> --repo siddharthgaur1/llm-regressor
```

If you would rather cut a fresh tag, delete and recreate it — but only because
nothing was published under `v0.1.0`. Once a version exists on PyPI it can
never be reused, even after deletion.

```bash
git tag -d v0.1.0 && git push --delete origin v0.1.0
git tag -a v0.1.0 -m "v0.1.0" && git push origin v0.1.0
```

## After it succeeds

1. Confirm the package resolves: `pip install llm-regressor` in a clean venv.
2. Only then add the PyPI badge back to `README.md` and the profile README. It
   was removed because it pointed at a 404 — do not restore it until the URL
   returns 200.

## Version bumps

`__version__` in `llm_regressor/__init__.py` and `version` in `pyproject.toml`
must match the tag. The workflow checks this and refuses to publish on a
mismatch, so a tag that disagrees fails at build rather than silently
republishing the previous version.
