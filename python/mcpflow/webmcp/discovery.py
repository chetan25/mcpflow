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

    async def discover_tools(self, url: str, origin: str) -> Optional[WebMCPManifest]:
        """
        Discover WebMCP tools on a page.

        Args:
            url: Full URL to navigate to
            origin: Origin slug (e.g., 'shop.example.com')

        Returns:
            WebMCPManifest with discovered tools, or None if discovery failed
        """
        # Navigate to the page
        if not await self.browser.navigate(url):
            logger.error(f"Failed to navigate to {url}")
            return None

        # Inject discovery script and get tools
        try:
            tools_list = await self.browser.inject_discovery_script()
        except Exception as e:
            logger.error(f"Discovery injection failed: {e}")
            return None

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
