"""Chat management and orchestration."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

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
    ):
        """Initialize chat manager.
        
        Args:
            model: Model name/ID for LLM inference
            registry: MCPRegistry instance for tool execution
            system_prompt: System prompt for the chat
            max_tool_calls: Maximum number of tool calls per message
        """
        self.model = model
        self.registry = registry
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.max_tool_calls = max_tool_calls
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
            context: Additional context for the request
            
        Returns:
            Assistant response
            
        Raises:
            ValueError: If no model configured and no override provided
        """
        with self._tracer.start_span("chat_send", {"model": model_override or self.model}):
            if not (model_override or self.model):
                raise ValueError("No model configured. Provide model or override.")
            
            # Add user message to history
            user_msg = Message(role="user", content=message)
            self.history.append(user_msg)
            
            # For now, simulate a response (actual LLM integration would go here)
            response = await self._generate_response(model_override or self.model, context)
            
            # Add assistant message to history
            assistant_msg = Message(role="assistant", content=response)
            self.history.append(assistant_msg)
            
            return response

    async def _generate_response(
        self, model: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate a response using the model.
        
        Args:
            model: Model to use
            context: Additional context
            
        Returns:
            Generated response
        """
        # Simulate async response generation
        await asyncio.sleep(0.01)
        return f"Response from {model} model"

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
