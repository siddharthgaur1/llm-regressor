"""Optional Slack webhook alert for a completed Report.

Ported from the llm-regression-detector prototype (merged into this repo —
see CHANGELOG). Requires the `httpx` extra: `pip install llm-regressor[all]`.
"""
from __future__ import annotations

import logging
import os

from .report import Report

logger = logging.getLogger(__name__)

SEVERITY_EMOJI = {"CRITICAL": "\U0001f534", "WARNING": "⚠️", "INFO": "ℹ️", "PASS": "✅"}


def send_slack_alert(report: Report, report_url: str | None = None) -> None:
    """POST a run summary to SLACK_WEBHOOK_URL. No-ops with a warning if the env var is unset.

    Raises:
        ImportError: if httpx isn't installed.
        httpx.HTTPStatusError: if Slack rejects the webhook request.
    """
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL not set, skipping Slack alert")
        return

    import httpx

    counts = report.counts()
    emoji = SEVERITY_EMOJI["CRITICAL"] if counts["CRITICAL"] else (
        SEVERITY_EMOJI["WARNING"] if counts["WARNING"] else SEVERITY_EMOJI["PASS"]
    )
    headline = f"{emoji} *{report.baseline_label} → {report.candidate_label}*: {counts['CRITICAL']} critical, {counts['WARNING']} warning"
    text = headline if not report_url else f"{headline}\n<{report_url}|View full report>"

    response = httpx.post(webhook_url, json={"text": text}, timeout=10)
    response.raise_for_status()
    logger.info("Slack alert sent")
