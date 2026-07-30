from pathlib import Path

from llm_regressor.core.test_suite import TestSuite


def test_from_yaml(tmp_path: Path):
    suite_file = tmp_path / "suite.yaml"
    suite_file.write_text("""
tests:
  - id: t1
    input: "hi"
    checks:
      - type: contains
        value: "hi"
    category: greeting
""")
    suite = TestSuite.from_yaml(suite_file)
    assert len(suite) == 1
    test = suite.tests[0]
    assert test.id == "t1"
    assert test.category == "greeting"
    assert test.checks[0].type == "contains"
    assert test.checks[0].params == {"value": "hi"}


def test_from_list():
    suite = TestSuite.from_list([{"id": "t1", "input": "x", "checks": []}])
    assert len(suite) == 1
    assert suite.tests[0].id == "t1"
