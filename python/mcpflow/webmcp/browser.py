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
        self._origin_pages = {}  # origin_slug -> Page, for concurrent multi-origin tool calls

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

    async def get_page_for_origin(self, origin_slug: str):
        """
        Get (creating if needed) a dedicated page + context for an origin.

        Each origin gets its own browser context, so concurrent tool calls
        across DIFFERENT origins run truly in parallel instead of
        serializing through one shared page - separate Playwright page
        objects, separate cookie jars, matching the "one profile per trust
        domain" isolation principle (spec section 3.4). A single origin's
        own calls still serialize against each other, since a real browser
        tab can only do one thing at a time anyway.

        Args:
            origin_slug: Origin identifier

        Returns:
            Playwright Page dedicated to this origin
        """
        if origin_slug in self._origin_pages:
            return self._origin_pages[origin_slug]

        if not self.browser:
            await self.initialize()

        context = await self.browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(self.timeout)

        self._origin_pages[origin_slug] = page
        logger.debug(f"Created dedicated page for origin: {origin_slug}")
        return page

    async def close_origin_page(self, origin_slug: str) -> bool:
        """
        Close and forget a specific origin's dedicated page/context.

        Args:
            origin_slug: Origin identifier

        Returns:
            True if a page was found and closed, False otherwise
        """
        page = self._origin_pages.pop(origin_slug, None)
        if not page:
            return False

        context = page.context
        await page.close()
        await context.close()
        logger.debug(f"Closed dedicated page for origin: {origin_slug}")
        return True

    async def navigate(self, url: str, page: Optional[Any] = None) -> bool:
        """
        Navigate to a URL and wait for page to load.

        Args:
            url: URL to navigate to
            page: Page to navigate (defaults to this controller's default
                page; pass the result of get_page_for_origin() for
                per-origin concurrency)

        Returns:
            True if navigation succeeded, False otherwise
        """
        page = page or self.page
        if not page:
            raise RuntimeError("Browser not initialized. Call initialize() first.")

        try:
            await page.goto(url, wait_until="networkidle")
            logger.debug(f"Navigated to {url}")
            return True
        except Exception as e:
            logger.error(f"Navigation failed to {url}: {e}")
            return False

    async def prepare_discovery(self, page: Optional[Any] = None) -> None:
        """
        Install the WebMCP discovery hook via an init script.

        Playwright init scripts only apply to navigations that happen after
        they're added — so this MUST be called before navigate(), or the
        hook never sees the page's own registerTool() calls on that first
        load and discovery silently returns zero tools.

        Args:
            page: Page to install the hook on (defaults to this controller's
                default page)
        """
        page = page or self.page
        if not page:
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

        await page.add_init_script(discovery_script)
        logger.debug("Discovery script injected")

    async def get_discovered_tools(self, page: Optional[Any] = None) -> list:
        """
        Read back the tools captured by the discovery hook after navigation.

        Call this after navigate() (and after prepare_discovery() was called
        before that navigate()) on the same page.

        Args:
            page: Page to read from (defaults to this controller's default page)

        Returns:
            List of discovered tool dicts (name, description, input_schema)
        """
        page = page or self.page
        if not page:
            raise RuntimeError("Browser not initialized.")

        await page.wait_for_load_state("networkidle")
        result = await page.evaluate("window.__mcpflow_discovery?.tools || []")
        return result

    async def inject_discovery_script(self) -> list:
        """
        Backward-compatible convenience wrapper operating on the default page.

        Prefer calling prepare_discovery() before navigate() and
        get_discovered_tools() after — calling this method after navigate()
        (as ToolDiscovery now does) will miss tools registered during that
        page's initial load, since the hook won't exist yet at that point.
        """
        await self.prepare_discovery()
        return await self.get_discovered_tools()

    async def call_tool(
        self, tool_name: str, args: Optional[dict] = None, page: Optional[Any] = None
    ) -> Any:
        """
        Invoke a previously-discovered WebMCP tool in the live page.

        Args:
            tool_name: Original (non-namespaced) tool name as registered on the page
            args: Tool arguments
            page: Page the tool was discovered on (defaults to this
                controller's default page)

        Returns:
            The tool's real return value from `navigator.modelContext`

        Raises:
            RuntimeError: If the browser isn't initialized, discovery was never
                injected, or the page has no executor registered for this tool
        """
        page = page or self.page
        if not page:
            raise RuntimeError("Browser not initialized.")

        result = await page.evaluate(
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

    async def submit_form(
        self, selector: str, args: dict, page: Optional[Any] = None
    ) -> dict:
        """
        Fill and submit a declarative-tier form-based tool.

        This is best-effort: form-synthesized tools are the fallback tier
        for non-WebMCP sites, not a guaranteed-robust automation mechanism.

        Args:
            selector: CSS selector identifying the form (from its
                data-tool-name attribute)
            args: Values to fill into the form's named inputs
            page: Page the form was discovered on (defaults to this
                controller's default page)

        Returns:
            dict with the resulting page url and title after submission

        Raises:
            RuntimeError: If the browser isn't initialized or the form isn't found
        """
        page = page or self.page
        if not page:
            raise RuntimeError("Browser not initialized.")

        form = page.locator(selector)
        if await form.count() == 0:
            raise RuntimeError(f"Form not found for selector: {selector}")

        for field_name, value in args.items():
            field = form.locator(f'[name="{field_name}"]')
            if await field.count() == 0:
                continue
            await field.first.fill(str(value))

        try:
            async with page.expect_navigation(wait_until="networkidle", timeout=5000):
                await form.evaluate(
                    "form => form.requestSubmit ? form.requestSubmit() : form.submit()"
                )
        except Exception:
            logger.debug("Form submission did not trigger a navigation within timeout")

        return {"url": page.url, "title": await page.title()}

    async def call_json_ld_entrypoint(
        self, url_template: str, http_method: str, args: dict, page: Optional[Any] = None
    ) -> dict:
        """
        Invoke a schema.org Action's EntryPoint by substituting args into its
        urlTemplate and fetching it inside the page, so the user's session
        cookies apply automatically (matching WebMCP's "browser session is
        the credential" model).

        Note: substitution here handles the common `{param}` / `{?param}`
        forms seen in schema.org examples, not the full RFC 6570 URI
        Template grammar.

        Args:
            url_template: schema.org EntryPoint urlTemplate
            http_method: HTTP method from the EntryPoint (defaults to GET)
            args: Values to substitute into the template
            page: Page to fetch from (defaults to this controller's default page)

        Returns:
            dict with the response status and parsed/text body

        Raises:
            RuntimeError: If the browser isn't initialized
        """
        page = page or self.page
        if not page:
            raise RuntimeError("Browser not initialized.")

        url = url_template
        for key, value in args.items():
            url = url.replace("{" + key + "}", str(value)).replace(
                "{?" + key + "}", f"?{key}={value}"
            )

        result = await page.evaluate(
            """async ([url, method]) => {
                const response = await fetch(url, { method: method || 'GET' });
                const text = await response.text();
                let body = text;
                try { body = JSON.parse(text); } catch (e) {}
                return { status: response.status, body: body };
            }""",
            [url, http_method or "GET"],
        )
        return result

    async def capture_page_json(self, page: Optional[Any] = None) -> dict:
        """
        Capture a lightweight JSON snapshot of the current page for result diffing.

        Args:
            page: Page to capture (defaults to this controller's default page)

        Returns:
            dict with url, title, forms, inputs, buttons, html, and cookies -
            shaped for DOMCapture.capture_state()
        """
        page = page or self.page
        if not page:
            raise RuntimeError("Browser not initialized.")

        data = await page.evaluate(
            """() => {
                const forms = Array.from(document.forms).map(f => f.name || f.id || '');
                const inputs = Array.from(document.querySelectorAll('input')).map(i => ({
                    name: i.name, value: i.value, type: i.type,
                }));
                const buttons = Array.from(document.querySelectorAll('button')).map(
                    b => b.textContent.trim()
                );
                return {
                    url: window.location.href,
                    title: document.title,
                    forms: forms,
                    inputs: inputs,
                    buttons: buttons,
                    html: document.documentElement.outerHTML,
                };
            }"""
        )

        try:
            data["cookies"] = await page.context.cookies()
        except Exception as e:
            logger.warning(f"Could not capture cookies for page snapshot: {e}")
            data["cookies"] = []

        return data

    async def screenshot(self, filename: str, page: Optional[Any] = None):
        """
        Take a screenshot of the current page.

        Args:
            filename: Path to save screenshot
            page: Page to screenshot (defaults to this controller's default page)
        """
        page = page or self.page
        if not page:
            raise RuntimeError("Browser not initialized.")

        await page.screenshot(path=filename)
        logger.debug(f"Screenshot saved to {filename}")

    async def get_page_content(self, page: Optional[Any] = None) -> str:
        """
        Get the current page content.

        Args:
            page: Page to read (defaults to this controller's default page)

        Returns:
            Page HTML
        """
        page = page or self.page
        if not page:
            raise RuntimeError("Browser not initialized.")

        return await page.content()

    async def close(self):
        """Close the browser and clean up resources."""
        for origin_slug in list(self._origin_pages.keys()):
            await self.close_origin_page(origin_slug)

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
