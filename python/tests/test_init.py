"""Tests for mcpflow package initialization."""

import pytest

from mcpflow import (
    ChatManager,
    Config,
    HTTPBridge,
    MCPRequest,
    MCPResponse,
    MCPServer,
    Message,
    MockServer,
    ToolDefinition,
    ToolRegistry,
    Tracer,
    __version__,
    create_test_server,
    tool,
)


class TestImports:
    """Test that all public API exports are importable."""

    def test_version(self):
        """Test version string."""
        assert __version__ == "0.1.0"

    def test_mcp_server_import(self):
        """Test MCPServer import."""
        assert MCPServer is not None
        server = MCPServer()
        assert server is not None

    def test_config_import(self):
        """Test Config import."""
        assert Config is not None
        config = Config()
        assert config.server_name == "mcpflow"
        assert config.debug is False

    def test_chat_manager_import(self):
        """Test ChatManager import."""
        assert ChatManager is not None
        manager = ChatManager()
        assert manager is not None

    def test_message_import(self):
        """Test Message import."""
        assert Message is not None
        msg = Message("user", "Hello")
        assert msg["role"] == "user"
        assert msg["content"] == "Hello"

    def test_tool_definition_import(self):
        """Test ToolDefinition import."""
        assert ToolDefinition is not None
        tool_def = ToolDefinition(name="test_tool", description="Test tool")
        assert tool_def.name == "test_tool"

    def test_mcp_request_import(self):
        """Test MCPRequest import."""
        assert MCPRequest is not None
        req = MCPRequest(method="test")
        assert req.method == "test"

    def test_mcp_response_import(self):
        """Test MCPResponse import."""
        assert MCPResponse is not None
        resp = MCPResponse()
        assert resp is not None

    def test_tool_registry_import(self):
        """Test ToolRegistry import."""
        assert ToolRegistry is not None
        registry = ToolRegistry()
        assert registry is not None

    def test_http_bridge_import(self):
        """Test HTTPBridge import."""
        assert HTTPBridge is not None

    def test_tracer_import(self):
        """Test Tracer import."""
        assert Tracer is not None
        tracer = Tracer()
        assert tracer is not None

    def test_mock_server_import(self):
        """Test MockServer import."""
        assert MockServer is not None
        mock = MockServer()
        assert mock is not None

    def test_create_test_server_import(self):
        """Test create_test_server import."""
        assert create_test_server is not None
        server = create_test_server()
        assert server is not None

    def test_tool_decorator_import(self):
        """Test tool decorator import."""
        assert tool is not None

        @tool("my_tool", "A test tool")
        def my_tool():
            return "result"

        assert my_tool._tool_name == "my_tool"
        assert my_tool._tool_description == "A test tool"


class TestBasicFunctionality:
    """Test basic functionality of imported classes."""

    def test_server_creation(self):
        """Test server creation."""
        config = Config(debug=True)
        server = MCPServer(config)
        assert server.config.debug is True

    def test_config_to_dict(self):
        """Test config conversion to dict."""
        config = Config(server_name="test-server")
        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)
        assert config_dict["server_name"] == "test-server"

    def test_chat_manager_session(self):
        """Test chat manager session management."""
        manager = ChatManager()
        manager.create_session("session1")
        msg = Message("user", "Hello")
        manager.add_message("session1", msg)
        history = manager.get_history("session1")
        assert len(history) == 1
        assert history[0]["content"] == "Hello"

    def test_tool_registry(self):
        """Test tool registry."""
        registry = ToolRegistry()
        tool_def = ToolDefinition(name="test", description="Test tool")

        def handler():
            return "test"

        registry.register(tool_def, handler)
        retrieved = registry.get("test")
        assert retrieved is not None
        assert retrieved.name == "test"

    def test_tracer_creation(self):
        """Test tracer creation."""
        tracer = Tracer(service_name="test-service", enabled=False)
        assert tracer.service_name == "test-service"
        assert tracer.enabled is False

    def test_mock_server_creation(self):
        """Test mock server creation."""
        mock = MockServer()
        assert mock.call_history == []

    @pytest.mark.asyncio
    async def test_mock_server_call_history(self):
        """Test mock server call history tracking."""
        mock = MockServer()
        tool_def = ToolDefinition(name="test_tool", description="Test")

        async def handler():
            return "result"

        mock.register_tool(tool_def, handler)
        await mock.call_tool("test_tool", {})
        assert len(mock.call_history) == 1
        assert mock.call_history[0]["tool"] == "test_tool"
