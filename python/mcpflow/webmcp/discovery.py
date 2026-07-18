"""WebMCP tool discovery logic."""

import logging
import hashlib
from typing import Optional
from datetime import datetime

from .types import WebMCPTool, WebMCPManifest

logger = logging.getLogger(__name__)


class ToolDiscovery:
    """Handles discovery of WebMCP tools on web pages."""

    def __init__(self, browser_controller):
        """
        Initialize tool discovery.

        Args:
            browser_controller: BrowserController instance
        """
        self.browser = browser_controller

    async def discover_tools(
        self, url: str, origin: str, fallback: bool = False
    ) -> Optional[WebMCPManifest]:
        """
        Discover WebMCP tools on a page.

        Args:
            url: Full URL to navigate to
            origin: Origin slug (e.g., 'shop.example.com')
            fallback: If the imperative WebMCP scan finds no tools, also try
                the declarative fallback tier (JSON-LD actions, annotated
                HTML forms, /llms.txt) so non-WebMCP sites still yield usable
                tool manifests.

        Returns:
            WebMCPManifest with discovered tools, or None if discovery failed
        """
        # Install the discovery hook BEFORE navigating: Playwright init
        # scripts only take effect on navigations that happen after they're
        # added, so this order is required to catch tools registered during
        # the page's initial load.
        try:
            await self.browser.prepare_discovery()
        except Exception as e:
            logger.error(f"Discovery script preparation failed: {e}")
            return None

        if not await self.browser.navigate(url):
            logger.error(f"Failed to navigate to {url}")
            return None

        try:
            tools_list = await self.browser.get_discovered_tools()
        except Exception as e:
            logger.error(f"Discovery read-back failed: {e}")
            return None

        tools_list = tools_list or []

        if not tools_list and fallback:
            logger.info(
                f"No WebMCP tools found on {url}; trying declarative fallback tier"
            )
            from .declarative_discovery import DeclarativeDiscovery

            tools_list = await DeclarativeDiscovery.discover_all(self.browser.page, url)
            # discover_from_llms_txt navigates to {origin}/llms.txt; return to
            # the original page so content hashing and later tool calls see
            # the intended page.
            await self.browser.navigate(url)

        if not tools_list:
            logger.warning(f"No tools discovered on {url}")
            return WebMCPManifest(origin=origin, tools=[])

        # Convert to WebMCPTool objects
        tools = []
        for tool_data in tools_list:
            try:
                tool = WebMCPTool(
                    name=tool_data.get("name", "unknown"),
                    description=tool_data.get("description", ""),
                    input_schema=tool_data.get("input_schema", {}),
                    origin=origin,
                )
                tools.append(tool)
                logger.debug(f"Discovered tool: {tool.name}")
            except Exception as e:
                logger.error(f"Failed to parse tool: {e}")
                continue

        # Generate content hash for change detection
        page_content = await self.browser.get_page_content()
        content_hash = hashlib.sha256(page_content.encode()).hexdigest()

        manifest = WebMCPManifest(
            origin=origin,
            tools=tools,
            discovered_at=datetime.utcnow(),
            content_hash=content_hash,
        )

        logger.info(f"Discovery complete: {len(tools)} tools found on {origin}")
        return manifest

    def filter_by_security_policy(self, manifest: WebMCPManifest, allowed_patterns: list[str]) -> WebMCPManifest:
        """
        Filter tools based on security allowlist patterns.

        Args:
            manifest: Discovered manifest
            allowed_patterns: List of allowed tool name patterns (supports wildcards)

        Returns:
            Filtered manifest
        """
        if "*" in allowed_patterns:
            return manifest  # Allow all

        from fnmatch import fnmatch

        filtered_tools = []
        for tool in manifest.tools:
            if any(fnmatch(tool.name, pattern) for pattern in allowed_patterns):
                filtered_tools.append(tool)
            else:
                logger.debug(f"Tool {tool.name} filtered by policy")

        filtered_manifest = WebMCPManifest(
            origin=manifest.origin,
            tools=filtered_tools,
            discovered_at=manifest.discovered_at,
            content_hash=manifest.content_hash,
        )
        return filtered_manifest
