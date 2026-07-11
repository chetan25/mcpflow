"""Playwright browser controller for WebMCP tool discovery."""

import logging
from typing import Optional
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

    async def inject_discovery_script(self) -> str:
        """
        Inject a content script that captures WebMCP tool registrations.

        Returns:
            JSON string with discovered tools
        """
        if not self.page:
            raise RuntimeError("Browser not initialized.")

        # Discovery script: hook navigator.modelContext.registerTool
        discovery_script = """
        window.__mcpflow_discovery = {
            tools: [],
            registerTool: function(name, inputSchema, description) {
                console.log('MCPFlow: Registering tool', name);
                this.tools.push({
                    name: name,
                    description: description || '',
                    input_schema: inputSchema || {}
                });
            }
        };

        // Hook if navigator.modelContext exists
        if (navigator.modelContext) {
            const original = navigator.modelContext.registerTool;
            if (original) {
                navigator.modelContext.registerTool = function(...args) {
                    window.__mcpflow_discovery.registerTool(...args);
                    return original.apply(this, args);
                };
            }
        }
        """

        await self.page.add_init_script(discovery_script)
        logger.debug("Discovery script injected")

        # Wait a bit for tools to register
        await self.page.wait_for_load_state("networkidle")

        # Return discovered tools
        result = await self.page.evaluate("window.__mcpflow_discovery?.tools || []")
        return result

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
        logger.debug("Browser closed")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
