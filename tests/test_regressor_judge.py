"""Regressor's judge and multi-sample paths.

The severity ladder is the product decision worth pinning: a candidate that
fails outright is CRITICAL and fails CI, but a candidate that merely scores
*worse than the baseline while still passing* is a WARNING — visible, not
blocking. Conflating those two would make the tool unusable in CI.
"""
from __future__ import annotations

from conftest import FakeProvider

from llm_regressor.core.regressor import Regressor, _max_severity, _stats
from llm_regressor.core.test_suite import TestSuite


def _judge_suite(**params):
    return TestSuite.from_list([{
        "id": "t1",
        "input": "summarise this",
        "checks": [{"type": "no_hallucination", **params}],
    }])


def _row(report, test_id="t1"):
    return next(r for r in report.regressions if r.test_id == test_id)


def test_judge_check_passing_on_both_sides_is_a_pass():
    reg = Regressor(FakeProvider("x"), FakeProvider("y"), judge=FakeProvider("0.9"))
    assert _row(reg.run(_judge_suite())).severity == "PASS"


def test_judge_score_below_threshold_is_critical():
    reg = Regressor(FakeProvider("x"), FakeProvider("y"), judge=FakeProvider("0.2"))
    row = _row(reg.run(_judge_suite()))
    assert row.severity == "CRITICAL"
    assert "no_hallucination failed" in row.message


def test_custom_threshold_is_honoured():
    # 0.6 passes the default 0.7? No — but it passes an explicit 0.5.
    strict = Regressor(FakeProvider("x"), FakeProvider("y"), judge=FakeProvider("0.6"))
    assert _row(strict.run(_judge_suite())).severity == "CRITICAL"

    lenient = Regressor(FakeProvider("x"), FakeProvider("y"), judge=FakeProvider("0.6"))
    assert _row(lenient.run(_judge_suite(threshold=0.5))).severity == "PASS"


def test_passing_candidate_that_drops_over_20_percent_warns_without_failing():
    # Judge sees baseline first (1.0), candidate second (0.75): still above the
    # 0.7 threshold, but a 25% drop. Warn, don't block.
    reg = Regressor(FakeProvider("x"), FakeProvider("y"), judge=FakeProvider("1.0", "0.75"))
    row = _row(reg.run(_judge_suite()))
    assert row.severity == "WARNING"
    assert "dropped >20%" in row.message


def test_small_drop_is_not_reported():
    reg = Regressor(FakeProvider("x"), FakeProvider("y"), judge=FakeProvider("1.0", "0.9"))
    assert _row(reg.run(_judge_suite())).severity == "PASS"


def test_judge_defaults_to_the_baseline_provider():
    baseline = FakeProvider("0.9")
    reg = Regressor(baseline, FakeProvider("y"))
    assert reg.judge is baseline


def test_unknown_check_type_is_skipped_rather_than_failing_the_run():
    suite = TestSuite.from_list([{"id": "t1", "input": "q", "checks": [{"type": "does_not_exist"}]}])
    report = Regressor(FakeProvider("a"), FakeProvider("a")).run(suite)
    row = _row(report)
    assert row.severity == "PASS"
    assert row.checks == []


def test_no_injection_risk_records_a_real_bool_not_a_float():
    suite = TestSuite.from_list([{"id": "t1", "input": "q", "checks": [{"type": "no_injection_risk"}]}])
    report = Regressor(FakeProvider("SELECT 1"), FakeProvider("SELECT 1")).run(suite)
    outcome = _row(report).checks[0]
    assert outcome.passed is True
    assert report.to_dict()["regressions"][0]["checks"][0]["passed"] is True


def test_multi_sample_run_calls_each_provider_n_times(no_embeddings):
    baseline, candidate = FakeProvider("Paris"), FakeProvider("Paris")
    suite = TestSuite.from_list([{"id": "t1", "input": "q", "checks": []}])
    report = Regressor(baseline, candidate).run(suite, samples=3)
    assert len(baseline.calls) == len(candidate.calls) == 3
    assert report.baseline_stats["n"] == 3


def test_less_consistent_candidate_warns(no_embeddings):
    # Baseline says the same thing every time; candidate wanders.
    baseline = FakeProvider("Paris", "Paris", "Paris")
    candidate = FakeProvider("Paris", "Lyon", "somewhere in France, probably")
    suite = TestSuite.from_list([{"id": "t1", "input": "q", "checks": []}])
    row = _row(Regressor(baseline, candidate).run(suite, samples=3))
    assert row.severity == "WARNING"
    assert "self_consistency dropped" in row.message


def test_equally_consistent_candidate_does_not_warn(no_embeddings):
    suite = TestSuite.from_list([{"id": "t1", "input": "q", "checks": []}])
    row = _row(Regressor(FakeProvider("Paris"), FakeProvider("Paris")).run(suite, samples=3))
    assert row.severity == "PASS"


def test_latency_and_cost_rows_are_informational_never_blocking():
    slow = FakeProvider("ok", latency_ms=5000.0, cost=1.0)
    fast = FakeProvider("ok", latency_ms=10.0, cost=0.001)
    suite = TestSuite.from_list([{"id": "t1", "input": "q", "checks": []}])
    report = Regressor(fast, slow).run(suite)
    assert _row(report, "__latency__").severity == "INFO"
    assert _row(report, "__cost__").severity == "INFO"
    # INFO must not fail the build — only CRITICAL does.
    assert report.passed is True


def test_max_severity_takes_the_worse_of_two():
    assert _max_severity("PASS", "WARNING") == "WARNING"
    assert _max_severity("CRITICAL", "INFO") == "CRITICAL"
    assert _max_severity("INFO", "INFO") == "INFO"


def test_stats_on_an_empty_run_do_not_divide_by_zero():
    assert _stats([], []) == {"avg_latency_ms": 0, "avg_cost": 0, "n": 0}
