"""Main WebMCP bridge orchestrator."""

import logging
from typing import Any, Callable, Optional
import json

from .browser import BrowserController
from .cache import ManifestCache
from .discovery import ToolDiscovery
from .translator import SchemaTranslator
from .security import SecurityManager
from .session import SessionProfileManager, EncryptedSessionStore
from .types import WebMCPManifest, WebMCPTool, ToolCallResult

logger = logging.getLogger(__name__)


class WebMCPBridge:
    """Main entry point for WebMCP bridge functionality."""

    def __init__(
        self,
        headless: bool = True,
        origins_allowlist: Optional[list[str]] = None,
        audit_dir: Optional[str] = None,
        interceptor: Optional[Any] = None,
        policy_file: Optional[str] = None,
        cache_ttl_seconds: int = 3600,
        multi_origin_config: Optional[Any] = None,
    ):
        """
        Initialize WebMCP bridge.

        Args:
            headless: Run browser in headless mode
            origins_allowlist: List of allowed origins (deny by default)
            audit_dir: Directory for audit logs
            interceptor: Pluggable security interceptor implementing
                InterceptorProtocol (e.g. `TrussInterceptor`). Defaults to
                `DefaultInterceptor`, which uses this bridge's built-in
                SecurityManager/PolicyEnforcer.
            policy_file: Path to a per-origin security policy YAML file. When
                given, creates `self.policy_enforcer` for fine-grained
                allow/deny/destructive/rate-limit rules.
            cache_ttl_seconds: Default manifest cache TTL; see discover()'s
                `force_rescan` to bypass the cache for a single call.
            multi_origin_config: Optional `MultiOriginConfig` used to look up
                per-origin `require_headed_for` tool patterns before invoking
                a tool (see call_tool()).
        """
        self.browser = BrowserController(headless=headless)
        self.discovery = ToolDiscovery(self.browser)
        self.translator = SchemaTranslator()
        self.security = SecurityManager(audit_dir=audit_dir)
        self.session_manager = SessionProfileManager(store=EncryptedSessionStore())
        self.cache = ManifestCache(default_ttl_seconds=cache_ttl_seconds)
        self.multi_origin_config = multi_origin_config
        self.manifests = {}  # origin -> WebMCPManifest
        self._origin_urls = {}  # origin_slug -> last-discovered full URL
        self._tools_changed_listeners: list[Callable[[str, WebMCPManifest], None]] = []

        self.policy_enforcer = None
        if policy_file:
            from .policy import PolicyFile, PolicyEnforcer

            self.policy_enforcer = PolicyEnforcer(PolicyFile(policy_file))

        if interceptor is not None:
            self.interceptor = interceptor
        else:
            from .interceptor import DefaultInterceptor

            self.interceptor = DefaultInterceptor(self)

        if origins_allowlist:
            self.security.set_allowed_origins(origins_allowlist)

        logger.info("WebMCP Bridge initialized")

    async def discover(
        self,
        url: str,
        origin_slug: Optional[str] = None,
        session_profile: Optional[str] = None,
        fallback: bool = False,
        force_rescan: bool = False,
        cache_ttl_seconds: Optional[int] = None,
    ) -> Optional[WebMCPManifest]:
        """
        Discover WebMCP tools on a page.

        Args:
            url: Full URL to discover on
            origin_slug: Short origin identifier (e.g., 'shop'). Defaults to domain from URL.
            session_profile: Name of a saved SessionProfile to apply before
                navigating, so discovery/calls run inside an authenticated
                session instead of a fresh anonymous one.
            fallback: Try the declarative fallback tier (JSON-LD/forms/llms.txt)
                if no imperative WebMCP tools are found.
            force_rescan: Bypass the manifest cache and re-navigate/re-scan
                even if a fresh cached manifest exists for this origin.
            cache_ttl_seconds: Override this bridge's default cache TTL for
                the manifest produced by this call.

        Returns:
            WebMCPManifest with discovered tools
        """
        from urllib.parse import urlparse

        if not origin_slug:
            parsed = urlparse(url)
            origin_slug = parsed.netloc.replace("www.", "").replace(".", "_")

        self._origin_urls[origin_slug] = url

        if not force_rescan:
            cached = self.cache.get(origin_slug)
            if cached:
                logger.debug(f"Using cached manifest for {origin_slug}")
                self.manifests[origin_slug] = cached
                return cached

        # Check security policy
        if not self.security.check_origin_allowed(url):
            logger.error(f"Origin not allowed: {url}")
            return None

        # Initialize browser if needed
        if not self.browser.browser:
            await self.browser.initialize()

        if session_profile:
            applied = await self.session_manager.apply_profile_to_context(
                session_profile, self.browser.context
            )
            if not applied:
                logger.warning(
                    f"Session profile '{session_profile}' not found or failed to apply"
                )

        # Discover tools
        prior_manifest = self.manifests.get(origin_slug)
        manifest = await self.discovery.discover_tools(url, origin_slug, fallback=fallback)

        if manifest:
            # Sanitize tool descriptions
            for tool in manifest.tools:
                sanitized, has_risk = self.security.sanitize_tool_description(tool.description)
                if has_risk:
                    logger.warning(f"Tool {tool.name} has injection risk in description")
                tool.description = sanitized

            # Cache manifest
            self.manifests[origin_slug] = manifest
            self.cache.set(origin_slug, manifest, ttl_seconds=cache_ttl_seconds)

            # Log discovery
            tool_names = [t.name for t in manifest.tools]
            self.security.log_discovery(origin_slug, len(manifest.tools), tool_names)

            # Notify listeners (e.g. the MCP server facade) if the tool set
            # for this origin changed, so they can emit
            # notifications/tools/list_changed
            if prior_manifest is not None:
                prior_names = {t.name for t in prior_manifest.tools}
                new_names = {t.name for t in manifest.tools}
                if prior_names != new_names:
                    for listener in self._tools_changed_listeners:
                        try:
                            listener(origin_slug, manifest)
                        except Exception as e:
                            logger.warning(f"tools_changed listener failed: {e}")

        return manifest

    def on_tools_changed(self, callback: Callable[[str, WebMCPManifest], None]) -> None:
        """
        Register a callback invoked when a rescan detects that an origin's
        tool set changed (tools added/removed since the last discovery).

        Args:
            callback: Callable invoked as callback(origin_slug, manifest)
        """
        self._tools_changed_listeners.append(callback)

    async def rescan(self, origin_slug: str, url: Optional[str] = None, **kwargs) -> Optional[WebMCPManifest]:
        """
        Force a re-scan of a previously-discovered origin.

        Args:
            origin_slug: Origin identifier to rescan
            url: Full URL to navigate to (defaults to the URL used at the
                last discovery of this origin)
            **kwargs: Forwarded to discover() (session_profile, fallback, etc.)

        Returns:
            The freshly-discovered WebMCPManifest

        Raises:
            ValueError: If no URL is known for this origin and none was given
        """
        url = url or self._origin_urls.get(origin_slug)
        if not url:
            raise ValueError(f"No known URL for origin '{origin_slug}'; pass url= explicitly")

        return await self.discover(url, origin_slug=origin_slug, force_rescan=True, **kwargs)

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

    def _resolve_tool(self, origin_slug: str, tool_name: str) -> Optional[WebMCPTool]:
        """
        Find a discovered tool by its namespaced or original name.

        Args:
            origin_slug: Origin identifier
            tool_name: Tool name, namespaced ({origin}__{tool}) or original

        Returns:
            WebMCPTool if found, None otherwise
        """
        manifest = self.manifests.get(origin_slug)
        if not manifest:
            return None

        for tool in manifest.tools:
            namespaced_name = f"{origin_slug}__{tool.name}".replace(".", "_").replace("-", "_")
            if namespaced_name == tool_name or tool.name == tool_name:
                return tool

        return None

    async def call_tool(self, origin_slug: str, tool_name: str, args: dict) -> ToolCallResult:
        """
        Invoke a discovered WebMCP tool for real, in the live browser page.

        This is the single entry point that actually executes a tool against
        navigator.modelContext — callers (streaming, server_facade, the
        registry) should go through this rather than talking to the browser
        directly.

        Args:
            origin_slug: Origin identifier (as used by discover())
            tool_name: Tool name, namespaced ({origin}__{tool}) or original
            args: Tool arguments

        Returns:
            ToolCallResult with the real success/result/error
        """
        if origin_slug not in self.manifests:
            error = f"Origin not discovered: {origin_slug}"
            self.security.log_tool_call(origin_slug, tool_name, False, error=error)
            return ToolCallResult(success=False, error=error)

        tool = self._resolve_tool(origin_slug, tool_name)
        if not tool:
            error = f"Tool not found: {tool_name}"
            self.security.log_tool_call(origin_slug, tool_name, False, error=error)
            return ToolCallResult(success=False, error=error)

        # MultiOriginConfig is keyed by the full origin URL, not the slug used
        # everywhere else in the bridge, so resolve slug -> URL before lookup.
        origin_url_for_config = self._origin_urls.get(origin_slug, origin_slug)
        if self.multi_origin_config and self.multi_origin_config.requires_headed(
            origin_url_for_config, tool.name
        ):
            if self.browser.headless:
                error = (
                    f"Tool '{tool.name}' matches a require_headed_for pattern for "
                    f"'{origin_slug}' but the bridge is running headless; refusing "
                    "to call it without a visible browser window"
                )
                self.security.log_tool_call(origin_slug, tool.name, False, error=error)
                return ToolCallResult(success=False, error=error)

        allowed, reason = await self.interceptor.before_tool_call(origin_slug, tool.name, args)
        if not allowed:
            error = reason or f"Tool call blocked by interceptor: {tool.name}"
            self.security.log_tool_call(origin_slug, tool.name, False, error=error)
            return ToolCallResult(success=False, error=error)

        try:
            result = await self.browser.call_tool(tool.name, args)
            await self.interceptor.after_tool_call(origin_slug, tool.name, args, result)
            self.security.log_tool_call(origin_slug, tool.name, True)
            return ToolCallResult(success=True, result=result)
        except Exception as e:
            logger.error(f"Tool call failed: {origin_slug}/{tool.name}: {e}")
            await self.interceptor.after_tool_call(
                origin_slug, tool.name, args, None, error=str(e)
            )
            self.security.log_tool_call(origin_slug, tool.name, False, error=str(e))
            return ToolCallResult(success=False, error=str(e))

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
