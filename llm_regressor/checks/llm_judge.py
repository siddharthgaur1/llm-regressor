"""LLM-as-judge and embedding-based checks.

Each function takes (response: str, judge: BaseProvider | None, **params) and returns
(score: float in [0, 1], detail: str). A score >= threshold (default 0.7) counts as passed;
the caller (Regressor) applies the threshold so it can also compare against the baseline score.
"""
from __future__ import annotations

import difflib
import re

_JUDGE_PROMPT = """You are grading an AI assistant's response. Answer with ONLY a number from 0 to 1 \
(one decimal place), where 1 means fully satisfies the criterion and 0 means fails it completely.

Criterion: {criterion}

User prompt:
{prompt}

Assistant response:
{response}

Score (number only):"""


def _judge_score(judge, criterion: str, prompt: str, response: str) -> tuple[float, str]:
    if judge is None:
        return 0.5, "no judge provider configured, score is a neutral default"
    result = judge.complete(_JUDGE_PROMPT.format(criterion=criterion, prompt=prompt, response=response))
    if result.error:
        return 0.0, f"judge call failed: {result.error}"
    match = re.search(r"(\d*\.?\d+)", result.response)
    if not match:
        return 0.0, f"judge returned unparseable score: {result.response!r}"
    score = max(0.0, min(1.0, float(match.group(1))))
    return score, f"judge score {score}"


def no_hallucination(response: str, judge=None, prompt: str = "", **_) -> tuple[float, str]:
    return _judge_score(judge, "The response contains no factual hallucinations or fabricated details.", prompt, response)


def tone_match(response: str, judge=None, prompt: str = "", expected_tone: str = "professional", **_) -> tuple[float, str]:
    return _judge_score(judge, f"The response's tone is {expected_tone}.", prompt, response)


def instruction_following(response: str, judge=None, prompt: str = "", **_) -> tuple[float, str]:
    return _judge_score(judge, "The response follows every instruction given in the user prompt.", prompt, response)


def coherence(response: str, judge=None, prompt: str = "", **_) -> tuple[float, str]:
    return _judge_score(judge, "The response is logically coherent and internally consistent.", prompt, response)


_DANGEROUS_PATTERNS = [
    r"\bDROP\s+TABLE\b", r"\bDELETE\s+FROM\b(?!.*WHERE)", r"\bTRUNCATE\b",
    r"\bexec\s*\(", r"\beval\s*\(", r"\bos\.system\s*\(", r"\bsubprocess\.",
    r";\s*--", r"\bxp_cmdshell\b",
]


def no_injection_risk(response: str, judge=None, prompt: str = "", **_) -> tuple[float, str]:
    for pattern in _DANGEROUS_PATTERNS:
        if re.search(pattern, response, re.IGNORECASE):
            return 0.0, f"matched dangerous pattern /{pattern}/"
    return 1.0, "no dangerous patterns found"


def semantic_similarity(response: str, reference: str, judge=None, threshold: float = 0.8, **_) -> tuple[float, str]:
    try:
        from sentence_transformers import SentenceTransformer, util
        model = _get_embedder()
        emb = model.encode([response, reference])
        score = float(util.cos_sim(emb[0], emb[1])[0][0])
    except ImportError:
        # ponytail: sentence-transformers not installed, fall back to lexical similarity
        score = difflib.SequenceMatcher(None, response.lower(), reference.lower()).ratio()
    return score, f"similarity {score:.3f} vs threshold {threshold}"


_embedder_cache = {}


def _get_embedder():
    if "model" not in _embedder_cache:
        from sentence_transformers import SentenceTransformer
        _embedder_cache["model"] = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder_cache["model"]


REGISTRY = {
    "no_hallucination": no_hallucination,
    "tone_match": tone_match,
    "instruction_following": instruction_following,
    "coherence": coherence,
    "no_injection_risk": no_injection_risk,
    "semantic_similarity": semantic_similarity,
}
