from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from . import providers
from .core import Regressor, TestSuite

_STARTER_SUITE = """tests:
  - id: factual_capital
    input: "What is the capital of France?"
    expected: "Paris"
    checks:
      - type: contains
        value: "Paris"
    category: factual

  - id: sentiment_classification
    input: "Classify the sentiment of: 'The product is terrible'"
    checks:
      - type: semantic_similarity
        reference: "negative sentiment"
        threshold: 0.6
      - type: length_range
        min: 1
        max: 200
    category: classification
"""


def _make_provider(model: str, prompt_file: str | None) -> providers.BaseProvider:
    system_prompt = Path(prompt_file).read_text() if prompt_file else None
    if model.startswith("claude"):
        return providers.Anthropic(model=model, system_prompt=system_prompt)
    if model.startswith("gpt") or model.startswith("o1"):
        return providers.OpenAI(model=model, system_prompt=system_prompt)
    return providers.LiteLLM(model=model, system_prompt=system_prompt)


@click.group()
def main():
    """llm-regressor: detect regressions between LLM model versions or prompt changes."""


@main.command()
@click.option("--suite", required=True, type=click.Path(exists=True), help="Path to the test suite YAML.")
@click.option("--baseline", default=None, help="Baseline model name, e.g. claude-sonnet-5.")
@click.option("--candidate", default=None, help="Candidate model name, e.g. claude-haiku-4-5-20251001.")
@click.option("--baseline-prompt", default=None, type=click.Path(exists=True), help="System prompt file for baseline (same model as candidate).")
@click.option("--candidate-prompt", default=None, type=click.Path(exists=True), help="System prompt file for candidate.")
@click.option("--samples", default=1, help="Runs per test, for consistency measurement.")
@click.option("--out", default="results.json", help="Where to write the JSON report.")
@click.option("--html", default=None, help="Optional path to also write an HTML report.")
def run(suite, baseline, candidate, baseline_prompt, candidate_prompt, samples, out, html):
    """Run a test suite comparing a baseline config against a candidate config."""
    suite_obj = TestSuite.from_yaml(suite)

    if baseline_prompt and candidate_prompt:
        model = baseline or candidate or "claude-sonnet-5"
        baseline_provider = _make_provider(model, baseline_prompt)
        candidate_provider = _make_provider(model, candidate_prompt)
    elif baseline and candidate:
        baseline_provider = _make_provider(baseline, None)
        candidate_provider = _make_provider(candidate, None)
    else:
        raise click.UsageError("Pass either --baseline/--candidate or --baseline-prompt/--candidate-prompt.")

    reg = Regressor(baseline=baseline_provider, candidate=candidate_provider)
    with click.progressbar(length=len(suite_obj), label="Running tests") as bar:
        report = reg.run(suite_obj, samples=samples)
        bar.update(len(suite_obj))

    report.summary()
    report.to_json(out)
    click.echo(f"JSON report written to {out}")
    if html:
        report.to_html(html)
        click.echo(f"HTML report written to {html}")

    sys.exit(0 if report.passed else 1)


@main.command()
@click.option("--input", "input_path", required=True, type=click.Path(exists=True))
@click.option("--format", "fmt", type=click.Choice(["html", "json"]), default="html")
@click.option("--out", default=None)
def report(input_path, fmt, out):
    """Re-render a previously saved results.json as html or json."""
    data = json.loads(Path(input_path).read_text())
    out = out or f"report.{fmt}"
    if fmt == "json":
        Path(out).write_text(json.dumps(data, indent=2))
    else:
        from jinja2 import Environment, FileSystemLoader

        template_dir = Path(__file__).parent / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        Path(out).write_text(env.get_template("report.html").render(report=data), encoding="utf-8")
    click.echo(f"Wrote {out}")


@main.command()
def init():
    """Scaffold a starter suite.yaml in the current directory."""
    path = Path("suite.yaml")
    if path.exists():
        raise click.ClickException(f"{path} already exists.")
    path.write_text(_STARTER_SUITE)
    click.echo(f"Wrote {path}")


if __name__ == "__main__":
    main()
