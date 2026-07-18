"""Zero-extra-dependency LLM provider for any OpenAI-compatible chat completions API.

Works against OpenRouter, Ollama, Groq, Together, vLLM's OpenAI-compatible
server, LM Studio, and anything else speaking this wire format - configured
purely via `base_url`. Deliberately does not special-case Anthropic's native
API; use LiteLLMProvider when you need provider-native features.
"""

import json
import logging
from typing import List, Optional

import httpx

from .base import LLMMessage, LLMResponse, LLMToolCall

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider:
    """LLMProvider backed by any OpenAI-compatible /chat/completions endpoint."""

    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: float = 60.0):
        """
        Args:
            base_url: Base API URL, e.g. "https://openrouter.ai/api/v1" or
                "http://localhost:11434/v1" for Ollama
            api_key: Bearer token, if the endpoint requires one (Ollama and
                other local servers typically don't)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _to_wire_message(self, message: LLMMessage) -> dict:
        """Convert a normalized LLMMessage into the OpenAI wire format."""
        wire: dict = {"role": message.role}

        if message.content is not None:
            wire["content"] = message.content
        elif not message.tool_calls:
            wire["content"] = ""

        if message.tool_call_id:
            wire["tool_call_id"] = message.tool_call_id

        if message.tool_calls:
            wire["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in message.tool_calls
            ]

        return wire

    async def generate(
        self, messages: List[LLMMessage], tools: List[dict], model: str
    ) -> LLMResponse:
        """Call the /chat/completions endpoint and normalize the response."""
        payload = {
            "model": model,
            "messages": [self._to_wire_message(m) for m in messages],
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._headers(),
            )
            response.raise_for_status()
            data = response.json()

        message = data["choices"][0]["message"]

        tool_calls = [
            LLMToolCall(
                id=tc["id"],
                name=tc["function"]["name"],
                arguments=json.loads(tc["function"]["arguments"] or "{}"),
            )
            for tc in (message.get("tool_calls") or [])
        ]

        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            raw=data,
        )
