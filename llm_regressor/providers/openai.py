from __future__ import annotations

import time
from typing import Optional

from .base import BaseProvider, CompletionResult

_PRICING = {
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4o": (2.5, 10.0),
    "gpt-4.1": (2.0, 8.0),
    "o1": (15.0, 60.0),
}


def _price_for(model: str) -> tuple[float, float]:
    for key, price in _PRICING.items():
        if model.startswith(key):
            return price
    return (2.5, 10.0)  # ponytail: unknown model, assume gpt-4o-tier pricing


class OpenAI(BaseProvider):
    """Also works for any OpenAI-compatible endpoint via base_url=."""

    name = "openai"

    def __init__(self, model: str, system_prompt: Optional[str] = None, api_key: Optional[str] = None,
                 base_url: Optional[str] = None, **kwargs):
        super().__init__(model, system_prompt, **kwargs)
        try:
            import openai
        except ImportError as e:
            raise ImportError("pip install openai to use providers.OpenAI") from e
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)

    def complete(self, prompt: str) -> CompletionResult:
        start = time.perf_counter()
        try:
            messages = []
            if self.system_prompt:
                messages.append({"role": "system", "content": self.system_prompt})
            messages.append({"role": "user", "content": prompt})
            resp = self._client.chat.completions.create(
                model=self.model, messages=messages, max_tokens=self.extra.get("max_tokens", 1024)
            )
            latency_ms = (time.perf_counter() - start) * 1000
            text = resp.choices[0].message.content or ""
            in_price, out_price = _price_for(self.model)
            usage = resp.usage
            cost = (usage.prompt_tokens / 1_000_000) * in_price + (usage.completion_tokens / 1_000_000) * out_price
            return CompletionResult(
                response=text,
                latency_ms=latency_ms,
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
                cost=cost,
            )
        except Exception as e:
            return CompletionResult(response="", latency_ms=(time.perf_counter() - start) * 1000, error=str(e))
