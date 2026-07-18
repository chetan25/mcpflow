"""Provider-agnostic LLM interface used by ChatManager.

`ChatManager` never talks to a specific LLM SDK directly - it only depends
on the `LLMProvider` protocol below. Anyone can implement it for any model
backend (a provider we've never heard of, a local server, a test double)
without mcpflow maintaining a fixed list of supported providers.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Protocol, runtime_checkable


@dataclass
class LLMToolCall:
    """A tool call the model requested."""

    id: str
    name: str
    arguments: dict


@dataclass
class LLMMessage:
    """A single message in the conversation sent to/from the provider."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: Optional[str] = None
    tool_call_id: Optional[str] = None  # set on role="tool" messages
    tool_calls: List[LLMToolCall] = field(default_factory=list)  # set on role="assistant"


@dataclass
class LLMResponse:
    """What a provider returns for one generation turn."""

    content: Optional[str]
    tool_calls: List[LLMToolCall] = field(default_factory=list)
    raw: Any = None  # provider's raw response, for debugging


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol every LLM backend implements to work with ChatManager."""

    async def generate(
        self, messages: List[LLMMessage], tools: List[dict], model: str
    ) -> LLMResponse:
        """
        Generate the next assistant turn.

        Args:
            messages: Full conversation so far, including the system prompt
            tools: Available tools in OpenAI function-calling JSON shape:
                {"type": "function", "function": {"name", "description", "parameters"}}
            model: Model identifier to request (provider-specific string)

        Returns:
            LLMResponse with either text content, tool calls, or both
        """
        ...
