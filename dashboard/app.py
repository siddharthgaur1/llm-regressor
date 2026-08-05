"""Streamlit dashboard over a directory of llm-regressor JSON reports.

`llm-regressor run --out results.json` writes one report per run. Point this at
the directory holding them and it gives what a single report cannot: whether
the trend is drifting, and which test IDs regress repeatedly rather than once.

    pip install "llm-regressor[dashboard]"
    streamlit run dashboard/app.py -- --reports ./reports

Ported from the llm-regression-detector prototype (merged into this repo, see
CHANGELOG). Rewritten rather than copied: the original read that project's own
run format, and carrying a second incompatible schema into this package would
have meant two ways of representing the same thing.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

SEVERITIES = ["CRITICAL", "WARNING", "INFO", "PASS"]
META_IDS = {"__latency__", "__cost__"}


@st.cache_data(show_spinner=False)
def load_reports(directory: str) -> list[dict]:
    """Read every JSON report in `directory`, newest last by mtime.

    Sorted by modification time rather than filename: run outputs are commonly
    called results.json in dated folders, and lexical order on those is wrong
    as soon as anyone uses a non-padded number.
    """
    reports = []
    for path in sorted(Path(directory).rglob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if "regressions" not in data or "counts" not in data:
            continue  # not one of ours
        data["_run"] = path.parent.name if path.name == "results.json" else path.stem
        reports.append(data)
    return reports


def real_rows(report: dict) -> list[dict]:
    """Per-test rows, excluding the synthetic __latency__/__cost__ entries."""
    return [r for r in report["regressions"] if r["test_id"] not in META_IDS]


def main() -> None:
    st.set_page_config(page_title="llm-regressor", layout="wide")
    st.title("llm-regressor")

    default_dir = os.environ.get("LLM_REGRESSOR_REPORTS", "reports")
    directory = st.sidebar.text_input("Reports directory", default_dir)

    reports = load_reports(directory)
    if not reports:
        st.info(
            f"No llm-regressor reports found in `{directory}`.\n\n"
            "Generate one with:\n\n"
            "```bash\n"
            "llm-regressor run --suite suite.yaml \\\n"
            "  --baseline claude-sonnet-5 --candidate claude-haiku-4-5-20251001 \\\n"
            "  --out reports/run-001/results.json\n"
            "```"
        )
        st.stop()

    latest = reports[-1]

    st.header("Latest run")
    c = latest["counts"]
    cols = st.columns(5)
    cols[0].metric("Verdict", "PASS" if latest["passed"] else "FAIL")
    for col, sev in zip(cols[1:], SEVERITIES[:4], strict=True):
        col.metric(sev.title(), c.get(sev, 0))
    st.caption(f"`{latest['baseline']}` → `{latest['candidate']}`")

    st.header("Trend")
    trend = pd.DataFrame([
        {
            "run": r["_run"],
            "critical": r["counts"].get("CRITICAL", 0),
            "warning": r["counts"].get("WARNING", 0),
            "pass_rate": (
                sum(1 for x in real_rows(r) if x["severity"] == "PASS") / len(real_rows(r))
                if real_rows(r) else 0.0
            ),
            "avg_latency_ms": r.get("candidate_stats", {}).get("avg_latency_ms", 0),
            "avg_cost": r.get("candidate_stats", {}).get("avg_cost", 0),
        }
        for r in reports
    ])

    left, right = st.columns(2)
    left.plotly_chart(
        px.line(trend, x="run", y="pass_rate", markers=True, title="Pass rate"),
        use_container_width=True,
    )
    right.plotly_chart(
        px.bar(trend, x="run", y=["critical", "warning"], title="Regressions by severity"),
        use_container_width=True,
    )

    cost_col, lat_col = st.columns(2)
    lat_col.plotly_chart(
        px.line(trend, x="run", y="avg_latency_ms", markers=True, title="Candidate avg latency (ms)"),
        use_container_width=True,
    )
    cost_col.plotly_chart(
        px.line(trend, x="run", y="avg_cost", markers=True, title="Candidate avg cost ($)"),
        use_container_width=True,
    )

    st.header("Repeat offenders")
    st.caption(
        "Test IDs that came back CRITICAL in more than one run. A test that "
        "fails once is a regression; a test that fails across runs is usually "
        "a bad test or an unstable prompt, and is worth looking at first."
    )
    failures: dict[str, int] = {}
    for r in reports:
        for row in real_rows(r):
            if row["severity"] == "CRITICAL":
                failures[row["test_id"]] = failures.get(row["test_id"], 0) + 1
    repeats = {k: v for k, v in failures.items() if v > 1}
    if repeats:
        st.dataframe(
            pd.DataFrame(
                sorted(repeats.items(), key=lambda kv: -kv[1]),
                columns=["test_id", "runs failed"],
            ),
            use_container_width=True,
        )
    else:
        st.success("No test failed in more than one run.")

    st.header("Run explorer")
    run_names = [r["_run"] for r in reports]
    chosen = st.selectbox("Run", run_names, index=len(run_names) - 1)
    report = reports[run_names.index(chosen)]

    rows = pd.DataFrame([
        {
            "test_id": r["test_id"],
            "severity": r["severity"],
            "message": r["message"],
            "baseline_response": r.get("baseline_response", ""),
            "candidate_response": r.get("candidate_response", ""),
        }
        for r in real_rows(report)
    ])
    severity_filter = st.multiselect("Severity", SEVERITIES, default=["CRITICAL", "WARNING"])
    if severity_filter:
        rows = rows[rows["severity"].isin(severity_filter)]
    st.dataframe(rows, use_container_width=True)

    st.header("Side-by-side")
    if not rows.empty:
        test_id = st.selectbox("Test", rows["test_id"].tolist())
        row = rows[rows["test_id"] == test_id].iloc[0]
        st.caption(row["message"])
        a, b = st.columns(2)
        a.subheader("Baseline")
        a.code(row["baseline_response"] or "(empty)")
        b.subheader("Candidate")
        b.code(row["candidate_response"] or "(empty)")


if __name__ == "__main__":
    main()
