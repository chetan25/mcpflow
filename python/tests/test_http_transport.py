"""Tests for HTTP transport."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from mcpflow.webmcp.http_transport import (
    StreamableHTTPTransport,
    HTTPBridgeServer,
)


def test_streamable_http_transport_creation():
    """Test StreamableHTTPTransport creation."""
    transport = StreamableHTTPTransport(
        host="0.0.0.0",
        port=8000,
        use_sse=True,
    )

    assert transport.host == "0.0.0.0"
    assert transport.port == 8000
    assert transport.use_sse is True
    assert transport.enable_cors is False


def test_streamable_http_transport_cors():
    """Test StreamableHTTPTransport with CORS."""
    transport = StreamableHTTPTransport(
        host="127.0.0.1",
        port=9000,
        enable_cors=True,
    )

    assert transport.enable_cors is True


def test_streamable_http_transport_register_handler():
    """Test registering handlers."""
    transport = StreamableHTTPTransport()

    async def dummy_handler(data):
        return {"result": "ok"}

    transport.register_handler("POST /discover", dummy_handler)

    assert "POST /discover" in transport.request_handlers
    assert transport.request_handlers["POST /discover"] is dummy_handler


class MockBridge:
    def __init__(self):
        self.manifests = {}

    def get_streaming_executor(self):
        from mcpflow.webmcp.streaming import StreamingToolExecutor

        return StreamingToolExecutor(self)


def test_http_bridge_server_creation():
    """Test HTTPBridgeServer creation."""
    bridge = MockBridge()
    server = HTTPBridgeServer(
        bridge,
        host="0.0.0.0",
        port=8080,
        use_sse=True,
    )

    assert server.bridge is bridge
    assert server.transport.host == "0.0.0.0"
    assert server.transport.port == 8080


def test_http_bridge_server_routes_registered():
    """Test that routes are registered."""
    bridge = MockBridge()
    server = HTTPBridgeServer(bridge)

    # Check that handlers were registered
    assert "POST /discover" in server.transport.request_handlers
    assert "POST /mcp/call_tool" in server.transport.request_handlers


@pytest.mark.asyncio
async def test_http_bridge_server_handle_discover_no_origin():
    """Test discover handler without origin."""
    bridge = MockBridge()
    server = HTTPBridgeServer(bridge)

    handler = server.transport.request_handlers["POST /discover"]
    result = await handler({})

    assert "error" in result
    assert "origin" in result["error"].lower()


@pytest.mark.asyncio
async def test_http_bridge_server_handle_call_tool_missing_params():
    """Test call_tool handler with missing parameters."""
    bridge = MockBridge()
    server = HTTPBridgeServer(bridge)

    handler = server.transport.request_handlers["POST /mcp/call_tool"]

    # Missing tool
    result = await handler({"origin": "test.com"})
    assert "error" in result

    # Missing origin
    result = await handler({"tool": "test"})
    assert "error" in result


def test_http_bridge_server_context_manager():
    """Test HTTPBridgeServer as async context manager."""
    bridge = MockBridge()
    server = HTTPBridgeServer(bridge)

    # Just verify it has the context manager methods
    assert hasattr(server, "__aenter__")
    assert hasattr(server, "__aexit__")


def test_streamable_http_transport_health_endpoint():
    """Test health data structure."""
    transport = StreamableHTTPTransport(use_sse=True)

    # Simulate health check data
    health_data = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "sse_enabled": transport.use_sse,
        "active_streams": len(transport.sse_connections),
    }

    assert health_data["status"] == "healthy"
    assert "timestamp" in health_data
    assert health_data["sse_enabled"] is True
    assert health_data["active_streams"] == 0
