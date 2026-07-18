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
            # Each origin gets its own dedicated page (for multi-tab
            # concurrency); install the polyfill on that same page before the
            # bridge's own discovery hook (added inside discover() ->
            # prepare_discovery()), so the hook has a real registerTool to wrap.
            page = await bridge.browser.get_page_for_origin("fixture")
            await page.add_init_script(_MODEL_CONTEXT_POLYFILL)

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
            page = await bridge.browser.get_page_for_origin("fixture")
            await page.add_init_script(_MODEL_CONTEXT_POLYFILL)
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
            page = await bridge.browser.get_page_for_origin("fixture")
            await page.add_init_script(_MODEL_CONTEXT_POLYFILL)

            first = await bridge.discover(url, origin_slug="fixture")
            second = await bridge.discover(url, origin_slug="fixture", force_rescan=True)

            assert len(first.tools) == 1
            assert len(second.tools) == 1
        finally:
            await bridge.close()


@pytest.mark.asyncio
async def test_end_to_end_multi_origin_pages_are_independent():
    """Each origin gets its own dedicated Playwright page/context, so
    concurrent tool calls across different origins don't serialize through
    one shared page (spec section 5, multi-tab parallelism)."""
    with TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "fixture.html"
        fixture_path.write_text(_FIXTURE_PAGE)
        url = fixture_path.as_uri()

        bridge = WebMCPBridge(headless=True, origins_allowlist=[url])
        try:
            page_a = await bridge.browser.get_page_for_origin("origin-a")
            page_b = await bridge.browser.get_page_for_origin("origin-b")

            assert page_a is not page_b
            assert page_a.context is not page_b.context

            # Same origin returns the same page on repeated calls
            page_a_again = await bridge.browser.get_page_for_origin("origin-a")
            assert page_a_again is page_a

            await page_a.add_init_script(_MODEL_CONTEXT_POLYFILL)
            await page_b.add_init_script(_MODEL_CONTEXT_POLYFILL)

            import asyncio

            manifest_a, manifest_b = await asyncio.gather(
                bridge.discover(url, origin_slug="origin-a"),
                bridge.discover(url, origin_slug="origin-b"),
            )

            assert len(manifest_a.tools) == 1
            assert len(manifest_b.tools) == 1
        finally:
            await bridge.close()


@pytest.mark.asyncio
async def test_end_to_end_declarative_form_invocation():
    """A form-based declarative tool (no real WebMCP execute callback) can
    still be invoked end-to-end via the fallback tier's form-fill-and-submit
    path."""
    form_fixture = """
    <!DOCTYPE html>
    <html>
    <head><title>Form fixture</title></head>
    <body>
    <form data-tool-name="searchItems" data-tool-description="Search items" method="GET" action="results.html">
        <input type="text" name="query" />
        <button type="submit">Search</button>
    </form>
    </body>
    </html>
    """
    with TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "form_fixture.html"
        fixture_path.write_text(form_fixture)
        (Path(tmpdir) / "results.html").write_text("<html><body>Results page</body></html>")
        url = fixture_path.as_uri()

        bridge = WebMCPBridge(headless=True, origins_allowlist=[url])
        try:
            manifest = await bridge.discover(url, origin_slug="formsite", fallback=True)

            assert manifest is not None
            assert len(manifest.tools) == 1
            assert manifest.tools[0].name == "searchItems"
            assert manifest.tools[0].invocation["type"] == "form"

            result = await bridge.call_tool("formsite", "searchItems", {"query": "widgets"})

            assert result.success is True, result.error
            assert "results.html" in result.result["url"]
        finally:
            await bridge.close()


@pytest.mark.asyncio
async def test_end_to_end_result_diffing_captures_real_change():
    """With result diffing enabled, calling a tool that mutates the DOM
    produces a real before/after diff, not a no-op."""
    mutating_fixture = """
    <!DOCTYPE html>
    <html>
    <head><title>Mutating fixture</title></head>
    <body>
    <div id="cart-count">0</div>
    <script>
    navigator.modelContext.registerTool({
        name: "addToCart",
        description: "Add an item to the cart",
        inputSchema: {type: "object", properties: {}},
        execute: async function(args) {
            const el = document.getElementById('cart-count');
            el.textContent = String(Number(el.textContent) + 1);
            return { added: true };
        }
    });
    </script>
    </body>
    </html>
    """
    with TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "mutating.html"
        fixture_path.write_text(mutating_fixture)
        url = fixture_path.as_uri()

        bridge = WebMCPBridge(
            headless=True, origins_allowlist=[url], enable_result_diffing=True
        )
        try:
            page = await bridge.browser.get_page_for_origin("mutating")
            await page.add_init_script(_MODEL_CONTEXT_POLYFILL)
            await bridge.discover(url, origin_slug="mutating")

            result = await bridge.call_tool("mutating", "addToCart", {})

            assert result.success is True, result.error
            assert result.diff is not None
            assert len(result.diff["changes"]) > 0
        finally:
            await bridge.close()
