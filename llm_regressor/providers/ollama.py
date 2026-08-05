from __future__ import annotations

import time

from .base import BaseProvider, CompletionResult


class Ollama(BaseProvider):
    """Local models via the Ollama REST API. Free to run, so cost is always 0."""

    name = "ollama"

    def __init__(self, model: str, system_prompt: str | None = None, host: str = "http://localhost:11434", **kwargs):
        super().__init__(model, system_prompt, **kwargs)
        self.host = host.rstrip("/")

    def complete(self, prompt: str) -> CompletionResult:
        import requests

        start = time.perf_counter()
        try:
            full_prompt = f"{self.system_prompt}\n\n{prompt}" if self.system_prompt else prompt
            resp = requests.post(
                f"{self.host}/api/generate",
                json={"model": self.model, "prompt": full_prompt, "stream": False},
                timeout=self.extra.get("timeout", 120),
            )
            resp.raise_for_status()
            data = resp.json()
            latency_ms = (time.perf_counter() - start) * 1000
            return CompletionResult(
                response=data.get("response", ""),
                latency_ms=latency_ms,
                input_tokens=data.get("prompt_eval_count", 0),
                output_tokens=data.get("eval_count", 0),
                cost=0.0,
            )
        except Exception as e:
            return CompletionResult(response="", latency_ms=(time.perf_counter() - start) * 1000, error=str(e))
