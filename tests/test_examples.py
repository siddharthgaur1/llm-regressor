"""The bundled examples are documentation, and documentation rots silently.

The demo's transcript is pasted into docs/example.md, so if it stops producing
that result the docs become a lie. This is the cheapest way to notice.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
EXAMPLES = sorted((REPO / "examples").glob("*.yaml"))


def test_examples_directory_is_not_empty():
    assert EXAMPLES


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_every_bundled_suite_parses(path):
    from llm_regressor.core import TestSuite

    suite = TestSuite.from_yaml(path)
    assert len(suite) > 0
    for test in suite:
        assert test.id and test.input


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_every_bundled_suite_uses_real_check_types(path):
    from llm_regressor.checks import ALL_CHECKS

    raw = yaml.safe_load(path.read_text())
    for test in raw["tests"]:
        for check in test.get("checks", []):
            # Unknown types are skipped at runtime rather than erroring, so a
            # typo in a shipped example would silently check nothing.
            assert check["type"] in ALL_CHECKS, f"{path.name}: unknown check {check['type']!r}"


def test_demo_fails_with_the_regression_it_is_meant_to_show(tmp_path):
    result = subprocess.run(
        [sys.executable, str(REPO / "examples" / "prompt_regression_demo.py")],
        capture_output=True,
        text=True,
        # rich draws the summary with box-drawing characters, which the default
        # console encoding on Windows cannot decode.
        encoding="utf-8",
        # COV_CORE_* stripped: pytest-cov's subprocess hook would otherwise
        # start a second collector here, and because cwd is a tmp dir it would
        # not find pyproject.toml, so it writes statement-only data that then
        # refuses to merge with the parent's branch data.
        env={
            **{k: v for k, v in os.environ.items() if not k.startswith("COV_CORE_")},
            "PYTHONIOENCODING": "utf-8",
        },
        cwd=tmp_path,
        timeout=120,
    )
    assert result.returncode == 1, result.stderr
    # Exact strings quoted in docs/example.md.
    assert "3 CRITICAL, 0 WARNING, 0 INFO" in result.stdout
    assert "json_valid failed" in result.stdout
    assert "Overall: FAILED" in result.stdout
    assert (tmp_path / "demo-report.html").exists()
