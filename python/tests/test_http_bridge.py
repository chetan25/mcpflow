"""Tests for HTTP MCP Client Bridge."""

import pytest
from unittest.mock import AsyncMock, MagicMock

import httpx

from mcpflow.http_bridge import MCPHTTPBridge
from mcpflow.types import ToolDefinition


@pytest.fixture
def mock_httpx_client(monkeypatch):
    """Fixture for mocking httpx.AsyncClient."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_get_patcher = AsyncMock()
    mock_post_patcher = AsyncMock()

    mock_client.get = mock_get_patcher
    mock_client.post = mock_post_patcher
    mock_client.aclose = AsyncMock()

    original_async_client = httpx.AsyncClient

    def mock_async_client_init(*args, **kwargs):
        return mock_client

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: mock_client)
    return mock_client


@pytest.mark.asyncio
async def test_http_bridge_init():
    """Test MCPHTTPBridge initialization."""
    bridge = MCPHTTPBridge(
        url="http://localhost:8000",
        auth_token="test-token",
        timeout=60.0,
    )

    assert bridge.url == "http://localhost:8000"
    assert bridge.auth_token == "test-token"
    assert bridge.timeout == 60.0
    assert bridge._client is None


@pytest.mark.asyncio
async def test_http_bridge_init_url_normalization():
    """Test URL normalization (trailing slash removal)."""
    bridge = MCPHTTPBridge(url="http://localhost:8000/")

    assert bridge.url == "http://localhost:8000"


@pytest.mark.asyncio
async def test_get_headers_with_auth():
    """Test header generation with authentication."""
    bridge = MCPHTTPBridge(
        url="http://localhost:8000",
        auth_token="test-token",
    )

    headers = bridge._get_headers()

    assert headers["Content-Type"] == "application/json"
    assert headers["Authorization"] == "Bearer test-token"


@pytest.mark.asyncio
async def test_get_headers_without_auth():
    """Test header generation without authentication."""
    bridge = MCPHTTPBridge(url="http://localhost:8000")

    headers = bridge._get_headers()

    assert headers["Content-Type"] == "application/json"
    assert "Authorization" not in headers


@pytest.mark.asyncio
async def test_discover_tools(mock_httpx_client):
    """Test tool discovery."""
    bridge = MCPHTTPBridge(
        url="http://localhost:8000",
        auth_token="test-token",
    )

    # Mock the response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "tools": [
            {
                "name": "tool1",
                "description": "Tool 1",
                "input_schema": {"type": "object"},
            },
            {
                "name": "tool2",
                "description": "Tool 2",
                "input_schema": {"type": "object"},
            },
        ]
    }
    mock_httpx_client.get.return_value = mock_response

    tools = await bridge.discover()

    assert len(tools) == 2
    assert tools[0].name == "tool1"
    assert tools[0].description == "Tool 1"
    assert tools[1].name == "tool2"

    # Verify the request was made correctly
    mock_httpx_client.get.assert_called_once()
    call_args = mock_httpx_client.get.call_args
    assert "http://localhost:8000/tools" in str(call_args)


@pytest.mark.asyncio
async def test_discover_tools_empty(mock_httpx_client):
    """Test discovery with no tools."""
    bridge = MCPHTTPBridge(url="http://localhost:8000")

    mock_response = MagicMock()
    mock_response.json.return_value = {"tools": []}
    mock_httpx_client.get.return_value = mock_response

    tools = await bridge.discover()

    assert len(tools) == 0


@pytest.mark.asyncio
async def test_call_tool(mock_httpx_client):
    """Test tool invocation."""
    bridge = MCPHTTPBridge(
        url="http://localhost:8000",
        auth_token="test-token",
    )

    # Mock the response
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": "success", "data": "test-data"}
    mock_httpx_client.post.return_value = mock_response

    result = await bridge.call_tool("test_tool", {"param1": "value1"})

    assert result["result"] == "success"
    assert result["data"] == "test-data"

    # Verify the request was made correctly
    mock_httpx_client.post.assert_called_once()
    call_args = mock_httpx_client.post.call_args
    assert "http://localhost:8000/tools/test_tool/call" in str(call_args)


@pytest.mark.asyncio
async def test_call_tool_error(mock_httpx_client):
    """Test tool invocation with error."""
    bridge = MCPHTTPBridge(url="http://localhost:8000")

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404 Not Found", request=MagicMock(), response=mock_response
    )
    mock_httpx_client.post.return_value = mock_response

    with pytest.raises(httpx.HTTPStatusError):
        await bridge.call_tool("nonexistent_tool", {})


@pytest.mark.asyncio
async def test_close():
    """Test closing the bridge."""
    bridge = MCPHTTPBridge(url="http://localhost:8000")

    # Create a real mock client with spec
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.aclose = AsyncMock()
    bridge._client = mock_client

    await bridge.close()

    mock_client.aclose.assert_called_once()
    assert bridge._client is None


@pytest.mark.asyncio
async def test_close_without_client():
    """Test closing when no client exists."""
    bridge = MCPHTTPBridge(url="http://localhost:8000")

    # Should not raise an error
    await bridge.close()

    assert bridge._client is None


@pytest.mark.asyncio
async def test_context_manager():
    """Test using bridge as async context manager."""
    # Create a real mock client
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.aclose = AsyncMock()

    async with MCPHTTPBridge(url="http://localhost:8000") as bridge:
        # Set up the mock after bridge is created
        bridge._client = mock_client
        assert bridge is not None

    # After exiting the context manager, close should have been called
    mock_client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_discover_and_call_workflow(mock_httpx_client):
    """Test a complete discover and call workflow."""
    bridge = MCPHTTPBridge(url="http://localhost:8000", auth_token="test-token")

    # Mock discovery response
    discover_response = MagicMock()
    discover_response.json.return_value = {
        "tools": [
            {
                "name": "add",
                "description": "Add two numbers",
                "input_schema": {"type": "object", "properties": {}},
            }
        ]
    }

    # Mock call response
    call_response = MagicMock()
    call_response.json.return_value = {"result": 5}

    # Setup the mock to return different responses
    mock_httpx_client.get.return_value = discover_response
    mock_httpx_client.post.return_value = call_response

    # Discover tools
    tools = await bridge.discover()
    assert len(tools) == 1
    assert tools[0].name == "add"

    # Call the tool
    result = await bridge.call_tool("add", {"a": 2, "b": 3})
    assert result["result"] == 5

    # Cleanup
    await bridge.close()
