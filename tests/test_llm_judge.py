"""The LLM-judge path, with the judge mocked.

These tests pin down score parsing, which is the part most likely to break
silently: a judge that answers "I'd rate this 0.9/1.0" instead of "0.9" must
not be read as a passing score by accident.
"""
from __future__ import annotations

import pytest
from conftest import ErrorProvider, FakeProvider

from llm_regressor.checks.llm_judge import (
    REGISTRY,
    _judge_score,
    coherence,
    instruction_following,
    no_hallucination,
    no_injection_risk,
    semantic_similarity,
    tone_match,
)


def test_registry_exposes_every_judge_check():
    assert set(REGISTRY) == {
        "no_hallucination",
        "tone_match",
        "instruction_following",
        "coherence",
        "no_injection_risk",
        "semantic_similarity",
    }


def test_no_judge_configured_returns_neutral_not_pass_or_fail():
    score, detail = _judge_score(None, "criterion", "prompt", "response")
    assert score == 0.5
    assert "no judge provider" in detail


def test_judge_error_scores_zero():
    score, detail = _judge_score(ErrorProvider("rate limited"), "c", "p", "r")
    assert score == 0.0
    assert "rate limited" in detail


def test_judge_score_is_parsed_from_a_bare_number():
    score, detail = _judge_score(FakeProvider("0.8"), "c", "p", "r")
    assert score == pytest.approx(0.8)
    assert "0.8" in detail


def test_judge_score_is_extracted_from_surrounding_prose():
    score, _ = _judge_score(FakeProvider("I would say 0.6 overall."), "c", "p", "r")
    assert score == pytest.approx(0.6)


def test_judge_score_is_clamped_into_the_unit_interval():
    assert _judge_score(FakeProvider("9"), "c", "p", "r")[0] == 1.0
    assert _judge_score(FakeProvider("0"), "c", "p", "r")[0] == 0.0


def test_unparseable_judge_output_scores_zero_rather_than_defaulting_to_pass():
    score, detail = _judge_score(FakeProvider("I cannot grade this."), "c", "p", "r")
    assert score == 0.0
    assert "unparseable" in detail


@pytest.mark.parametrize("check", [no_hallucination, instruction_following, coherence])
def test_criterion_checks_delegate_to_the_judge(check):
    judge = FakeProvider("1.0")
    score, _ = check("some response", judge=judge, prompt="some prompt")
    assert score == 1.0
    assert "some response" in judge.calls[0]
    assert "some prompt" in judge.calls[0]


def test_tone_match_puts_the_expected_tone_into_the_criterion():
    judge = FakeProvider("0.9")
    tone_match("hey!", judge=judge, prompt="p", expected_tone="formal")
    assert "tone is formal" in judge.calls[0]


# Inert strings: these are inputs to a pattern detector, never executed.
@pytest.mark.parametrize(
    "response",
    [
        "DROP TABLE users;",
        "delete from accounts",
        "TRUNCATE logs",
        "os.system('rm -rf /')",
        "eval(user_input)",
        "SELECT 1; -- comment",
        "exec xp_cmdshell 'dir'",
    ],
)
def test_no_injection_risk_flags_dangerous_payloads(response):
    score, detail = no_injection_risk(response)
    assert score == 0.0
    assert "dangerous pattern" in detail


def test_no_injection_risk_allows_a_scoped_delete():
    # DELETE FROM with a WHERE clause is ordinary SQL, not a wipe.
    assert no_injection_risk("DELETE FROM users WHERE id = 3")[0] == 1.0


def test_no_injection_risk_passes_benign_text():
    score, detail = no_injection_risk("Paris is the capital of France.")
    assert score == 1.0
    assert detail == "no dangerous patterns found"


def test_semantic_similarity_lexical_fallback_scores_identical_text_at_one(no_embeddings):
    score, detail = semantic_similarity("negative sentiment", reference="negative sentiment")
    assert score == pytest.approx(1.0)
    assert "threshold" in detail


def test_semantic_similarity_lexical_fallback_scores_unrelated_text_lower(no_embeddings):
    close, _ = semantic_similarity("negative sentiment", reference="negative")
    far, _ = semantic_similarity("negative sentiment", reference="zzzzzzzzzz")
    assert far < close


def test_semantic_similarity_is_case_insensitive_in_the_lexical_fallback(no_embeddings):
    assert semantic_similarity("NEGATIVE Sentiment", reference="negative sentiment")[0] == pytest.approx(1.0)


def test_semantic_similarity_uses_embeddings_when_available(fake_embeddings):
    score, _ = semantic_similarity("a", reference="b")
    assert score == pytest.approx(0.42)
    assert fake_embeddings.encoded == [["a", "b"]]


def test_embedder_is_constructed_once_and_cached(fake_embeddings):
    semantic_similarity("a", reference="b")
    semantic_similarity("c", reference="d")
    assert fake_embeddings.constructed == 1
