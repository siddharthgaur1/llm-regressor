"""Provider adapters, with each vendor SDK faked at the sys.modules level.

The point of these tests is the translation layer, not the vendors: token
accounting, cost arithmetic, and the promise that a provider never raises —
it returns a CompletionResult carrying .error. Regressor depends on that
promise, so one flaky API call cannot abort a whole suite run.
"""
from __future__ import annotations

import sys
import types

import pytest

from llm_regressor.providers import Anthropic, LiteLLM, Ollama, OpenAI
from llm_regressor.providers.anthropic import _price_for as anthropic_price
from llm_regressor.providers.base import BaseProvider, CompletionResult
from llm_regressor.providers.openai import _price_for as openai_price


def _fake_module(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


@pytest.fixture
def fake_sdk(monkeypatch):
    """Install a fake vendor module under `name` for the duration of a test."""

    def install(name, **attrs):
        monkeypatch.setitem(sys.modules, name, _fake_module(name, **attrs))

    return install


@pytest.fixture
def missing_sdk(monkeypatch):
    """Make `import <name>` raise ImportError, as it would on a bare install."""

    def install(name):
        monkeypatch.setitem(sys.modules, name, None)

    return install


# --- base -------------------------------------------------------------------


def test_base_provider_complete_is_abstract():
    with pytest.raises(NotImplementedError):
        BaseProvider(model="m").complete("hi")


def test_label_identifies_provider_and_model():
    assert Ollama(model="llama3").label() == "ollama:llama3"


def test_extra_kwargs_are_retained_for_subclasses():
    assert Ollama(model="llama3", max_tokens=99).extra["max_tokens"] == 99


# --- pricing tables ---------------------------------------------------------


def test_anthropic_pricing_matches_on_model_prefix():
    assert anthropic_price("claude-haiku-4-5-20251001") == (0.8, 4.0)
    assert anthropic_price("claude-opus-5") == (15.0, 75.0)


def test_anthropic_unknown_model_falls_back_to_sonnet_tier():
    assert anthropic_price("claude-something-unreleased") == (3.0, 15.0)


def test_openai_pricing_matches_on_model_prefix():
    assert openai_price("gpt-4o-mini") == (0.15, 0.6)
    assert openai_price("gpt-4o-2024-11-20") == (2.5, 10.0)


def test_openai_unknown_model_falls_back_to_gpt4o_tier():
    assert openai_price("some-new-model") == (2.5, 10.0)


# --- anthropic --------------------------------------------------------------


class _Block:
    def __init__(self, text, type="text"):
        self.text = text
        self.type = type


def _anthropic_client(response_blocks, recorder):
    class Messages:
        def create(self, **kwargs):
            recorder.append(kwargs)
            return types.SimpleNamespace(
                content=response_blocks,
                usage=types.SimpleNamespace(input_tokens=1000, output_tokens=2000),
            )

    class Client:
        messages = Messages()

    return Client


def test_anthropic_missing_sdk_raises_actionable_import_error(missing_sdk):
    missing_sdk("anthropic")
    with pytest.raises(ImportError, match="pip install anthropic"):
        Anthropic(model="claude-sonnet-5")


def test_anthropic_completes_and_prices_the_call(fake_sdk):
    calls = []
    client = _anthropic_client([_Block("Paris")], calls)
    fake_sdk("anthropic", Anthropic=lambda **kw: client())

    result = Anthropic(model="claude-sonnet-5", api_key="k").complete("capital of France?")

    assert result.response == "Paris"
    assert (result.input_tokens, result.output_tokens) == (1000, 2000)
    # 1000 in @ $3/M + 2000 out @ $15/M
    assert result.cost == pytest.approx(0.003 + 0.030)
    assert result.error is None


def test_anthropic_concatenates_text_blocks_and_drops_non_text(fake_sdk):
    client = _anthropic_client([_Block("Par"), _Block("<thinking>", type="thinking"), _Block("is")], [])
    fake_sdk("anthropic", Anthropic=lambda **kw: client())
    assert Anthropic(model="claude-sonnet-5").complete("q").response == "Paris"


def test_anthropic_sends_system_prompt_only_when_set(fake_sdk):
    calls = []
    client = _anthropic_client([_Block("ok")], calls)
    fake_sdk("anthropic", Anthropic=lambda **kw: client())

    Anthropic(model="claude-sonnet-5").complete("q")
    assert "system" not in calls[0]

    Anthropic(model="claude-sonnet-5", system_prompt="be terse").complete("q")
    assert calls[1]["system"] == "be terse"


def test_anthropic_api_failure_becomes_a_result_not_an_exception(fake_sdk):
    class Boom:
        class messages:
            @staticmethod
            def create(**kwargs):
                raise RuntimeError("529 overloaded")

    fake_sdk("anthropic", Anthropic=lambda **kw: Boom())
    result = Anthropic(model="claude-sonnet-5").complete("q")
    assert result.response == ""
    assert "529 overloaded" in result.error
    assert result.latency_ms > 0


# --- openai -----------------------------------------------------------------


def _openai_client(content, recorder, usage=(1000, 2000)):
    class Completions:
        def create(self, **kwargs):
            recorder.append(kwargs)
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))],
                usage=types.SimpleNamespace(prompt_tokens=usage[0], completion_tokens=usage[1]),
            )

    class Chat:
        completions = Completions()

    class Client:
        chat = Chat()

    return Client


def test_openai_missing_sdk_raises_actionable_import_error(missing_sdk):
    missing_sdk("openai")
    with pytest.raises(ImportError, match="pip install openai"):
        OpenAI(model="gpt-4o-mini")


def test_openai_completes_and_prices_the_call(fake_sdk):
    calls = []
    client = _openai_client("Paris", calls)
    fake_sdk("openai", OpenAI=lambda **kw: client())

    result = OpenAI(model="gpt-4o-mini").complete("capital of France?")

    assert result.response == "Paris"
    # 1000 in @ $0.15/M + 2000 out @ $0.60/M
    assert result.cost == pytest.approx(0.00015 + 0.0012)
    assert calls[0]["messages"] == [{"role": "user", "content": "capital of France?"}]


def test_openai_prepends_system_prompt_as_a_message(fake_sdk):
    calls = []
    client = _openai_client("ok", calls)
    fake_sdk("openai", OpenAI=lambda **kw: client())
    OpenAI(model="gpt-4o", system_prompt="be terse").complete("q")
    assert calls[0]["messages"][0] == {"role": "system", "content": "be terse"}


def test_openai_null_content_becomes_empty_string(fake_sdk):
    client = _openai_client(None, [])
    fake_sdk("openai", OpenAI=lambda **kw: client())
    assert OpenAI(model="gpt-4o").complete("q").response == ""


def test_openai_api_failure_becomes_a_result_not_an_exception(fake_sdk):
    class Boom:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    raise RuntimeError("rate limit")

    fake_sdk("openai", OpenAI=lambda **kw: Boom())
    result = OpenAI(model="gpt-4o").complete("q")
    assert result.response == ""
    assert "rate limit" in result.error


# --- litellm ----------------------------------------------------------------


def _litellm_response(content="Paris", prompt_tokens=10, completion_tokens=20):
    return types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))],
        usage=types.SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


def test_litellm_missing_sdk_raises_actionable_import_error(missing_sdk):
    missing_sdk("litellm")
    with pytest.raises(ImportError, match="pip install litellm"):
        LiteLLM(model="bedrock/claude").complete("q")


def test_litellm_completes_and_reports_cost(fake_sdk):
    calls = []
    fake_sdk(
        "litellm",
        completion=lambda **kw: (calls.append(kw), _litellm_response())[1],
        completion_cost=lambda completion_response: 0.0042,
    )
    result = LiteLLM(model="gemini/gemini-1.5-pro", system_prompt="be terse").complete("q")
    assert result.response == "Paris"
    assert result.cost == pytest.approx(0.0042)
    assert result.input_tokens == 10
    assert calls[0]["messages"][0]["role"] == "system"


def test_litellm_reports_zero_cost_when_pricing_is_unknown(fake_sdk):
    def no_price(completion_response):
        raise ValueError("model not in cost map")

    fake_sdk("litellm", completion=lambda **kw: _litellm_response(), completion_cost=no_price)
    # 0.0 here means "unknown", not "free" — documented in the provider.
    assert LiteLLM(model="custom/model").complete("q").cost == 0.0


def test_litellm_tolerates_a_response_without_usage(fake_sdk):
    resp = types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="hi"))])
    fake_sdk("litellm", completion=lambda **kw: resp, completion_cost=lambda completion_response: 0.0)
    result = LiteLLM(model="custom/model").complete("q")
    assert (result.input_tokens, result.output_tokens) == (0, 0)


def test_litellm_api_failure_becomes_a_result_not_an_exception(fake_sdk):
    def boom(**kwargs):
        raise RuntimeError("provider down")

    fake_sdk("litellm", completion=boom, completion_cost=lambda **kw: 0.0)
    assert "provider down" in LiteLLM(model="x/y").complete("q").error


# --- ollama -----------------------------------------------------------------


def test_ollama_strips_trailing_slash_from_host():
    assert Ollama(model="llama3", host="http://box:11434/").host == "http://box:11434"


def test_ollama_completes_and_is_always_free(fake_sdk):
    calls = []

    class Resp:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"response": "Paris", "prompt_eval_count": 7, "eval_count": 3}

    fake_sdk("requests", post=lambda url, json, timeout: (calls.append((url, json)), Resp)[1])
    result = Ollama(model="llama3", system_prompt="be terse").complete("q")

    assert result.response == "Paris"
    assert result.cost == 0.0
    assert (result.input_tokens, result.output_tokens) == (7, 3)
    url, payload = calls[0]
    assert url == "http://localhost:11434/api/generate"
    assert payload["prompt"] == "be terse\n\nq"
    assert payload["stream"] is False


def test_ollama_connection_failure_becomes_a_result_not_an_exception(fake_sdk):
    def boom(url, json, timeout):
        raise OSError("connection refused")

    fake_sdk("requests", post=boom)
    result = Ollama(model="llama3").complete("q")
    assert result.response == ""
    assert "connection refused" in result.error


def test_completion_result_defaults_are_zero_and_error_free():
    r = CompletionResult(response="x", latency_ms=1.0)
    assert (r.input_tokens, r.output_tokens, r.cost, r.error) == (0, 0, 0.0, None)
