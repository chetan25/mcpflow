"""Tests for chat management and orchestration."""

import asyncio
from datetime import datetime

import pytest

from mcpflow import ChatManager, Message, ToolCall


class TestMessage:
    """Tests for Message dataclass."""

    def test_message_creation(self):
        """Test creating a basic message."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp is not None
        assert isinstance(msg.timestamp, datetime)
        assert msg.tool_calls == []

    def test_message_with_tool_calls(self):
        """Test message with tool calls."""
        tool_call = ToolCall(
            tool_name="get_weather",
            mcp_name="weather_service",
            inputs={"location": "NYC"},
        )
        msg = Message(role="assistant", content="Checking weather...", tool_calls=[tool_call])
        assert msg.role == "assistant"
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].tool_name == "get_weather"

    def test_message_to_dict(self):
        """Test converting message to dictionary."""
        msg = Message(role="user", content="Test message")
        msg_dict = msg.to_dict()
        assert msg_dict["role"] == "user"
        assert msg_dict["content"] == "Test message"
        assert "timestamp" in msg_dict
        assert msg_dict["tool_calls"] == []

    def test_message_to_dict_with_tool_calls(self):
        """Test converting message with tool calls to dictionary."""
        tool_call = ToolCall(
            tool_name="search",
            mcp_name="search_service",
            inputs={"query": "python"},
            result={"results": ["a", "b", "c"]},
        )
        msg = Message(role="assistant", content="Searching...", tool_calls=[tool_call])
        msg_dict = msg.to_dict()

        assert len(msg_dict["tool_calls"]) == 1
        assert msg_dict["tool_calls"][0]["tool_name"] == "search"
        assert msg_dict["tool_calls"][0]["result"] == {"results": ["a", "b", "c"]}


class TestChatManager:
    """Tests for ChatManager class."""

    def test_chat_manager_init_defaults(self):
        """Test ChatManager initialization with defaults."""
        manager = ChatManager()
        assert manager.model is None
        assert manager.registry is None
        assert manager.max_tool_calls == 10
        assert manager.history == []
        assert manager.system_prompt == ChatManager._DEFAULT_SYSTEM_PROMPT

    def test_chat_manager_init_with_params(self):
        """Test ChatManager initialization with parameters."""
        custom_prompt = "You are a test assistant"
        manager = ChatManager(
            model="gpt-4",
            system_prompt=custom_prompt,
            max_tool_calls=5,
        )
        assert manager.model == "gpt-4"
        assert manager.system_prompt == custom_prompt
        assert manager.max_tool_calls == 5

    def test_default_system_prompt(self):
        """Test default system prompt."""
        prompt = ChatManager._default_system_prompt()
        assert "helpful assistant" in prompt.lower()
        assert "tools" in prompt.lower()

    def test_clear_history(self):
        """Test clearing chat history."""
        manager = ChatManager(model="test")
        manager.history.append(Message(role="user", content="test"))
        assert len(manager.history) == 1

        manager.clear_history()
        assert len(manager.history) == 0

    def test_get_history(self):
        """Test getting chat history."""
        manager = ChatManager()
        msg1 = Message(role="user", content="Hello")
        msg2 = Message(role="assistant", content="Hi there")

        manager.history.append(msg1)
        manager.history.append(msg2)

        history = manager.get_history()
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"

    def test_get_history_dict(self):
        """Test getting chat history as dictionaries."""
        manager = ChatManager()
        manager.history.append(Message(role="user", content="Test"))
        manager.history.append(Message(role="assistant", content="Response"))

        history_dict = manager.get_history_dict()
        assert len(history_dict) == 2
        assert history_dict[0]["role"] == "user"
        assert history_dict[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_send_message_with_model(self):
        """Test sending a message with model configured."""
        manager = ChatManager(model="test-model")
        response = await manager.send("Hello")

        assert "test-model" in response
        assert len(manager.history) == 2  # user message + assistant response
        assert manager.history[0].role == "user"
        assert manager.history[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_send_message_without_model_raises(self):
        """Test sending message without model raises ValueError."""
        manager = ChatManager()
        with pytest.raises(ValueError, match="No model configured"):
            await manager.send("Hello")

    @pytest.mark.asyncio
    async def test_send_message_with_model_override(self):
        """Test sending message with model override."""
        manager = ChatManager(model="default-model")
        response = await manager.send("Hello", model_override="override-model")

        assert "override-model" in response

    @pytest.mark.asyncio
    async def test_send_message_with_context(self):
        """Test sending message with context."""
        manager = ChatManager(model="test-model")
        context = {"user_id": "123", "session": "abc"}
        response = await manager.send("Hello", context=context)

        assert response is not None
        assert len(manager.history) == 2

    @pytest.mark.asyncio
    async def test_chat_history_accumulation(self):
        """Test that chat history accumulates correctly."""
        manager = ChatManager(model="test-model")

        # Send first message
        response1 = await manager.send("First message")
        assert len(manager.history) == 2

        # Send second message
        response2 = await manager.send("Second message")
        assert len(manager.history) == 4
        assert manager.history[0].content == "First message"
        assert manager.history[2].content == "Second message"

    def test_tool_call_creation(self):
        """Test creating a tool call."""
        tool_call = ToolCall(
            tool_name="calculator",
            mcp_name="math_service",
            inputs={"operation": "add", "a": 1, "b": 2},
        )
        assert tool_call.tool_name == "calculator"
        assert tool_call.mcp_name == "math_service"
        assert tool_call.inputs["operation"] == "add"
        assert tool_call.result is None
        assert tool_call.error is None

    def test_tool_call_with_result(self):
        """Test tool call with result."""
        tool_call = ToolCall(
            tool_name="add",
            mcp_name="math",
            inputs={"a": 1, "b": 2},
            result={"sum": 3},
        )
        assert tool_call.result == {"sum": 3}
        assert tool_call.error is None

    def test_tool_call_with_error(self):
        """Test tool call with error."""
        tool_call = ToolCall(
            tool_name="divide",
            mcp_name="math",
            inputs={"a": 1, "b": 0},
            error="Division by zero",
        )
        assert tool_call.error == "Division by zero"
        assert tool_call.result is None
