"""Playwright browser controller for WebMCP tool discovery."""

import logging
from typing import Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BrowserController:
    """Manages Playwright browser instances for WebMCP discovery."""

    def __init__(self, headless: bool = True, timeout: int = 30000):
        """
        Initialize the browser controller.

        Args:
            headless: Whether to run browser in headless mode
            timeout: Page load timeout in milliseconds
        """
        self.headless = headless
        self.timeout = timeout
        self.browser = None
        self.context = None
        self.page = None
        self._playwright = None
        self._extra_playwrights = []  # (playwright, browser) pairs from create_context()

    async def initialize(self):
        """Start Playwright and create a browser instance."""
        from playwright.async_api import async_playwright

        self._playwright = async_playwright()
        p = await self._playwright.__aenter__()
        self.browser = await p.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()
        self.page.set_default_timeout(self.timeout)
        logger.debug("Browser initialized")

    async def navigate(self, url: str) -> bool:
        """
        Navigate to a URL and wait for page to load.

        Args:
            url: URL to navigate to

        Returns:
            True if navigation succeeded, False otherwise
        """
        if not self.page:
            raise RuntimeError("Browser not initialized. Call initialize() first.")

        try:
            await self.page.goto(url, wait_until="networkidle")
            logger.debug(f"Navigated to {url}")
            return True
        except Exception as e:
            logger.error(f"Navigation failed to {url}: {e}")
            return False

    async def prepare_discovery(self) -> None:
        """
        Install the WebMCP discovery hook via an init script.

        Playwright init scripts only apply to navigations that happen after
        they're added — so this MUST be called before navigate(), or the
        hook never sees the page's own registerTool() calls on that first
        load and discovery silently returns zero tools.
        """
        if not self.page:
            raise RuntimeError("Browser not initialized.")

        # Discovery script: hook navigator.modelContext.registerTool.
        # The real WebMCP API registers tools with a single definition object
        # ({name, description, inputSchema, execute}); we keep a reference to
        # each tool's `execute` callback so we can invoke it later via
        # call_tool(), not just read its schema.
        discovery_script = """
        window.__mcpflow_discovery = {
            tools: [],
            executors: {},
            registerTool: function(toolDef) {
                if (!toolDef || typeof toolDef !== 'object') {
                    return;
                }
                const name = toolDef.name;
                console.log('MCPFlow: Registering tool', name);
                this.tools.push({
                    name: name,
                    description: toolDef.description || '',
                    input_schema: toolDef.inputSchema || {}
                });
                if (typeof toolDef.execute === 'function') {
                    this.executors[name] = toolDef.execute;
                }
            },
            invoke: async function(name, args) {
                const fn = this.executors[name];
                if (!fn) {
                    throw new Error('No executor registered for tool: ' + name);
                }
                return await fn(args);
            }
        };

        // Hook if navigator.modelContext exists. Guarded so repeated
        // rescans (which accumulate multiple add_init_script calls on the
        // same page) don't wrap registerTool multiple times and duplicate
        // every registration.
        if (navigator.modelContext && !navigator.modelContext.__mcpflow_hooked) {
            const original = navigator.modelContext.registerTool;
            if (original) {
                navigator.modelContext.registerTool = function(toolDef) {
                    window.__mcpflow_discovery.registerTool(toolDef);
                    return original.call(this, toolDef);
                };
                navigator.modelContext.__mcpflow_hooked = true;
            }
        }
        """

        await self.page.add_init_script(discovery_script)
        logger.debug("Discovery script injected")

    async def get_discovered_tools(self) -> list:
        """
        Read back the tools captured by the discovery hook after navigation.

        Call this after navigate() (and after prepare_discovery() was called
        before that navigate()).

        Returns:
            List of discovered tool dicts (name, description, input_schema)
        """
        if not self.page:
            raise RuntimeError("Browser not initialized.")

        await self.page.wait_for_load_state("networkidle")
        result = await self.page.evaluate("window.__mcpflow_discovery?.tools || []")
        return result

    async def inject_discovery_script(self) -> list:
        """
        Backward-compatible convenience wrapper.

        Prefer calling prepare_discovery() before navigate() and
        get_discovered_tools() after — calling this method after navigate()
        (as ToolDiscovery now does) will miss tools registered during that
        page's initial load, since the hook won't exist yet at that point.
        """
        await self.prepare_discovery()
        return await self.get_discovered_tools()

    async def call_tool(self, tool_name: str, args: Optional[dict] = None) -> Any:
        """
        Invoke a previously-discovered WebMCP tool in the live page.

        Args:
            tool_name: Original (non-namespaced) tool name as registered on the page
            args: Tool arguments

        Returns:
            The tool's real return value from `navigator.modelContext`

        Raises:
            RuntimeError: If the browser isn't initialized, discovery was never
                injected, or the page has no executor registered for this tool
        """
        if not self.page:
            raise RuntimeError("Browser not initialized.")

        result = await self.page.evaluate(
            """async ([name, args]) => {
                const discovery = window.__mcpflow_discovery;
                if (!discovery) {
                    throw new Error('WebMCP discovery not injected on this page');
                }
                return await discovery.invoke(name, args);
            }""",
            [tool_name, args or {}],
        )
        logger.debug(f"Invoked tool {tool_name} -> {result!r}")
        return result

    async def create_context(
        self,
        headless: Optional[bool] = None,
        record_video: bool = False,
        extra_http_headers: Optional[dict] = None,
    ):
        """
        Create an independent Playwright browser context.

        Used by SessionProfileManager for headed login flows and for loading
        saved session profiles, independent of this controller's default
        navigate()/call_tool() context.

        Args:
            headless: Run this context's browser headless (defaults to this
                controller's `headless` setting)
            record_video: Record video of the session (debugging)
            extra_http_headers: Extra HTTP headers to apply to every request

        Returns:
            Playwright BrowserContext instance (caller is responsible for
            calling `await context.close()` when done)
        """
        from playwright.async_api import async_playwright

        use_headless = self.headless if headless is None else headless

        playwright = async_playwright()
        p = await playwright.__aenter__()
        browser = await p.chromium.launch(headless=use_headless)
        self._extra_playwrights.append((playwright, browser))

        context_kwargs: dict = {}
        if extra_http_headers:
            context_kwargs["extra_http_headers"] = extra_http_headers
        if record_video:
            context_kwargs["record_video_dir"] = "videos/"

        context = await browser.new_context(**context_kwargs)
        logger.debug(f"Created independent browser context (headless={use_headless})")
        return context

    async def screenshot(self, filename: str):
        """
        Take a screenshot of the current page.

        Args:
            filename: Path to save screenshot
        """
        if not self.page:
            raise RuntimeError("Browser not initialized.")

        await self.page.screenshot(path=filename)
        logger.debug(f"Screenshot saved to {filename}")

    async def get_page_content(self) -> str:
        """
        Get the current page content.

        Returns:
            Page HTML
        """
        if not self.page:
            raise RuntimeError("Browser not initialized.")

        return await self.page.content()

    async def close(self):
        """Close the browser and clean up resources."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.__aexit__(None, None, None)

        for playwright, browser in self._extra_playwrights:
            try:
                await browser.close()
            except Exception as e:
                logger.warning(f"Error closing extra browser context: {e}")
            try:
                await playwright.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing extra playwright instance: {e}")
        self._extra_playwrights = []

        logger.debug("Browser closed")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
