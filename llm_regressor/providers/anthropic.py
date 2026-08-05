from __future__ import annotations

import time

from .base import BaseProvider, CompletionResult

# USD per 1M tokens (input, output). Approximate published pricing; update as Anthropic changes it.
_PRICING = {
    "claude-opus-5": (15.0, 75.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (0.8, 4.0),
    "claude-fable-5": (3.0, 15.0),
}


def _price_for(model: str) -> tuple[float, float]:
    for key, price in _PRICING.items():
        if model.startswith(key):
            return price
    return (3.0, 15.0)  # ponytail: unknown model, assume Sonnet-tier pricing


class Anthropic(BaseProvider):
    name = "anthropic"

    def __init__(self, model: str, system_prompt: str | None = None, api_key: str | None = None, **kwargs):
        super().__init__(model, system_prompt, **kwargs)
        try:
            import anthropic
        except ImportError as e:
            raise ImportError("pip install anthropic to use providers.Anthropic") from e
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    def complete(self, prompt: str) -> CompletionResult:
        start = time.perf_counter()
        try:
            kwargs = dict(
                model=self.model,
                max_tokens=self.extra.get("max_tokens", 1024),
                messages=[{"role": "user", "content": prompt}],
            )
            if self.system_prompt:
                kwargs["system"] = self.system_prompt
            resp = self._client.messages.create(**kwargs)
            latency_ms = (time.perf_counter() - start) * 1000
            text = "".join(block.text for block in resp.content if getattr(block, "type", None) == "text")
            in_price, out_price = _price_for(self.model)
            cost = (resp.usage.input_tokens / 1_000_000) * in_price + (resp.usage.output_tokens / 1_000_000) * out_price
            return CompletionResult(
                response=text,
                latency_ms=latency_ms,
                input_tokens=resp.usage.input_tokens,
                output_tokens=resp.usage.output_tokens,
                cost=cost,
            )
        except Exception as e:
            return CompletionResult(response="", latency_ms=(time.perf_counter() - start) * 1000, error=str(e))
