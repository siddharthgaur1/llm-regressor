"""CLI surface, including the bit that actually matters in CI: the exit code.

`llm-regressor run` is meant to gate a pipeline, so exit 0 vs 1 is the
contract other people's workflows depend on. Everything else here is
plumbing, but that one assertion is the product.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import FakeProvider

from llm_regressor import cli


@pytest.fixture
def runner():
    return CliRunner()


def _patch_providers(monkeypatch, baseline_response, candidate_response):
    made = []

    def fake_make(model, prompt_file):
        response = baseline_response if not made else candidate_response
        provider = FakeProvider(response, model=model)
        made.append((model, prompt_file))
        return provider

    monkeypatch.setattr(cli, "_make_provider", fake_make)
    return made


# --- run --------------------------------------------------------------------


def test_run_exits_zero_when_the_candidate_holds_up(runner, monkeypatch, suite_yaml, tmp_path):
    _patch_providers(monkeypatch, "Paris", "Paris")
    out = tmp_path / "results.json"
    result = runner.invoke(
        cli.main,
        ["run", "--suite", str(suite_yaml), "--baseline", "a", "--candidate", "b", "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(out.read_text())["passed"] is True


def test_run_exits_one_on_a_critical_regression(runner, monkeypatch, suite_yaml, tmp_path):
    _patch_providers(monkeypatch, "Paris", "Tokyo")
    out = tmp_path / "results.json"
    result = runner.invoke(
        cli.main,
        ["run", "--suite", str(suite_yaml), "--baseline", "a", "--candidate", "b", "--out", str(out)],
    )
    assert result.exit_code == 1
    assert json.loads(out.read_text())["passed"] is False


def test_run_writes_html_only_when_asked(runner, monkeypatch, suite_yaml, tmp_path):
    _patch_providers(monkeypatch, "Paris", "Paris")
    html = tmp_path / "r.html"
    result = runner.invoke(
        cli.main,
        [
            "run", "--suite", str(suite_yaml), "--baseline", "a", "--candidate", "b",
            "--out", str(tmp_path / "r.json"), "--html", str(html),
        ],
    )
    assert result.exit_code == 0
    assert html.exists()
    assert "HTML report written" in result.output


def test_run_in_prompt_mode_uses_one_model_with_two_prompts(runner, monkeypatch, suite_yaml, tmp_path):
    made = _patch_providers(monkeypatch, "Paris", "Paris")
    base_prompt = tmp_path / "base.txt"
    cand_prompt = tmp_path / "cand.txt"
    base_prompt.write_text("be terse")
    cand_prompt.write_text("be verbose")

    result = runner.invoke(
        cli.main,
        [
            "run", "--suite", str(suite_yaml),
            "--baseline-prompt", str(base_prompt), "--candidate-prompt", str(cand_prompt),
            "--out", str(tmp_path / "r.json"),
        ],
    )
    assert result.exit_code == 0
    # Same model on both sides; only the prompt file differs. That is the point
    # of prompt mode — otherwise you cannot attribute the delta to the prompt.
    assert made[0][0] == made[1][0] == "claude-sonnet-5"
    assert [str(base_prompt), str(cand_prompt)] == [made[0][1], made[1][1]]


def test_run_without_either_pair_of_options_is_a_usage_error(runner, suite_yaml, tmp_path):
    result = runner.invoke(cli.main, ["run", "--suite", str(suite_yaml), "--out", str(tmp_path / "r.json")])
    assert result.exit_code == 2
    assert "Pass either" in result.output


def test_run_rejects_a_missing_suite_file(runner):
    result = runner.invoke(cli.main, ["run", "--suite", "nope.yaml", "--baseline", "a", "--candidate", "b"])
    assert result.exit_code == 2


# --- report -----------------------------------------------------------------


def _results_json(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(json.dumps({
        "baseline": "a", "candidate": "b", "passed": False,
        "counts": {"CRITICAL": 1, "WARNING": 0, "INFO": 0, "PASS": 0},
        "baseline_stats": {}, "candidate_stats": {},
        "regressions": [{
            "test_id": "t1", "severity": "CRITICAL", "message": "failed",
            "baseline_response": "Paris", "candidate_response": "Tokyo", "checks": [],
        }],
    }))
    return path


def test_report_rerenders_saved_results_as_html(runner, tmp_path):
    # Stats deliberately empty: `report` re-renders a file the user supplies,
    # so a missing stat must degrade to 0, not abort the render.
    src = _results_json(tmp_path)
    out = tmp_path / "out.html"
    result = runner.invoke(cli.main, ["report", "--input", str(src), "--out", str(out)])
    assert result.exit_code == 0
    html = out.read_text(encoding="utf-8")
    assert "t1" in html
    assert "avg latency: 0ms" in html


def test_report_rerenders_saved_results_as_json(runner, tmp_path):
    src = _results_json(tmp_path)
    out = tmp_path / "out.json"
    result = runner.invoke(cli.main, ["report", "--input", str(src), "--format", "json", "--out", str(out)])
    assert result.exit_code == 0
    assert json.loads(out.read_text())["regressions"][0]["test_id"] == "t1"


def test_report_rejects_an_unknown_format(runner, tmp_path):
    result = runner.invoke(cli.main, ["report", "--input", str(_results_json(tmp_path)), "--format", "pdf"])
    assert result.exit_code == 2


# --- init -------------------------------------------------------------------


def test_init_scaffolds_a_loadable_suite(runner):
    from llm_regressor.core import TestSuite

    with runner.isolated_filesystem():
        result = runner.invoke(cli.main, ["init"])
        assert result.exit_code == 0
        # The scaffold has to actually parse; a starter file that fails on first
        # run is worse than no starter file.
        suite = TestSuite.from_yaml(Path("suite.yaml"))
        assert {t.id for t in suite} == {"factual_capital", "sentiment_classification"}


def test_init_refuses_to_clobber_an_existing_suite(runner):
    with runner.isolated_filesystem():
        Path("suite.yaml").write_text("tests: []")
        result = runner.invoke(cli.main, ["init"])
        assert result.exit_code == 1
        assert "already exists" in result.output
        assert Path("suite.yaml").read_text() == "tests: []"


# --- provider routing -------------------------------------------------------


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("claude-sonnet-5", "anthropic"),
        ("gpt-4o-mini", "openai"),
        ("o1", "openai"),
        ("bedrock/anthropic.claude-v2", "litellm"),
        ("gemini/gemini-1.5-pro", "litellm"),
    ],
)
def test_make_provider_routes_on_model_prefix(monkeypatch, model, expected):
    seen = {}

    for attr in ("Anthropic", "OpenAI", "LiteLLM"):
        def recorder(name):
            def make(model, system_prompt=None, **kw):
                seen["name"] = name
                return FakeProvider("", model=model)
            return make
        monkeypatch.setattr(cli.providers, attr, recorder(attr.lower()))

    cli._make_provider(model, None)
    assert seen["name"] == expected


def test_make_provider_reads_the_system_prompt_file(monkeypatch, tmp_path):
    prompt = tmp_path / "p.txt"
    prompt.write_text("be terse")
    captured = {}

    def fake_anthropic(model, system_prompt=None, **kw):
        captured["system_prompt"] = system_prompt
        return FakeProvider("", model=model)

    monkeypatch.setattr(cli.providers, "Anthropic", fake_anthropic)
    cli._make_provider("claude-sonnet-5", str(prompt))
    assert captured["system_prompt"] == "be terse"
