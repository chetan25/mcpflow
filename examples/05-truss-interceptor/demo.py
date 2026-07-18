"""Runnable demo: WebMCPBridge with a pluggable, Truss-shaped interceptor.

Run:
    pip install mcpflow[webmcp]
    playwright install chromium
    python demo.py

Shows the InterceptorProtocol seam actually gating tool calls: a tool
matching the scope manifest is allowed, one that doesn't is blocked -
without WebMCPBridge or its default DefaultInterceptor ever being involved.
"""

import asyncio
import tempfile
from pathlib import Path

from mcpflow.webmcp.bridge import WebMCPBridge
from mcpflow.webmcp.interceptor import InterceptorProtocol
from truss_style_interceptor import ExampleTrussStyleInterceptor, ScopeManifest

# Stand-in for the browser's native navigator.modelContext (the real W3C
# WebMCP origin-trial API isn't available without a Chrome trial token).
_MODEL_CONTEXT_POLYFILL = """
navigator.modelContext = {
    registerTool: function(toolDef) {}
};
"""

_FIXTURE_PAGE = """
<!DOCTYPE html>
<html>
<head><title>Truss interceptor demo fixture</title></head>
<body>
<script>
navigator.modelContext.registerTool({
    name: "searchItems",
    description: "Search items (read-only)",
    inputSchema: {type: "object", properties: {query: {type: "string"}}},
    execute: async function(args) { return { results: ["item-a", "item-b"] }; }
});
navigator.modelContext.registerTool({
    name: "deleteAccount",
    description: "Delete the user's account",
    inputSchema: {type: "object", properties: {}},
    execute: async function(args) { return { deleted: true }; }
});
</script>
</body>
</html>
"""


async def main():
    # Only "search*" tools are in scope - "deleteAccount" is not, so the
    # interceptor should block it before it ever reaches the browser.
    manifest = ScopeManifest(allowed_tool_patterns=["search*"])
    interceptor = ExampleTrussStyleInterceptor(manifest)

    print("Structurally conforms to InterceptorProtocol:", isinstance(interceptor, InterceptorProtocol))

    with tempfile.TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "fixture.html"
        fixture_path.write_text(_FIXTURE_PAGE)
        url = fixture_path.as_uri()

        bridge = WebMCPBridge(
            headless=True,
            origins_allowlist=[url],
            interceptor=interceptor,
        )
        try:
            page = await bridge.browser.get_page_for_origin("demo")
            await page.add_init_script(_MODEL_CONTEXT_POLYFILL)

            manifest_result = await bridge.discover(url, origin_slug="demo")
            print(f"\nDiscovered tools: {[t.name for t in manifest_result.tools]}")

            allowed_result = await bridge.call_tool("demo", "searchItems", {"query": "widgets"})
            print(f"\nsearchItems (in scope):   success={allowed_result.success} result={allowed_result.result}")

            blocked_result = await bridge.call_tool("demo", "deleteAccount", {})
            print(f"deleteAccount (out of scope): success={blocked_result.success} error={blocked_result.error}")

            print("\nAudit trail recorded by the interceptor:")
            for event in interceptor.audit_events:
                print(f"  {event}")
        finally:
            await bridge.close()


if __name__ == "__main__":
    asyncio.run(main())
