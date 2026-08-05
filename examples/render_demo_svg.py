"""Regenerate docs/assets/demo.svg from the demo's real output.

Not a hand-drawn mockup: this runs `prompt_regression_demo` and records what
rich actually printed, so the image in the README cannot drift from the tool's
behaviour. Rerun after any change to report formatting:

    python examples/render_demo_svg.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

from rich.console import Console

sys.path.insert(0, str(Path(__file__).parent))

from prompt_regression_demo import SUITE, V1_RESPONSES, V2_RESPONSES, _Scripted  # noqa: E402

from llm_regressor import Regressor, TestSuite  # noqa: E402

OUT = Path(__file__).parent.parent / "docs" / "assets" / "demo.svg"


def main() -> None:
    # Write into a buffer, not this terminal: `quiet=True` would suppress the
    # recording as well as the output. force_terminal keeps the colour codes
    # that the SVG export renders.
    console = Console(record=True, width=100, file=io.StringIO(), force_terminal=True)

    prompts = {t["id"]: t["input"] for t in SUITE}
    suite = TestSuite.from_list(SUITE)
    report = Regressor(
        baseline=_Scripted(V1_RESPONSES, prompts, latency_ms=820.0),
        candidate=_Scripted(V2_RESPONSES, prompts, latency_ms=910.0),
    ).run(suite)

    console.print("[bold]$[/] llm-regressor run --suite tests/support_suite.yaml \\")
    console.print("      --baseline-prompt prompts/v1.txt --candidate-prompt prompts/v2.txt")
    console.print()
    report.summary(console=console)
    console.print()
    console.print("[dim]$ echo $?[/]")
    console.print("1")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    console.save_svg(str(OUT), title="llm-regressor")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
