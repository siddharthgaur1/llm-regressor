# GitHub Action

## Five lines

```yaml
- uses: siddharthgaur1/llm-regressor@v0.1.0
  with:
    suite: tests/suite.yaml
    baseline: claude-sonnet-5
    candidate: claude-haiku-4-5-20251001
```

## A complete workflow

```yaml
name: Prompt regression

on:
  pull_request:
    paths:
      - "prompts/**"
      - "tests/suite.yaml"

jobs:
  regression:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write   # required for comment-on-pr
    steps:
      - uses: actions/checkout@v4
      - uses: siddharthgaur1/llm-regressor@v0.1.0
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        with:
          suite: tests/suite.yaml
          baseline-prompt: prompts/main.txt
          candidate-prompt: prompts/candidate.txt
          samples: 3
```

The action posts a summary table to the job summary and to the pull request,
uploads the JSON and HTML reports as a build artifact, and then fails the job
if anything came back CRITICAL.

!!! tip "Pin the tag"
    `@v0.1.0`, not `@master`. This action runs your prompts against a paid
    API; you do not want its behaviour changing under you between runs.

## Inputs

| Input | Default | Description |
| --- | --- | --- |
| `suite` | *required* | Path to the suite YAML. |
| `baseline` | — | Baseline model name. Use with `candidate`. |
| `candidate` | — | Candidate model name. |
| `baseline-prompt` | — | Baseline system prompt file. Use with `candidate-prompt`. |
| `candidate-prompt` | — | Candidate system prompt file. |
| `samples` | `1` | Completions per test. `>1` enables `self_consistency` and costs proportionally more. |
| `fail-on-regression` | `true` | Set `false` to report without blocking the merge. |
| `version` | *latest* | Version specifier, e.g. `==0.1.0`. |
| `extras` | `all` | Extras to install. Narrow this to just your provider to speed up the job. |
| `python-version` | `3.12` | Python version for the run. |
| `comment-on-pr` | `true` | Post the summary as a PR comment. |

Pass either `baseline`/`candidate` or `baseline-prompt`/`candidate-prompt`.
Passing neither is a usage error.

## Outputs

| Output | Description |
| --- | --- |
| `passed` | `'true'` when nothing came back CRITICAL. |
| `critical` | Count of CRITICAL regressions. |
| `warning` | Count of WARNING regressions. |
| `json-report` | Path to the JSON report. |

Use these when you want your own handling rather than a hard failure:

```yaml
- uses: siddharthgaur1/llm-regressor@v0.1.0
  id: regressions
  with:
    suite: tests/suite.yaml
    baseline: claude-sonnet-5
    candidate: claude-haiku-4-5-20251001
    fail-on-regression: false

- name: Label the PR instead of blocking it
  if: steps.regressions.outputs.critical != '0'
  run: gh pr edit "$PR" --add-label "prompt-regression"
  env:
    GH_TOKEN: ${{ github.token }}
    PR: ${{ github.event.pull_request.number }}
```

## Cost

Every run makes real API calls: roughly
`tests × (deterministic checks are free + one call per judge check) × samples × 2 sides`.
A 40-test suite with two judge checks at `samples: 3` is around 480 calls per
pull request.

Two ways to keep that sane:

- Scope the workflow with `on.pull_request.paths` so it only fires when a
  prompt or the suite actually changed.
- Keep `samples: 1` for the PR gate and run `samples: 5` on a nightly
  schedule, where consistency drift matters and latency does not.
