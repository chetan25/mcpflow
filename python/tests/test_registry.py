"""Tests for MCP Registry."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from mcpflow.config import AuthConfig, MCPConfig
from mcpflow.registry import MCPRegistry
from mcpflow.types import ToolDefinition


@pytest.fixture
def mock_httpx_client(monkeypatch):
    """Fixture for mocking httpx.AsyncClient."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock()
    mock_client.post = AsyncMock()
    mock_client.aclose = AsyncMock()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: mock_client)
    return mock_client


@pytest.fixture
def sample_tools():
    """Sample tool definitions."""
    return [
        ToolDefinition(name="tool1", description="First tool", input_schema={}),
        ToolDefinition(name="tool2", description="Second tool", input_schema={}),
        ToolDefinition(name="tool3", description="Third tool", input_schema={}),
    ]


@pytest.fixture
def sample_mcp_config():
    """Sample MCP configuration."""
    return MCPConfig(
        name="test_server",
        url="http://localhost:8000",
        auth=AuthConfig(type="bearer", token="test-token"),
        timeout=30.0,
    )


@pytest.mark.asyncio
async def test_registry_init():
    """Test MCPRegistry initialization."""
    registry = MCPRegistry()

    assert registry.get_registered_mcps() == []
    assert registry.get_tools() == []


@pytest.mark.asyncio
async def test_register_mcp(mock_httpx_client, sample_mcp_config, sample_tools):
    """Test registering an MCP server."""
    # Mock the discovery response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "tools": [t.model_dump() for t in sample_tools]
    }
    mock_httpx_client.get.return_value = mock_response

    registry = MCPRegistry()
    tools = await registry.register_mcp(sample_mcp_config)

    assert len(tools) == 3
    assert tools[0].name == "tool1"
    assert tools[1].name == "tool2"
    assert tools[2].name == "tool3"
    assert "test_server" in registry.get_registered_mcps()


@pytest.mark.asyncio
async def test_register_mcp_with_tool_filter(
    mock_httpx_client, sample_mcp_config, sample_tools
):
    """Test registering MCP with tool filtering."""
    # Update config to filter tools
    sample_mcp_config.tools = ["tool1", "tool3"]

    # Mock the discovery response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "tools": [t.model_dump() for t in sample_tools]
    }
    mock_httpx_client.get.return_value = mock_response

    registry = MCPRegistry()
    tools = await registry.register_mcp(sample_mcp_config)

    # Should only have filtered tools
    assert len(tools) == 2
    assert tools[0].name == "tool1"
    assert tools[1].name == "tool3"


@pytest.mark.asyncio
async def test_register_multiple_mcps(mock_httpx_client, sample_tools):
    """Test registering multiple MCP servers."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "tools": [t.model_dump() for t in sample_tools]
    }
    mock_httpx_client.get.return_value = mock_response

    registry = MCPRegistry()

    config1 = MCPConfig(name="server1", url="http://localhost:8000")
    config2 = MCPConfig(name="server2", url="http://localhost:8001")

    await registry.register_mcp(config1)
    await registry.register_mcp(config2)

    assert len(registry.get_registered_mcps()) == 2
    assert "server1" in registry.get_registered_mcps()
    assert "server2" in registry.get_registered_mcps()


@pytest.mark.asyncio
async def test_get_tools_all(mock_httpx_client, sample_tools):
    """Test getting all tools from registry."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "tools": [t.model_dump() for t in sample_tools]
    }
    mock_httpx_client.get.return_value = mock_response

    registry = MCPRegistry()
    config1 = MCPConfig(name="server1", url="http://localhost:8000")
    config2 = MCPConfig(name="server2", url="http://localhost:8001")

    await registry.register_mcp(config1)
    await registry.register_mcp(config2)

    all_tools = registry.get_tools()

    # Should have 6 tools (3 from each server)
    assert len(all_tools) == 6


@pytest.mark.asyncio
async def test_get_tools_from_specific_mcp(
    mock_httpx_client, sample_mcp_config, sample_tools
):
    """Test getting tools from a specific MCP."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "tools": [t.model_dump() for t in sample_tools]
    }
    mock_httpx_client.get.return_value = mock_response

    registry = MCPRegistry()
    await registry.register_mcp(sample_mcp_config)

    tools = registry.get_tools("test_server")

    assert len(tools) == 3
    assert all(t.name in ["tool1", "tool2", "tool3"] for t in tools)


@pytest.mark.asyncio
async def test_get_tools_nonexistent_mcp(mock_httpx_client):
    """Test getting tools from nonexistent MCP."""
    registry = MCPRegistry()

    tools = registry.get_tools("nonexistent")

    assert tools == []


@pytest.mark.asyncio
async def test_call_tool(mock_httpx_client, sample_mcp_config, sample_tools):
    """Test calling a tool."""
    # Mock discovery response
    discover_response = MagicMock()
    discover_response.json.return_value = {
        "tools": [t.model_dump() for t in sample_tools]
    }

    # Mock call response
    call_response = MagicMock()
    call_response.json.return_value = {"result": "success", "data": "test-data"}

    # Setup mock to return different responses
    mock_httpx_client.get.return_value = discover_response
    mock_httpx_client.post.return_value = call_response

    registry = MCPRegistry()
    await registry.register_mcp(sample_mcp_config)

    result = await registry.call_tool("test_server", "tool1", {"param": "value"})

    assert result["result"] == "success"
    assert result["data"] == "test-data"


@pytest.mark.asyncio
async def test_call_tool_nonexistent_mcp(mock_httpx_client):
    """Test calling a tool on nonexistent MCP."""
    registry = MCPRegistry()

    with pytest.raises(ValueError, match="MCP 'nonexistent' not found"):
        await registry.call_tool("nonexistent", "tool1", {})


@pytest.mark.asyncio
async def test_call_tool_nonexistent_tool(
    mock_httpx_client, sample_mcp_config, sample_tools
):
    """Test calling a nonexistent tool."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "tools": [t.model_dump() for t in sample_tools]
    }
    mock_httpx_client.get.return_value = mock_response

    registry = MCPRegistry()
    await registry.register_mcp(sample_mcp_config)

    with pytest.raises(ValueError, match="Tool 'nonexistent_tool' not found"):
        await registry.call_tool("test_server", "nonexistent_tool", {})


@pytest.mark.asyncio
async def test_get_mcp_config(mock_httpx_client, sample_mcp_config):
    """Test getting MCP configuration."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"tools": []}
    mock_httpx_client.get.return_value = mock_response

    registry = MCPRegistry()
    await registry.register_mcp(sample_mcp_config)

    config = registry.get_mcp_config("test_server")

    assert config is not None
    assert config.name == "test_server"
    assert config.url == "http://localhost:8000"


@pytest.mark.asyncio
async def test_get_mcp_config_nonexistent(mock_httpx_client):
    """Test getting configuration for nonexistent MCP."""
    registry = MCPRegistry()

    config = registry.get_mcp_config("nonexistent")

    assert config is None


@pytest.mark.asyncio
async def test_close_all(mock_httpx_client, sample_mcp_config):
    """Test closing all connections."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"tools": []}
    mock_httpx_client.get.return_value = mock_response

    registry = MCPRegistry()
    config1 = MCPConfig(name="server1", url="http://localhost:8000")
    config2 = MCPConfig(name="server2", url="http://localhost:8001")

    await registry.register_mcp(config1)
    await registry.register_mcp(config2)

    # Verify we have registered MCPs
    assert len(registry.get_registered_mcps()) == 2

    await registry.close_all()

    # Verify cleanup
    assert len(registry.get_registered_mcps()) == 0
    assert mock_httpx_client.aclose.call_count == 2


@pytest.mark.asyncio
async def test_context_manager(mock_httpx_client, sample_mcp_config):
    """Test using registry as async context manager."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"tools": []}
    mock_httpx_client.get.return_value = mock_response

    async with MCPRegistry() as registry:
        await registry.register_mcp(sample_mcp_config)
        assert len(registry.get_registered_mcps()) == 1

    # After exiting context manager, should be cleaned up
    # The registry instance no longer has MCPs registered
    assert len(registry.get_registered_mcps()) == 0


@pytest.mark.asyncio
async def test_multiple_tool_calls(mock_httpx_client, sample_mcp_config, sample_tools):
    """Test multiple tool calls on the same MCP."""
    # Mock discovery response
    discover_response = MagicMock()
    discover_response.json.return_value = {
        "tools": [t.model_dump() for t in sample_tools]
    }

    # Mock multiple call responses
    call_response_1 = MagicMock()
    call_response_1.json.return_value = {"result": "first"}

    call_response_2 = MagicMock()
    call_response_2.json.return_value = {"result": "second"}

    # Setup mock responses
    mock_httpx_client.get.return_value = discover_response
    mock_httpx_client.post.side_effect = [call_response_1, call_response_2]

    registry = MCPRegistry()
    await registry.register_mcp(sample_mcp_config)

    result1 = await registry.call_tool("test_server", "tool1", {"x": 1})
    result2 = await registry.call_tool("test_server", "tool2", {"y": 2})

    assert result1["result"] == "first"
    assert result2["result"] == "second"


@pytest.mark.asyncio
async def test_registry_auth_token_handling(mock_httpx_client):
    """Test that auth tokens are properly passed to bridge."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"tools": []}
    mock_httpx_client.get.return_value = mock_response

    registry = MCPRegistry()

    config_with_auth = MCPConfig(
        name="secure_server",
        url="http://localhost:8000",
        auth=AuthConfig(type="bearer", token="secret-token-123"),
    )

    await registry.register_mcp(config_with_auth)

    # Verify the auth header was set correctly
    mock_httpx_client.get.assert_called_once()
    call_args = mock_httpx_client.get.call_args
    headers = call_args[1].get("headers", {})
    assert headers.get("Authorization") == "Bearer secret-token-123"
