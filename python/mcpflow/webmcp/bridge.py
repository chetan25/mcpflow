"""Main WebMCP bridge orchestrator."""

import logging
from typing import Optional
import json

from .browser import BrowserController
from .discovery import ToolDiscovery
from .translator import SchemaTranslator
from .security import SecurityManager
from .types import WebMCPManifest

logger = logging.getLogger(__name__)


class WebMCPBridge:
    """Main entry point for WebMCP bridge functionality."""

    def __init__(
        self,
        headless: bool = True,
        origins_allowlist: Optional[list[str]] = None,
        audit_dir: Optional[str] = None,
    ):
        """
        Initialize WebMCP bridge.

        Args:
            headless: Run browser in headless mode
            origins_allowlist: List of allowed origins (deny by default)
            audit_dir: Directory for audit logs
        """
        self.browser = BrowserController(headless=headless)
        self.discovery = ToolDiscovery(self.browser)
        self.translator = SchemaTranslator()
        self.security = SecurityManager(audit_dir=audit_dir)
        self.manifests = {}  # origin -> WebMCPManifest

        if origins_allowlist:
            self.security.set_allowed_origins(origins_allowlist)

        logger.info("WebMCP Bridge initialized")

    async def discover(self, url: str, origin_slug: Optional[str] = None) -> Optional[WebMCPManifest]:
        """
        Discover WebMCP tools on a page.

        Args:
            url: Full URL to discover on
            origin_slug: Short origin identifier (e.g., 'shop'). Defaults to domain from URL.

        Returns:
            WebMCPManifest with discovered tools
        """
        from urllib.parse import urlparse

        if not origin_slug:
            parsed = urlparse(url)
            origin_slug = parsed.netloc.replace("www.", "").replace(".", "_")

        # Check security policy
        if not self.security.check_origin_allowed(url):
            logger.error(f"Origin not allowed: {url}")
            return None

        # Initialize browser if needed
        if not self.browser.browser:
            await self.browser.initialize()

        # Discover tools
        manifest = await self.discovery.discover_tools(url, origin_slug)

        if manifest:
            # Sanitize tool descriptions
            for tool in manifest.tools:
                sanitized, has_risk = self.security.sanitize_tool_description(tool.description)
                if has_risk:
                    logger.warning(f"Tool {tool.name} has injection risk in description")
                tool.description = sanitized

            # Cache manifest
            self.manifests[origin_slug] = manifest

            # Log discovery
            tool_names = [t.name for t in manifest.tools]
            self.security.log_discovery(origin_slug, len(manifest.tools), tool_names)

        return manifest

    def get_mcp_tools(self, origin_slug: str) -> list[dict]:
        """
        Get MCP-formatted tool definitions for an origin.

        Args:
            origin_slug: Origin identifier

        Returns:
            List of MCP tool definitions
        """
        manifest = self.manifests.get(origin_slug)
        if not manifest:
            return []

        mcp_tools = []
        for tool in manifest.tools:
            mcp_tool = self.translator.translate_tool(tool, origin_slug)
            mcp_tools.append(mcp_tool)

        return mcp_tools

    async def close(self):
        """Clean up resources."""
        await self.browser.close()

    def get_streaming_executor(self):
        """
        Get access to the streaming executor for advanced use.

        Returns:
            StreamingToolExecutor instance
        """
        from .streaming import StreamingToolExecutor

        if not hasattr(self, "_streaming"):
            self._streaming = StreamingToolExecutor(self)
        return self._streaming

    def get_http_server(self, host: str = "127.0.0.1", port: int = 8000, use_sse: bool = True):
        """
        Get an HTTP server for remote access to the bridge.

        Args:
            host: Server host
            port: Server port
            use_sse: Enable Server-Sent Events streaming

        Returns:
            HTTPBridgeServer instance
        """
        from .http_transport import HTTPBridgeServer

        return HTTPBridgeServer(self, host=host, port=port, use_sse=use_sse)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
