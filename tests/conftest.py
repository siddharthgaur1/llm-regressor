"""Shared fakes.

FakeProvider is the workhorse: it lets every test drive the Regressor without a
network call, which is the whole reason the BaseProvider seam exists.
"""
from __future__ import annotations

import sys
import types

import pytest

from llm_regressor.checks import llm_judge
from llm_regressor.providers.base import BaseProvider, CompletionResult


class FakeProvider(BaseProvider):
    """Returns canned responses in order, cycling on the last one."""

    name = "fake"

    def __init__(self, *responses: str, model: str = "fake-model", latency_ms: float = 10.0, cost: float = 0.0):
        super().__init__(model=model)
        self.responses = list(responses) or [""]
        self.latency_ms = latency_ms
        self.cost = cost
        self.calls: list[str] = []

    def complete(self, prompt: str) -> CompletionResult:
        self.calls.append(prompt)
        idx = min(len(self.calls) - 1, len(self.responses) - 1)
        return CompletionResult(
            response=self.responses[idx],
            latency_ms=self.latency_ms,
            input_tokens=5,
            output_tokens=5,
            cost=self.cost,
        )


class ErrorProvider(BaseProvider):
    name = "error"

    def __init__(self, message: str = "boom"):
        super().__init__(model="error-model")
        self.message = message

    def complete(self, prompt: str) -> CompletionResult:
        return CompletionResult(response="", latency_ms=1.0, error=self.message)


@pytest.fixture(autouse=True)
def _clear_embedder_cache():
    """The embedder is a module-level singleton; leaking it across tests would
    make results depend on execution order."""
    llm_judge._embedder_cache.clear()
    yield
    llm_judge._embedder_cache.clear()


@pytest.fixture
def no_embeddings(monkeypatch):
    """Force the lexical fallback.

    Without this, every embedding-touching test silently changes behaviour and
    downloads a ~90MB model depending on whether sentence-transformers happens
    to be installed. Both branches are real code paths, so both get pinned
    explicitly instead of left to the environment.
    """
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)


@pytest.fixture
def fake_embeddings(monkeypatch):
    """Force the embedding path, with a stub model that returns a fixed score."""
    state = types.SimpleNamespace(constructed=0, encoded=[])

    class _Model:
        def __init__(self, name):
            state.constructed += 1
            state.name = name

        def encode(self, texts):
            state.encoded.append(list(texts))
            return list(texts)

    fake = types.ModuleType("sentence_transformers")
    fake.SentenceTransformer = _Model
    fake.util = types.SimpleNamespace(cos_sim=lambda a, b: [[0.42]])
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)
    return state


@pytest.fixture
def suite_yaml(tmp_path):
    """A minimal on-disk suite the CLI can load."""
    path = tmp_path / "suite.yaml"
    path.write_text(
        "tests:\n"
        "  - id: t1\n"
        '    input: "capital of France?"\n'
        "    checks:\n"
        "      - type: contains\n"
        '        value: "Paris"\n'
    )
    return path
