"""Tests for LLM provider adapters."""

import json

import httpx
import pytest

from mcpflow.providers import (
    LLMMessage,
    LLMToolCall,
    OpenAICompatibleProvider,
    build_provider_from_config,
)


class _FakeModelConfig:
    """Duck-typed stand-in for mcpflow.config.ModelConfig."""

    def __init__(self, provider="openrouter", base_url=None, api_key=None):
        self.provider = provider
        self.base_url = base_url
        self.api_key = api_key


def _fake_post(payload: dict):
    """Monkeypatch target for httpx.AsyncClient.post returning a canned response."""

    async def handler(self, url, json=None, headers=None):
        return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

    return handler


class TestOpenAICompatibleProvider:
    @pytest.mark.asyncio
    async def test_plain_text_response(self, monkeypatch):
        payload = {
            "choices": [
                {"message": {"role": "assistant", "content": "Hello there", "tool_calls": None}}
            ]
        }
        monkeypatch.setattr(httpx.AsyncClient, "post", _fake_post(payload))

        provider = OpenAICompatibleProvider(base_url="https://openrouter.ai/api/v1", api_key="sk-test")
        response = await provider.generate(
            messages=[LLMMessage(role="user", content="Hi")], tools=[], model="test-model"
        )

        assert response.content == "Hello there"
        assert response.tool_calls == []

    @pytest.mark.asyncio
    async def test_tool_call_response(self, monkeypatch):
        payload = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {
                                    "name": "calc__add",
                                    "arguments": json.dumps({"a": 2, "b": 3}),
                                },
                            }
                        ],
                    }
                }
            ]
        }
        monkeypatch.setattr(httpx.AsyncClient, "post", _fake_post(payload))

        provider = OpenAICompatibleProvider(base_url="http://localhost:11434/v1")
        response = await provider.generate(
            messages=[LLMMessage(role="user", content="What is 2+3?")],
            tools=[{"type": "function", "function": {"name": "calc__add"}}],
            model="llama3",
        )

        assert response.content is None
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0] == LLMToolCall(
            id="call-1", name="calc__add", arguments={"a": 2, "b": 3}
        )

    @pytest.mark.asyncio
    async def test_sends_correct_payload_shape(self, monkeypatch):
        captured = {}

        async def capturing_post(self, url, json=None, headers=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            payload = {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
            return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx.AsyncClient, "post", capturing_post)

        provider = OpenAICompatibleProvider(base_url="https://openrouter.ai/api/v1/", api_key="sk-test")

        tool_call_msg = LLMMessage(
            role="assistant",
            content=None,
            tool_calls=[LLMToolCall(id="call-1", name="calc__add", arguments={"a": 1})],
        )
        tool_result_msg = LLMMessage(role="tool", content='{"sum": 1}', tool_call_id="call-1")

        await provider.generate(
            messages=[LLMMessage(role="user", content="hi"), tool_call_msg, tool_result_msg],
            tools=[],
            model="gpt-4o",
        )

        assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
        assert captured["headers"]["Authorization"] == "Bearer sk-test"
        assert captured["json"]["model"] == "gpt-4o"

        sent_messages = captured["json"]["messages"]
        assert sent_messages[1]["tool_calls"][0]["function"]["arguments"] == json.dumps({"a": 1})
        assert sent_messages[2]["tool_call_id"] == "call-1"


class TestBuildProviderFromConfig:
    def test_defaults_to_openai_compatible(self):
        config = _FakeModelConfig(provider="openrouter", base_url="https://openrouter.ai/api/v1", api_key="k")
        provider = build_provider_from_config(config)

        assert isinstance(provider, OpenAICompatibleProvider)
        assert provider.base_url == "https://openrouter.ai/api/v1"
        assert provider.api_key == "k"

    def test_raises_without_base_url(self):
        config = _FakeModelConfig(provider="openrouter", base_url=None)
        with pytest.raises(ValueError, match="base_url"):
            build_provider_from_config(config)

    def test_litellm_provider_selected_by_name(self):
        litellm = pytest.importorskip("litellm")
        from mcpflow.providers import LiteLLMProvider

        config = _FakeModelConfig(provider="litellm")
        provider = build_provider_from_config(config)

        assert isinstance(provider, LiteLLMProvider)


class TestLiteLLMProvider:
    def test_raises_clear_error_when_litellm_missing(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "litellm":
                raise ImportError("simulated: litellm not installed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        from mcpflow.providers import LiteLLMProvider

        with pytest.raises(ImportError, match=r"pip install mcpflow\[llm\]"):
            LiteLLMProvider()

    @pytest.mark.asyncio
    async def test_generate_parses_litellm_response(self, monkeypatch):
        litellm = pytest.importorskip("litellm")
        from unittest.mock import MagicMock

        from mcpflow.providers import LiteLLMProvider

        fake_message = MagicMock()
        fake_message.content = "Hello!"
        fake_message.tool_calls = None
        fake_response = MagicMock()
        fake_response.choices = [MagicMock(message=fake_message)]

        async def fake_acompletion(**kwargs):
            return fake_response

        monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

        provider = LiteLLMProvider()
        result = await provider.generate(
            messages=[LLMMessage(role="user", content="hi")], tools=[], model="gpt-4o"
        )

        assert result.content == "Hello!"
        assert result.tool_calls == []
