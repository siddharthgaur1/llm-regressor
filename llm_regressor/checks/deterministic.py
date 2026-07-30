"""Deterministic checks: pure functions of the response text, no LLM call needed.

Each check function takes (response: str, **params) and returns (passed: bool, detail: str).
"""
from __future__ import annotations

import json
import re


def contains(response: str, value: str, **_) -> tuple[bool, str]:
    ok = value in response
    return ok, f"expected substring {value!r}" if not ok else "ok"


def not_contains(response: str, value: str, **_) -> tuple[bool, str]:
    ok = value not in response
    return ok, f"unexpected substring {value!r} present" if not ok else "ok"


def regex_match(response: str, pattern: str, flags: str = "", **_) -> tuple[bool, str]:
    re_flags = getattr(re, flags, 0) if flags else 0
    ok = re.search(pattern, response, re_flags) is not None
    return ok, f"no match for /{pattern}/" if not ok else "ok"


# format_match is the same mechanic as regex_match, kept as a distinct name per the check-type spec.
format_match = regex_match


def length_range(response: str, min: int = 0, max: int = 10**9, **_) -> tuple[bool, str]:
    n = len(response)
    ok = min <= n <= max
    return ok, f"length {n} outside [{min}, {max}]" if not ok else "ok"


def json_valid(response: str, **_) -> tuple[bool, str]:
    try:
        json.loads(response)
        return True, "ok"
    except json.JSONDecodeError as e:
        return False, f"invalid JSON: {e}"


def starts_with(response: str, prefix: str, **_) -> tuple[bool, str]:
    ok = response.startswith(prefix)
    return ok, f"does not start with {prefix!r}" if not ok else "ok"


def ends_with(response: str, suffix: str, **_) -> tuple[bool, str]:
    ok = response.endswith(suffix)
    return ok, f"does not end with {suffix!r}" if not ok else "ok"


REGISTRY = {
    "contains": contains,
    "not_contains": not_contains,
    "regex_match": regex_match,
    "format_match": format_match,
    "length_range": length_range,
    "json_valid": json_valid,
    "starts_with": starts_with,
    "ends_with": ends_with,
}
