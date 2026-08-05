from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Check:
    type: str
    params: dict = field(default_factory=dict)


@dataclass
class TestCase:
    id: str
    input: str
    checks: list[Check]
    expected: str | None = None
    category: str = "general"


@dataclass
class TestSuite:
    tests: list[TestCase]

    @classmethod
    def from_yaml(cls, path: str | Path) -> TestSuite:
        data = yaml.safe_load(Path(path).read_text())
        return cls.from_list(data.get("tests", []))

    @classmethod
    def from_list(cls, tests: list[dict]) -> TestSuite:
        parsed = []
        for raw in tests:
            checks = [
                Check(type=c["type"], params={k: v for k, v in c.items() if k != "type"})
                for c in raw.get("checks", [])
            ]
            parsed.append(TestCase(
                id=raw["id"],
                input=raw["input"],
                checks=checks,
                expected=raw.get("expected"),
                category=raw.get("category", "general"),
            ))
        return cls(tests=parsed)

    def __iter__(self):
        return iter(self.tests)

    def __len__(self):
        return len(self.tests)
