from llm_regressor.checks.deterministic import (
    contains, not_contains, regex_match, length_range, json_valid, starts_with, ends_with,
)


def test_contains():
    assert contains("Paris is the capital", "Paris")[0] is True
    assert contains("Paris is the capital", "Tokyo")[0] is False


def test_not_contains():
    assert not_contains("safe response", "DROP TABLE")[0] is True
    assert not_contains("DROP TABLE users", "DROP TABLE")[0] is False


def test_regex_match():
    assert regex_match("SELECT * FROM t ORDER BY x LIMIT 5", r"SELECT.*FROM.*ORDER BY.*LIMIT 5")[0] is True
    assert regex_match("no match here", r"SELECT.*FROM")[0] is False


def test_length_range():
    assert length_range("hello", min=1, max=10)[0] is True
    assert length_range("hello", min=10, max=20)[0] is False


def test_json_valid():
    assert json_valid('{"a": 1}')[0] is True
    assert json_valid("not json")[0] is False


def test_starts_ends_with():
    assert starts_with("hello world", "hello")[0] is True
    assert ends_with("hello world", "world")[0] is True
    assert starts_with("hello world", "world")[0] is False
