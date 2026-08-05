
import httpx

from llm_regressor.core.alerting import send_slack_alert
from llm_regressor.core.report import Regression, Report


def _report():
    return Report(
        baseline_label="baseline",
        candidate_label="candidate",
        regressions=[
            Regression(test_id="t1", severity="CRITICAL", message="failed"),
            Regression(test_id="t2", severity="PASS", message="ok"),
            Regression(test_id="__latency__", severity="PASS", message="ok"),
        ],
    )


def test_summary_renders_into_a_supplied_console():
    # The console parameter exists so the summary can be captured or recorded
    # rather than only written to stdout; examples/render_demo_svg.py relies on
    # it to build the README image out of real output.
    import io

    from rich.console import Console

    buffer = io.StringIO()
    _report().summary(console=Console(file=buffer, width=120))
    output = buffer.getvalue()
    assert "t1" in output
    assert "CRITICAL" in output
    assert "Overall: FAILED" in output


def test_summary_defaults_to_stdout(capsys):
    _report().summary()
    assert "Overall: FAILED" in capsys.readouterr().out


def test_counts_by_category_buckets_and_labels_meta_rows():
    report = _report()
    buckets = report.counts_by_category({"t1": "factual", "t2": "factual"})
    assert buckets["factual"] == {"CRITICAL": 1, "WARNING": 0, "INFO": 0, "PASS": 1}
    assert buckets["meta"]["PASS"] == 1


def test_send_slack_alert_noops_without_webhook_url(monkeypatch, caplog):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    send_slack_alert(_report())
    assert "skipping Slack alert" in caplog.text


def test_send_slack_alert_posts_to_webhook(monkeypatch):
    calls = []

    def fake_post(url, json, timeout):
        calls.append((url, json))
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.test/x")
    monkeypatch.setattr(httpx, "post", fake_post)
    send_slack_alert(_report(), report_url="https://example.com/report.html")

    assert len(calls) == 1
    url, payload = calls[0]
    assert url == "https://hooks.slack.test/x"
    assert "1 critical" in payload["text"]
    assert "https://example.com/report.html" in payload["text"]
