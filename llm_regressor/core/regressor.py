from __future__ import annotations

from ..checks import ALL_CHECKS, statistical
from ..providers.base import BaseProvider
from .report import CheckOutcome, Regression, Report
from .test_suite import TestCase, TestSuite

JUDGE_CHECK_NAMES = {"no_hallucination", "tone_match", "instruction_following", "coherence", "semantic_similarity"}


class Regressor:
    def __init__(self, baseline: BaseProvider, candidate: BaseProvider, judge: BaseProvider | None = None):
        self.baseline = baseline
        self.candidate = candidate
        self.judge = judge or baseline

    def run(self, suite: TestSuite, samples: int = 1) -> Report:
        regressions: list[Regression] = []
        all_latencies: dict[str, list[float]] = {"baseline": [], "candidate": []}
        all_costs: dict[str, list[float]] = {"baseline": [], "candidate": []}

        for test in suite:
            base_runs = [self.baseline.complete(test.input) for _ in range(samples)]
            cand_runs = [self.candidate.complete(test.input) for _ in range(samples)]
            for label, runs in (("baseline", base_runs), ("candidate", cand_runs)):
                all_latencies[label].extend(r.latency_ms for r in runs)
                all_costs[label].extend(r.cost for r in runs)

            base_response = base_runs[0].response
            cand_response = cand_runs[0].response

            outcomes, severity, messages = self._evaluate_checks(test, base_response, cand_response)

            if samples > 1:
                base_score, base_detail = statistical.self_consistency([r.response for r in base_runs])
                cand_score, cand_detail = statistical.self_consistency([r.response for r in cand_runs])
                outcomes.append(CheckOutcome("self_consistency", cand_score >= base_score - 0.15, cand_detail, base_detail, cand_detail))
                if cand_score < base_score - 0.15:
                    severity = _max_severity(severity, "WARNING")
                    messages.append(f"self_consistency dropped: {cand_detail}")

            regressions.append(Regression(
                test_id=test.id,
                severity=severity,
                message="; ".join(messages) if messages else "no regression detected",
                baseline_response=base_response,
                candidate_response=cand_response,
                checks=outcomes,
            ))

        lat_ok, lat_detail = statistical.latency_regression(all_latencies["baseline"], all_latencies["candidate"])
        cost_ok, cost_detail = statistical.cost_regression(all_costs["baseline"], all_costs["candidate"])
        regressions.append(Regression(
            test_id="__latency__",
            severity="PASS" if lat_ok else "INFO",
            message=lat_detail,
        ))
        regressions.append(Regression(
            test_id="__cost__",
            severity="PASS" if cost_ok else "INFO",
            message=cost_detail,
        ))

        return Report(
            baseline_label=self.baseline.label(),
            candidate_label=self.candidate.label(),
            regressions=regressions,
            baseline_stats=_stats(all_latencies["baseline"], all_costs["baseline"]),
            candidate_stats=_stats(all_latencies["candidate"], all_costs["candidate"]),
        )

    def _evaluate_checks(
        self, test: TestCase, base_response: str, cand_response: str
    ) -> tuple[list[CheckOutcome], str, list[str]]:
        outcomes: list[CheckOutcome] = []
        severity = "PASS"
        messages: list[str] = []

        for check in test.checks:
            fn = ALL_CHECKS.get(check.type)
            if fn is None:
                continue  # ponytail: unknown check type is a suite authoring error, not a regression signal

            if check.type in JUDGE_CHECK_NAMES:
                threshold = check.params.get("threshold", 0.7)
                base_score, base_detail = fn(base_response, judge=self.judge, prompt=test.input, **check.params)
                cand_score, cand_detail = fn(cand_response, judge=self.judge, prompt=test.input, **check.params)
                passed = cand_score >= threshold
                outcomes.append(CheckOutcome(check.type, passed, cand_detail, base_detail, cand_detail))
                if not passed:
                    severity = _max_severity(severity, "CRITICAL")
                    messages.append(f"{check.type} failed: {cand_detail}")
                elif base_score > 0 and (base_score - cand_score) / base_score > 0.2:
                    severity = _max_severity(severity, "WARNING")
                    messages.append(f"{check.type} dropped >20%: baseline {base_score:.2f} -> candidate {cand_score:.2f}")
            else:
                passed, detail = fn(cand_response, **check.params)
                # no_injection_risk lives in the judge registry but takes the deterministic path,
                # and returns 1.0/0.0 rather than True/False. Normalise so CheckOutcome.passed
                # is always a bool and serialises to JSON as one.
                passed = bool(passed)
                outcomes.append(CheckOutcome(check.type, passed, detail))
                if not passed:
                    severity = _max_severity(severity, "CRITICAL")
                    messages.append(f"{check.type} failed: {detail}")

        return outcomes, severity, messages


def _max_severity(a: str, b: str) -> str:
    from .report import SEVERITY_ORDER
    return a if SEVERITY_ORDER[a] >= SEVERITY_ORDER[b] else b


def _stats(latencies: list[float], costs: list[float]) -> dict:
    return {
        "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
        "avg_cost": sum(costs) / len(costs) if costs else 0,
        "n": len(latencies),
    }
