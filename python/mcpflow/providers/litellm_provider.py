"""Optional LLM provider that delegates to LiteLLM for broad, native
provider coverage (Anthropic, Bedrock, Vertex, OpenAI, etc.) beyond what the
OpenAI-compatible wire format alone can express.

Requires the `litellm` package (`pip install mcpflow[llm]`). Imported lazily
so importing mcpflow.providers never requires it.
"""

import json
import logging
from typing import Any, List

from .base import LLMMessage, LLMResponse, LLMToolCall

logger = logging.getLogger(__name__)


class LiteLLMProvider:
    """LLMProvider backed by litellm.acompletion()."""

    def __init__(self, **default_kwargs: Any):
        """
        Args:
            **default_kwargs: Extra kwargs forwarded to every
                litellm.acompletion() call (e.g. api_key, api_base)
        """
        try:
            import litellm  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "LiteLLMProvider requires the 'litellm' package. "
                "Install it with: pip install mcpflow[llm]"
            ) from e

        self._default_kwargs = default_kwargs

    def _to_wire_message(self, message: LLMMessage) -> dict:
        """Convert a normalized LLMMessage into the OpenAI-shaped dict litellm expects."""
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
        """Call litellm.acompletion() and normalize the response."""
        import litellm

        kwargs = dict(self._default_kwargs)
        if tools:
            kwargs["tools"] = tools

        response = await litellm.acompletion(
            model=model,
            messages=[self._to_wire_message(m) for m in messages],
            **kwargs,
        )

        message = response.choices[0].message

        tool_calls = [
            LLMToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=json.loads(tc.function.arguments or "{}"),
            )
            for tc in (getattr(message, "tool_calls", None) or [])
        ]

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            raw=response,
        )
