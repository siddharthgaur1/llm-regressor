"""Dashboard report loading.

Only the pure functions are tested — the Streamlit rendering is not worth a
browser harness. `load_reports` is the part with real logic: it has to ignore
JSON that isn't ours and order runs correctly, and both failures are silent.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

pytest.importorskip("streamlit", reason="dashboard extra not installed")
pytest.importorskip("plotly", reason="dashboard extra not installed")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dashboard"))

from app import META_IDS, load_reports, real_rows  # noqa: E402


def _report(run_dir, critical=1, name="results.json"):
    run_dir.mkdir(parents=True, exist_ok=True)
    regressions = [
        {"test_id": f"t{i}", "severity": "CRITICAL" if i < critical else "PASS",
         "message": "m", "baseline_response": "b", "candidate_response": "c", "checks": []}
        for i in range(3)
    ] + [
        {"test_id": "__latency__", "severity": "PASS", "message": "lat"},
        {"test_id": "__cost__", "severity": "PASS", "message": "cost"},
    ]
    payload = {
        "baseline": "a", "candidate": "b", "passed": critical == 0,
        "counts": {"CRITICAL": critical, "WARNING": 0, "INFO": 0, "PASS": 3 - critical},
        "baseline_stats": {"avg_latency_ms": 10, "avg_cost": 0.1},
        "candidate_stats": {"avg_latency_ms": 20, "avg_cost": 0.2},
        "regressions": regressions,
    }
    (run_dir / name).write_text(json.dumps(payload))
    return run_dir / name


def test_loads_reports_from_nested_run_directories(tmp_path):
    _report(tmp_path / "run-001")
    _report(tmp_path / "run-002")
    load_reports.clear()
    reports = load_reports(str(tmp_path))
    assert len(reports) == 2
    assert {r["_run"] for r in reports} == {"run-001", "run-002"}


def test_ignores_json_that_is_not_an_llm_regressor_report(tmp_path):
    _report(tmp_path / "run-001")
    (tmp_path / "package.json").write_text('{"name": "unrelated"}')
    (tmp_path / "broken.json").write_text("{not json")
    load_reports.clear()
    assert len(load_reports(str(tmp_path))) == 1


def test_empty_directory_returns_nothing_rather_than_raising(tmp_path):
    load_reports.clear()
    assert load_reports(str(tmp_path)) == []


def test_run_name_falls_back_to_filename_when_not_results_json(tmp_path):
    _report(tmp_path, name="nightly.json")
    load_reports.clear()
    assert load_reports(str(tmp_path))[0]["_run"] == "nightly"


def test_real_rows_excludes_the_synthetic_meta_entries(tmp_path):
    path = _report(tmp_path / "run-001")
    report = json.loads(path.read_text())
    rows = real_rows(report)
    assert len(rows) == 3
    assert not {r["test_id"] for r in rows} & META_IDS
