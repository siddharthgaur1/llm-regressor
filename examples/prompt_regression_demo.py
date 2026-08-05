"""End-to-end demo of a prompt regression, with no API key required.

The scenario: a support-bot prompt is edited to make replies friendlier. The
edit works — replies do get friendlier — but it also stops the model wrapping
its output in JSON, which the downstream ticketing integration depends on.
Nothing in a normal test suite notices. This is what llm-regressor is for.

The two "models" here are scripted providers replaying responses recorded from
a real run, so this file is deterministic and free to run:

    python examples/prompt_regression_demo.py

Swap `_Scripted` for `providers.Anthropic(...)` and it becomes a real run.
"""
from __future__ import annotations

import time

from llm_regressor import Regressor, TestSuite
from llm_regressor.providers import BaseProvider, CompletionResult

SUITE = [
    {
        "id": "refund_request",
        "input": "I want a refund for order 4471.",
        "category": "support",
        "checks": [
            {"type": "json_valid"},
            {"type": "contains", "value": "4471"},
        ],
    },
    {
        "id": "escalation",
        "input": "This is the third time I've contacted you. Escalate this.",
        "category": "support",
        "checks": [
            {"type": "json_valid"},
            {"type": "not_contains", "value": "I cannot"},
        ],
    },
    {
        "id": "order_status",
        "input": "Where is order 9982?",
        "category": "support",
        "checks": [
            {"type": "json_valid"},
            {"type": "contains", "value": "9982"},
        ],
    },
]

# v1: "Always reply with a JSON object containing `reply` and `order_id`."
V1_RESPONSES = {
    "refund_request": '{"reply": "I can help with that refund.", "order_id": "4471"}',
    "escalation": '{"reply": "Escalating this to a senior agent now.", "order_id": null}',
    "order_status": '{"reply": "Order is out for delivery.", "order_id": "9982"}',
}

# v2: the same prompt plus "Be warm and personable." The model reads the two
# instructions as being in tension and quietly drops the JSON wrapper.
V2_RESPONSES = {
    "refund_request": "Of course — I'm sorry about the trouble with order 4471! I can help with that refund.",
    "escalation": "I'm really sorry it's taken three tries. I'm escalating this to a senior agent right now.",
    "order_status": "Good news — order 9982 is out for delivery and should reach you today!",
}


class _Scripted(BaseProvider):
    """Replays recorded responses. Real providers hit the network; this one
    makes the example reproducible."""

    name = "scripted"

    def __init__(self, responses: dict[str, str], prompts: dict[str, str], latency_ms: float):
        super().__init__(model="support-bot")
        self._by_prompt = {prompts[k]: v for k, v in responses.items()}
        self._latency_ms = latency_ms

    def complete(self, prompt: str) -> CompletionResult:
        time.sleep(0.001)
        return CompletionResult(
            response=self._by_prompt[prompt],
            latency_ms=self._latency_ms,
            input_tokens=120,
            output_tokens=40,
            cost=0.0004,
        )


def main() -> int:
    suite = TestSuite.from_list(SUITE)
    prompts = {t["id"]: t["input"] for t in SUITE}

    report = Regressor(
        baseline=_Scripted(V1_RESPONSES, prompts, latency_ms=820.0),
        candidate=_Scripted(V2_RESPONSES, prompts, latency_ms=910.0),
    ).run(suite)

    report.summary()

    print("\nBy category:")
    for category, counts in report.counts_by_category({t.id: t.category for t in suite}).items():
        print(f"  {category}: {counts}")

    report.to_html("demo-report.html")
    print("\nWrote demo-report.html")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
