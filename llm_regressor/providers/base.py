"""Provider abstraction: every provider implements .complete(prompt) -> CompletionResult."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CompletionResult:
    response: str
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    error: str | None = None


class BaseProvider:
    """Subclass and implement complete(). model/system_prompt are stored for display in reports."""

    name: str = "base"

    def __init__(self, model: str, system_prompt: str | None = None, **kwargs):
        self.model = model
        self.system_prompt = system_prompt
        self.extra = kwargs

    def complete(self, prompt: str) -> CompletionResult:
        raise NotImplementedError

    def label(self) -> str:
        return f"{self.name}:{self.model}"
