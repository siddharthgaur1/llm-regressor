"""llm-regressor: detect regressions between LLM model versions or prompt changes.

Public API — the names below are covered by semantic versioning:

    Regressor                          run a suite against a baseline/candidate pair
    TestSuite, TestCase, Check         the suite model (also loadable from YAML)
    Report, Regression, CheckOutcome   the result model
    providers                          BaseProvider + the bundled provider implementations
    send_slack_alert                   optional Slack notification for a finished Report

Everything else — including ``llm_regressor.checks`` (the check registries),
``llm_regressor.cli``, and any name starting with ``_`` — is internal and may
change in a patch release. To add a custom check, register a
``(response: str, **params) -> tuple[bool, str]`` callable in
``llm_regressor.checks.ALL_CHECKS``, accepting that this hook is provisional.
"""
from . import providers
from .core import Check, CheckOutcome, Regression, Regressor, Report, TestCase, TestSuite
from .core.alerting import send_slack_alert

__version__ = "0.1.0"
__all__ = [
    "Check",
    "CheckOutcome",
    "Regression",
    "Regressor",
    "Report",
    "TestCase",
    "TestSuite",
    "providers",
    "send_slack_alert",
]
