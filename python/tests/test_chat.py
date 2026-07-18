"""Tests for chat management and orchestration."""

from datetime import datetime

import pytest

from mcpflow import ChatManager, Message, ToolCall
from mcpflow.providers import LLMResponse, LLMToolCall


class FakeProvider:
    """Test double for LLMProvider - returns scripted responses in order."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []  # list of (messages, tools, model) tuples

    async def generate(self, messages, tools, model):
        self.calls.append((messages, tools, model))
        return self._responses.pop(0)


class FakeRegistry:
    """Minimal test double matching the MCPRegistry surface ChatManager uses."""

    def __init__(self, tools_by_mcp, call_tool_fn):
        self._tools_by_mcp = tools_by_mcp
        self._call_tool_fn = call_tool_fn
        self.calls = []

    def get_registered_mcps(self):
        return list(self._tools_by_mcp.keys())

    def get_tools(self, mcp_name):
        return self._tools_by_mcp.get(mcp_name, [])

    async def call_tool(self, mcp_name, tool_name, inputs):
        self.calls.append((mcp_name, tool_name, inputs))
        return await self._call_tool_fn(mcp_name, tool_name, inputs)


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
        assert manager.provider is None
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
        """Test sending a message calls the provider with the configured model."""
        provider = FakeProvider([LLMResponse(content="Hi there", tool_calls=[])])
        manager = ChatManager(model="test-model", provider=provider)
        response = await manager.send("Hello")

        assert response == "Hi there"
        assert provider.calls[0][2] == "test-model"
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
    async def test_send_message_without_provider_raises_when_litellm_unavailable(self, monkeypatch):
        """When no provider is given and litellm can't be imported, send()
        must fail loudly - never silently fake a response."""
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "litellm":
                raise ImportError("simulated: litellm not installed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        manager = ChatManager(model="test-model")
        with pytest.raises(RuntimeError, match="litellm"):
            await manager.send("Hello")

    @pytest.mark.asyncio
    async def test_send_message_with_model_override(self):
        """Test sending message with model override passes it to the provider."""
        provider = FakeProvider([LLMResponse(content="Override response", tool_calls=[])])
        manager = ChatManager(model="default-model", provider=provider)
        response = await manager.send("Hello", model_override="override-model")

        assert response == "Override response"
        assert provider.calls[0][2] == "override-model"

    @pytest.mark.asyncio
    async def test_send_message_with_context(self):
        """Test sending message with context."""
        provider = FakeProvider([LLMResponse(content="ok", tool_calls=[])])
        manager = ChatManager(model="test-model", provider=provider)
        context = {"user_id": "123", "session": "abc"}
        response = await manager.send("Hello", context=context)

        assert response is not None
        assert len(manager.history) == 2

    @pytest.mark.asyncio
    async def test_chat_history_accumulation(self):
        """Test that chat history accumulates correctly across turns."""
        provider = FakeProvider(
            [
                LLMResponse(content="First response", tool_calls=[]),
                LLMResponse(content="Second response", tool_calls=[]),
            ]
        )
        manager = ChatManager(model="test-model", provider=provider)

        await manager.send("First message")
        assert len(manager.history) == 2

        await manager.send("Second message")
        assert len(manager.history) == 4
        assert manager.history[0].content == "First message"
        assert manager.history[2].content == "Second message"

    @pytest.mark.asyncio
    async def test_send_executes_tool_call_via_registry(self):
        """ChatManager's loop actually invokes the registry tool the
        provider requested, then feeds the real result back for a final
        answer - proving this isn't a simulated response."""
        from mcpflow.types import ToolDefinition

        tools_by_mcp = {
            "calc": [
                ToolDefinition(
                    name="add",
                    description="Add two numbers",
                    input_schema={
                        "type": "object",
                        "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                    },
                )
            ]
        }

        async def call_tool_fn(mcp_name, tool_name, inputs):
            return {"sum": inputs["a"] + inputs["b"]}

        registry = FakeRegistry(tools_by_mcp, call_tool_fn)

        provider = FakeProvider(
            [
                LLMResponse(
                    content=None,
                    tool_calls=[
                        LLMToolCall(id="call-1", name="calc__add", arguments={"a": 2, "b": 3})
                    ],
                ),
                LLMResponse(content="The sum is 5", tool_calls=[]),
            ]
        )

        manager = ChatManager(model="test-model", registry=registry, provider=provider)
        response = await manager.send("What is 2 + 3?")

        assert response == "The sum is 5"
        assert registry.calls == [("calc", "add", {"a": 2, "b": 3})]
        assert len(manager.history) == 2
        assert len(manager.history[1].tool_calls) == 1
        assert manager.history[1].tool_calls[0].result == {"sum": 5}

        # Tool schema handed to the provider should be namespaced {mcp}__{tool}
        first_call_tools = provider.calls[0][1]
        assert first_call_tools[0]["function"]["name"] == "calc__add"

    @pytest.mark.asyncio
    async def test_send_reports_tool_error_back_to_provider(self):
        """A failing tool call is fed back as an error, not raised, so the
        model can react instead of the whole loop crashing."""
        from mcpflow.types import ToolDefinition

        tools_by_mcp = {
            "calc": [ToolDefinition(name="divide", description="Divide", input_schema={})]
        }

        async def call_tool_fn(mcp_name, tool_name, inputs):
            raise ValueError("Division by zero")

        registry = FakeRegistry(tools_by_mcp, call_tool_fn)

        provider = FakeProvider(
            [
                LLMResponse(
                    content=None,
                    tool_calls=[
                        LLMToolCall(id="call-1", name="calc__divide", arguments={"a": 1, "b": 0})
                    ],
                ),
                LLMResponse(content="I couldn't divide by zero.", tool_calls=[]),
            ]
        )

        manager = ChatManager(model="test-model", registry=registry, provider=provider)
        response = await manager.send("Divide 1 by 0")

        assert response == "I couldn't divide by zero."
        assert manager.history[1].tool_calls[0].error == "Division by zero"
        assert manager.history[1].tool_calls[0].result is None

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
