# Python API

Everything below is exported from the top-level `llm_regressor` package and is
covered by semantic versioning. Anything not on this page — including
`llm_regressor.checks`, `llm_regressor.cli`, and any underscore-prefixed
name — is internal and may change in a patch release.

```python
from llm_regressor import (
    Regressor, TestSuite, TestCase, Check,
    Report, Regression, CheckOutcome,
    providers, send_slack_alert,
)
```

## `Regressor`

```python
Regressor(baseline: BaseProvider, candidate: BaseProvider, judge: BaseProvider | None = None)
```

`judge` defaults to `baseline`. Using the baseline model as its own judge is
cheap and usually fine, but it does mean the judge shares the baseline's
blind spots — if you are grading factuality on a domain the baseline is weak
in, pass a stronger judge.

```python
Regressor.run(suite: TestSuite, samples: int = 1) -> Report
```

Calls both providers `samples` times per test, evaluates every check against
the *first* completion from each side, and adds `self_consistency` across all
of them when `samples > 1`.

## `TestSuite`

```python
TestSuite.from_yaml(path) -> TestSuite     # see the suite schema
TestSuite.from_list([{...}]) -> TestSuite  # same shape, already parsed
len(suite)                                 # number of test cases
for test in suite: ...                     # TestCase objects
```

`TestCase` fields: `id`, `input`, `checks`, `expected`, `category`.
`Check` fields: `type`, `params`.

## `Report`

```python
report.passed                  # False if any regression is CRITICAL
report.counts()                # {"CRITICAL": n, "WARNING": n, "INFO": n, "PASS": n}
report.counts_by_category(m)   # per-category breakdown; m maps test_id -> category
report.summary()               # rich table to the terminal
report.to_dict()               # plain dict, the JSON report's shape
report.to_json(path)           # -> Path
report.to_html(path)           # -> Path
```

`counts_by_category` takes the mapping rather than reading it off the suite,
so a report loaded back from JSON can still be bucketed. Synthetic rows
(`__latency__`, `__cost__`) land under `"meta"`.

```python
categories = {t.id: t.category for t in suite}
report.counts_by_category(categories)
```

`Regression` fields: `test_id`, `severity`, `message`, `baseline_response`,
`candidate_response`, `checks`.
`CheckOutcome` fields: `check_type`, `passed`, `detail`, `baseline_detail`,
`candidate_detail`.

## Providers

```python
class BaseProvider:
    def __init__(self, model: str, system_prompt: str | None = None, **kwargs): ...
    def complete(self, prompt: str) -> CompletionResult: ...
    def label(self) -> str  # "anthropic:claude-sonnet-5"
```

`CompletionResult`: `response`, `latency_ms`, `input_tokens`, `output_tokens`,
`cost`, `error`.

### Writing your own

Subclass `BaseProvider` and implement `complete`. The one rule the rest of the
library depends on: **do not raise**. Catch the failure and return a
`CompletionResult` with `error` set.

```python
import time
from llm_regressor.providers import BaseProvider, CompletionResult

class MyGateway(BaseProvider):
    name = "mygateway"

    def complete(self, prompt: str) -> CompletionResult:
        start = time.perf_counter()
        try:
            text = my_client.generate(self.model, prompt, system=self.system_prompt)
            return CompletionResult(response=text, latency_ms=(time.perf_counter() - start) * 1000)
        except Exception as e:
            return CompletionResult(response="", latency_ms=(time.perf_counter() - start) * 1000, error=str(e))
```

This is also how you test: swap in a provider returning canned strings and the
whole pipeline runs offline. That is how this project's own suite reaches full
coverage without an API key.

## Custom checks

Provisional, and the one part of this page not covered by semver. Register a
callable in the shared registry before running:

```python
from llm_regressor.checks import ALL_CHECKS

def mentions_disclaimer(response: str, **params) -> tuple[bool, str]:
    ok = "not financial advice" in response.lower()
    return ok, "ok" if ok else "disclaimer missing"

ALL_CHECKS["mentions_disclaimer"] = mentions_disclaimer
```

```yaml
- type: mentions_disclaimer
```

The signature is `(response: str, **params) -> tuple[bool, str]`, where
`params` is every key on the YAML check except `type`. Return `(passed,
detail)`; `detail` is what shows up in the report, so make it say what went
wrong rather than repeating the check name.

## `send_slack_alert`

```python
send_slack_alert(report: Report, report_url: str | None = None) -> None
```

Posts to `SLACK_WEBHOOK_URL`. No-ops with a logged warning if unset. Raises
`ImportError` without `pip install "llm-regressor[slack]"`, and
`httpx.HTTPStatusError` if Slack rejects the post.
