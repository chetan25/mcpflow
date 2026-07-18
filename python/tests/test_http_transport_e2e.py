"""End-to-end test of the Streamable HTTP transport against a real ASGI client.

Existing unit tests only checked StreamableHTTPTransport's config attributes
and its request_handlers bookkeeping - none of them ever exercised the real
FastAPI app's routing. That gap hid a real bug: HTTPBridgeServer registered a
"/discover" handler that had no matching FastAPI route at all, so it was
completely unreachable over HTTP. This test drives the actual ASGI app via
httpx.ASGITransport (in-process, no real socket) against a real WebMCPBridge
and HTML fixture to prove the whole HTTP path - not just the handler
functions - actually works.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

httpx = pytest.importorskip("httpx")
pytest.importorskip("fastapi")

from mcpflow.webmcp.bridge import WebMCPBridge

_MODEL_CONTEXT_POLYFILL = """
navigator.modelContext = {
    registerTool: function(toolDef) {}
};
"""

_FIXTURE_PAGE = """
<!DOCTYPE html>
<html>
<head><title>HTTP transport e2e fixture</title></head>
<body>
<script>
navigator.modelContext.registerTool({
    name: "echo",
    description: "Echo the input",
    inputSchema: {type: "object", properties: {value: {type: "string"}}},
    execute: async function(args) { return { echoed: args.value }; }
});
</script>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_http_transport_discover_and_call_tool_over_real_asgi_app():
    """Drive /discover and /mcp/call_tool through the real FastAPI app."""
    with TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "fixture.html"
        fixture_path.write_text(_FIXTURE_PAGE)
        url = fixture_path.as_uri()

        bridge = WebMCPBridge(headless=True, origins_allowlist=[url])
        try:
            page = await bridge.browser.get_page_for_origin("httpfixture")
            await page.add_init_script(_MODEL_CONTEXT_POLYFILL)

            http_server = bridge.get_http_server()
            app = http_server.transport.build_app()

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                discover_response = await client.post(
                    "/discover", json={"origin": url, "origin_slug": "httpfixture"}
                )
                assert discover_response.status_code == 200
                discover_data = discover_response.json()
                assert discover_data["tools"][0]["name"] == "echo"

                call_response = await client.post(
                    "/mcp/call_tool",
                    json={
                        "origin": "httpfixture",
                        "tool": "echo",
                        "arguments": {"value": "hello"},
                    },
                )
                assert call_response.status_code == 200
                call_data = call_response.json()

                chunks = call_data["chunks"]
                final_chunk = chunks[-1]
                assert final_chunk["final"] is True
                assert "hello" in final_chunk["content"]

                health_response = await client.get("/mcp/health")
                assert health_response.status_code == 200
                assert health_response.json()["status"] == "healthy"
        finally:
            await bridge.close()


@pytest.mark.asyncio
async def test_http_transport_discover_route_actually_exists():
    """Regression test: /discover must be a real FastAPI route, not just an
    entry in request_handlers with nothing serving it."""
    from mcpflow.webmcp.http_transport import HTTPBridgeServer

    bridge = WebMCPBridge(headless=True, origins_allowlist=["https://example.com"])
    try:
        http_server = bridge.get_http_server()
        app = http_server.transport.build_app()

        route_paths = {route.path for route in app.routes}
        assert "/discover" in route_paths
    finally:
        await bridge.close()
