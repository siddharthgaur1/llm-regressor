from __future__ import annotations

import time

from .base import BaseProvider, CompletionResult


class LiteLLM(BaseProvider):
    """Catch-all provider: any model string LiteLLM understands (bedrock/, azure/, gemini/, ...)."""

    name = "litellm"

    def complete(self, prompt: str) -> CompletionResult:
        try:
            import litellm
        except ImportError as e:
            raise ImportError("pip install litellm to use providers.LiteLLM") from e

        start = time.perf_counter()
        try:
            messages = []
            if self.system_prompt:
                messages.append({"role": "system", "content": self.system_prompt})
            messages.append({"role": "user", "content": prompt})
            resp = litellm.completion(model=self.model, messages=messages, max_tokens=self.extra.get("max_tokens", 1024))
            latency_ms = (time.perf_counter() - start) * 1000
            text = resp.choices[0].message.content or ""
            cost = 0.0
            try:
                cost = litellm.completion_cost(completion_response=resp)
            except Exception:
                pass  # ponytail: not every model has cost data in litellm; 0.0 is an honest "unknown"
            usage = getattr(resp, "usage", None)
            return CompletionResult(
                response=text,
                latency_ms=latency_ms,
                input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                cost=cost or 0.0,
            )
        except Exception as e:
            return CompletionResult(response="", latency_ms=(time.perf_counter() - start) * 1000, error=str(e))
