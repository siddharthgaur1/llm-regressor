from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

SEVERITY_ORDER = {"PASS": 0, "INFO": 1, "WARNING": 2, "CRITICAL": 3}


@dataclass
class CheckOutcome:
    check_type: str
    passed: bool
    detail: str
    baseline_detail: str = ""
    candidate_detail: str = ""


@dataclass
class Regression:
    test_id: str
    severity: str  # PASS | INFO | WARNING | CRITICAL
    message: str
    baseline_response: str = ""
    candidate_response: str = ""
    checks: list[CheckOutcome] = field(default_factory=list)


@dataclass
class Report:
    baseline_label: str
    candidate_label: str
    regressions: list[Regression]
    baseline_stats: dict = field(default_factory=dict)
    candidate_stats: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not any(r.severity == "CRITICAL" for r in self.regressions)

    def counts(self) -> dict:
        out = {"CRITICAL": 0, "WARNING": 0, "INFO": 0, "PASS": 0}
        for r in self.regressions:
            out[r.severity] += 1
        return out

    def counts_by_category(self, test_categories: dict[str, str]) -> dict[str, dict[str, int]]:
        """Bucket regression severities by test category.

        Args:
            test_categories: Maps test_id -> category (e.g. from TestCase.category).
                Synthetic rows like ``__latency__``/``__cost__`` are grouped under "meta".
        """
        out: dict[str, dict[str, int]] = {}
        for r in self.regressions:
            category = test_categories.get(r.test_id, "meta")
            bucket = out.setdefault(category, {"CRITICAL": 0, "WARNING": 0, "INFO": 0, "PASS": 0})
            bucket[r.severity] += 1
        return out

    def summary(self, console: Console | None = None) -> None:
        """Print the results table. Pass `console` to render somewhere other
        than stdout — a file, a string buffer, or a recording console."""
        from rich.console import Console
        from rich.table import Table

        console = console or Console()
        table = Table(title=f"{self.baseline_label}  vs  {self.candidate_label}")
        table.add_column("Test ID")
        table.add_column("Severity")
        table.add_column("Message")
        style = {"CRITICAL": "bold red", "WARNING": "bold yellow", "INFO": "bold blue", "PASS": "bold green"}
        for r in sorted(self.regressions, key=lambda r: -SEVERITY_ORDER[r.severity]):
            table.add_row(r.test_id, f"[{style[r.severity]}]{r.severity}[/]", r.message)
        console.print(table)
        c = self.counts()
        console.print(f"Regressions: {c['CRITICAL']} CRITICAL, {c['WARNING']} WARNING, {c['INFO']} INFO")
        console.print(f"Overall: {'PASSED' if self.passed else 'FAILED'}")

    def to_dict(self) -> dict:
        return {
            "baseline": self.baseline_label,
            "candidate": self.candidate_label,
            "passed": self.passed,
            "counts": self.counts(),
            "baseline_stats": self.baseline_stats,
            "candidate_stats": self.candidate_stats,
            "regressions": [asdict(r) for r in self.regressions],
        }

    def to_json(self, path: str | Path = "report.json") -> Path:
        path = Path(path)
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path

    def to_html(self, path: str | Path = "report.html") -> Path:
        from jinja2 import Environment, FileSystemLoader

        template_dir = Path(__file__).parent.parent / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template("report.html")
        html = template.render(report=self.to_dict())
        path = Path(path)
        path.write_text(html, encoding="utf-8")
        return path
