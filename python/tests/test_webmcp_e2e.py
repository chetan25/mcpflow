"""End-to-end test proving the WebMCP bridge performs a REAL tool invocation.

Prior to the gap-closure work, calling any WebMCP tool through the bridge
returned a simulated echo of the input (`{"input": args, "schema": ...}`)
without ever touching the page. This test drives a real Chromium instance
via Playwright against a local HTML fixture and asserts a genuinely computed
result comes back instead.

Requires the `webmcp` optional dependency group (`playwright`, `mcp`) and a
Playwright-installed Chromium (`playwright install chromium`).
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

playwright = pytest.importorskip("playwright")

from mcpflow.webmcp.bridge import WebMCPBridge

# Stand-in for the browser's native navigator.modelContext (the real W3C
# WebMCP origin-trial API isn't available in stock Chromium without a trial
# token). This reproduces the API's documented shape exactly: a single
# tool-definition object with an `execute` callback.
_MODEL_CONTEXT_POLYFILL = """
navigator.modelContext = {
    registerTool: function(toolDef) {
        window.__test_registered = window.__test_registered || [];
        window.__test_registered.push(toolDef.name);
    }
};
"""

_FIXTURE_PAGE = """
<!DOCTYPE html>
<html>
<head><title>WebMCP E2E Fixture</title></head>
<body>
<form data-tool-name="notAWebMcpTool"></form>
<script>
navigator.modelContext.registerTool({
    name: "addNumbers",
    description: "Add two numbers",
    inputSchema: {
        type: "object",
        properties: {a: {type: "number"}, b: {type: "number"}},
        required: ["a", "b"]
    },
    execute: async function(args) {
        return { sum: args.a + args.b };
    }
});
</script>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_end_to_end_real_tool_invocation():
    """Discover a real WebMCP tool and invoke it end-to-end."""
    with TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "fixture.html"
        fixture_path.write_text(_FIXTURE_PAGE)
        url = fixture_path.as_uri()

        bridge = WebMCPBridge(headless=True, origins_allowlist=[url])
        try:
            await bridge.browser.initialize()
            # Install the polyfill before the bridge's own discovery hook
            # (added inside discover() -> prepare_discovery()), so the hook
            # has a real registerTool to wrap.
            await bridge.browser.page.add_init_script(_MODEL_CONTEXT_POLYFILL)

            manifest = await bridge.discover(url, origin_slug="fixture")

            assert manifest is not None
            assert len(manifest.tools) == 1
            assert manifest.tools[0].name == "addNumbers"

            result = await bridge.call_tool("fixture", "addNumbers", {"a": 2, "b": 3})

            assert result.success is True, result.error
            assert result.result == {"sum": 5}
            # The historical bug: this used to come back as
            # {"input": {"a": 2, "b": 3}, "schema": {...}} without ever
            # calling into the page. Assert that shape is gone.
            assert "input" not in (result.result or {})
            assert "schema" not in (result.result or {})
        finally:
            await bridge.close()


@pytest.mark.asyncio
async def test_end_to_end_unknown_tool_fails_cleanly():
    """Calling a tool that was never registered on the page fails with a
    real error instead of a fake success."""
    with TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "fixture.html"
        fixture_path.write_text(_FIXTURE_PAGE)
        url = fixture_path.as_uri()

        bridge = WebMCPBridge(headless=True, origins_allowlist=[url])
        try:
            await bridge.browser.initialize()
            await bridge.browser.page.add_init_script(_MODEL_CONTEXT_POLYFILL)
            await bridge.discover(url, origin_slug="fixture")

            result = await bridge.call_tool("fixture", "doesNotExist", {})

            assert result.success is False
            assert "not found" in result.error.lower()
        finally:
            await bridge.close()


@pytest.mark.asyncio
async def test_end_to_end_rescan_detects_no_duplicate_tools():
    """Rescanning the same page twice doesn't duplicate discovered tools
    (regression test for accumulated add_init_script wrapping)."""
    with TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "fixture.html"
        fixture_path.write_text(_FIXTURE_PAGE)
        url = fixture_path.as_uri()

        bridge = WebMCPBridge(headless=True, origins_allowlist=[url])
        try:
            await bridge.browser.initialize()
            await bridge.browser.page.add_init_script(_MODEL_CONTEXT_POLYFILL)

            first = await bridge.discover(url, origin_slug="fixture")
            second = await bridge.discover(url, origin_slug="fixture", force_rescan=True)

            assert len(first.tools) == 1
            assert len(second.tools) == 1
        finally:
            await bridge.close()
