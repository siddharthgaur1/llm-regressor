from llm_regressor.core.regressor import Regressor
from llm_regressor.core.test_suite import TestSuite
from llm_regressor.providers.base import BaseProvider, CompletionResult


class FakeProvider(BaseProvider):
    name = "fake"

    def __init__(self, canned_response: str, model="fake-model"):
        super().__init__(model=model)
        self.canned_response = canned_response

    def complete(self, prompt: str) -> CompletionResult:
        return CompletionResult(response=self.canned_response, latency_ms=10.0, input_tokens=5, output_tokens=5, cost=0.0)


def _suite():
    return TestSuite.from_list([
        {"id": "t1", "input": "capital of France?", "checks": [{"type": "contains", "value": "Paris"}]},
    ])


def test_no_regression_when_both_pass():
    reg = Regressor(baseline=FakeProvider("Paris"), candidate=FakeProvider("Paris"))
    report = reg.run(_suite())
    assert report.passed is True
    t1 = next(r for r in report.regressions if r.test_id == "t1")
    assert t1.severity == "PASS"


def test_critical_regression_when_candidate_fails_deterministic_check():
    reg = Regressor(baseline=FakeProvider("Paris"), candidate=FakeProvider("Tokyo"))
    report = reg.run(_suite())
    assert report.passed is False
    t1 = next(r for r in report.regressions if r.test_id == "t1")
    assert t1.severity == "CRITICAL"


def test_report_to_json_and_html(tmp_path):
    reg = Regressor(baseline=FakeProvider("Paris"), candidate=FakeProvider("Paris"))
    report = reg.run(_suite())
    json_path = report.to_json(tmp_path / "r.json")
    html_path = report.to_html(tmp_path / "r.html")
    assert json_path.exists()
    assert html_path.exists()
    assert "t1" in html_path.read_text(encoding="utf-8")
