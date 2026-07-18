"""Chat management and orchestration."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .providers import LLMMessage, LLMProvider
from .registry import MCPRegistry
from .tracing import get_tracer


@dataclass
class ToolCall:
    """Represents a tool call within a message."""

    tool_name: str
    mcp_name: str
    inputs: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class Message:
    """Represents a message in a conversation."""

    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tool_calls: List[ToolCall] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "tool_calls": [
                {
                    "tool_name": tc.tool_name,
                    "mcp_name": tc.mcp_name,
                    "inputs": tc.inputs,
                    "result": tc.result,
                    "error": tc.error,
                }
                for tc in self.tool_calls
            ],
        }


class ChatManager:
    """Manages chat sessions and message flow with tool execution."""

    # Default system prompt
    _DEFAULT_SYSTEM_PROMPT = (
        "You are a helpful assistant with access to various tools and services. "
        "Use the available tools to help the user accomplish their goals. "
        "Always explain your actions and the results."
    )

    def __init__(
        self,
        model: Optional[str] = None,
        registry: Optional[MCPRegistry] = None,
        system_prompt: Optional[str] = None,
        max_tool_calls: int = 10,
        provider: Optional[LLMProvider] = None,
    ):
        """Initialize chat manager.

        Args:
            model: Model identifier passed to the provider (e.g. "gpt-4o",
                "openrouter/anthropic/claude-3.5-sonnet")
            registry: MCPRegistry instance for tool execution
            system_prompt: System prompt for the chat
            max_tool_calls: Maximum number of tool-call round-trips per message
            provider: LLMProvider implementation to use. If not given, it's
                resolved lazily on first use: LiteLLMProvider if `litellm` is
                installed, otherwise send() raises a clear error asking for
                one explicitly.
        """
        self.model = model
        self.registry = registry
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.max_tool_calls = max_tool_calls
        self.provider = provider
        self.history: List[Message] = []
        self._tracer = get_tracer()

    @staticmethod
    def _default_system_prompt() -> str:
        """Get the default system prompt.

        Returns:
            Default system prompt string
        """
        return ChatManager._DEFAULT_SYSTEM_PROMPT

    async def send(
        self,
        message: str,
        model_override: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Send a message to the chat and get a response.

        Args:
            message: User message
            model_override: Override model for this request
            context: Additional context for the request (currently unused;
                reserved for future prompt-augmentation use cases)

        Returns:
            Assistant response

        Raises:
            ValueError: If no model configured and no override provided
            RuntimeError: If no provider was given and none can be resolved
        """
        model = model_override or self.model

        with self._tracer.start_span("chat_send", {"model": model}):
            if not model:
                raise ValueError("No model configured. Provide model or override.")

            user_msg = Message(role="user", content=message)
            self.history.append(user_msg)

            provider = self.provider or self._resolve_default_provider()
            response_text, executed_tool_calls = await self._run_tool_calling_loop(provider, model)

            assistant_msg = Message(
                role="assistant", content=response_text, tool_calls=executed_tool_calls
            )
            self.history.append(assistant_msg)

            return response_text

    def _resolve_default_provider(self) -> LLMProvider:
        """Lazily resolve a default provider when none was passed explicitly."""
        try:
            from .providers import LiteLLMProvider

            return LiteLLMProvider()
        except ImportError as e:
            raise RuntimeError(
                "No provider configured and litellm isn't installed. "
                "Pass provider=... to ChatManager, or run: pip install mcpflow[llm]"
            ) from e

    def _build_llm_messages(self) -> List[LLMMessage]:
        """Convert the system prompt + this manager's history into the
        provider-facing message list. This is a separate representation from
        Message/ToolCall, which exist for the user-facing conversation log."""
        llm_messages = [LLMMessage(role="system", content=self.system_prompt)]
        for msg in self.history:
            llm_messages.append(LLMMessage(role=msg.role, content=msg.content))
        return llm_messages

    async def _tools_to_llm_schema(self) -> List[dict]:
        """Convert every registered MCP's tools into OpenAI function-calling
        schema, namespaced as {mcp_name}__{tool_name} since the LLM sees one
        flat namespace across every registered MCP server."""
        if not self.registry:
            return []

        schemas = []
        for mcp_name in self.registry.get_registered_mcps():
            for tool_def in self.registry.get_tools(mcp_name):
                schemas.append(
                    {
                        "type": "function",
                        "function": {
                            "name": f"{mcp_name}__{tool_def.name}",
                            "description": tool_def.description,
                            "parameters": tool_def.input_schema or {
                                "type": "object",
                                "properties": {},
                            },
                        },
                    }
                )
        return schemas

    async def _run_tool_calling_loop(
        self, provider: LLMProvider, model: str
    ) -> tuple:
        """Run the generate -> execute tool calls -> feed results back loop.

        Returns:
            Tuple of (final response text, list of executed ToolCall records)
        """
        llm_messages = self._build_llm_messages()
        tools_schema = await self._tools_to_llm_schema()
        executed_tool_calls: List[ToolCall] = []

        for _ in range(self.max_tool_calls + 1):
            response = await provider.generate(llm_messages, tools_schema, model)

            if not response.tool_calls:
                return response.content or "", executed_tool_calls

            llm_messages.append(
                LLMMessage(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
            )

            for call in response.tool_calls:
                mcp_name, _, tool_name = call.name.partition("__")
                tool_call_record = ToolCall(
                    tool_name=tool_name or call.name,
                    mcp_name=mcp_name,
                    inputs=call.arguments,
                )

                try:
                    result = await self.registry.call_tool(mcp_name, tool_name, call.arguments)
                    tool_call_record.result = result
                    tool_content = json.dumps(result)
                except Exception as e:
                    tool_call_record.error = str(e)
                    tool_content = json.dumps({"error": str(e)})

                executed_tool_calls.append(tool_call_record)
                llm_messages.append(
                    LLMMessage(role="tool", content=tool_content, tool_call_id=call.id)
                )

        return "Max tool calls exceeded without a final response.", executed_tool_calls

    def clear_history(self) -> None:
        """Clear all message history."""
        self.history.clear()

    def get_history(self) -> List[Message]:
        """Get the full message history.

        Returns:
            List of messages
        """
        return self.history

    def get_history_dict(self) -> List[Dict[str, Any]]:
        """Get the message history as dictionaries.

        Returns:
            List of message dictionaries
        """
        return [msg.to_dict() for msg in self.history]
