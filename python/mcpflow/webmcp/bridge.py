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
        enable_result_diffing: bool = False,
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
            enable_result_diffing: Capture page state before/after each real
                tool call and attach a before/after diff to ToolCallResult.
                Off by default since it costs an extra page snapshot per call.
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
        self._recent_results: list = []  # (origin_slug, result) - for cross-origin chain guard
        self._recent_results_limit = 20
        self.enable_result_diffing = enable_result_diffing

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

        # Each origin gets its own dedicated page/context so concurrent tool
        # calls across different origins can run in parallel rather than
        # serializing through one shared page (spec section 5, multi-tab
        # parallelism).
        page = await self.browser.get_page_for_origin(origin_slug)

        if session_profile:
            applied = await self.session_manager.apply_profile_to_context(
                session_profile, page.context
            )
            if not applied:
                logger.warning(
                    f"Session profile '{session_profile}' not found or failed to apply"
                )

        # Discover tools
        prior_manifest = self.manifests.get(origin_slug)
        manifest = await self.discovery.discover_tools(
            url, origin_slug, fallback=fallback, page=page
        )

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

    @staticmethod
    def _flatten_leaf_values(obj) -> list:
        """Flatten a nested dict/list into its scalar leaf values.

        Used by the cross-origin chain guard as a lightweight heuristic for
        detecting when data from one origin's tool result is being passed
        into a call on another origin - the exfiltration path the guard
        exists for (spec section 3.6.6). This is exact-value matching, not
        full taint tracking; it catches the common case of an agent copying
        a returned value straight into a follow-up call.
        """
        values = []
        if isinstance(obj, dict):
            for v in obj.values():
                values.extend(WebMCPBridge._flatten_leaf_values(v))
        elif isinstance(obj, list):
            for v in obj:
                values.extend(WebMCPBridge._flatten_leaf_values(v))
        elif isinstance(obj, (str, int, float)) and obj != "":
            values.append(obj)
        return values

    def _detect_cross_origin_source(self, target_origin: str, args: dict) -> Optional[str]:
        """
        Check whether any argument value matches a value recently returned
        by a tool call on a DIFFERENT origin.

        Returns:
            The source origin slug if a match is found, else None
        """
        arg_values = set(self._flatten_leaf_values(args))
        if not arg_values:
            return None

        for source_origin, result in reversed(self._recent_results):
            if source_origin == target_origin:
                continue
            result_values = set(self._flatten_leaf_values(result))
            if arg_values & result_values:
                return source_origin

        return None

    def _record_result(self, origin_slug: str, result) -> None:
        """Record a tool result for later cross-origin detection."""
        self._recent_results.append((origin_slug, result))
        if len(self._recent_results) > self._recent_results_limit:
            self._recent_results.pop(0)

    async def _capture_diff_state(self, page) -> Optional[dict]:
        """Capture a normalized page-state snapshot for result diffing."""
        from .result_diffing import DOMCapture

        try:
            page_json = await self.browser.capture_page_json(page=page)
        except Exception as e:
            logger.warning(f"Could not capture page state for diffing: {e}")
            return None

        # include_html=True so a diff catches real DOM mutations (e.g. a
        # cart count updating) - the forms/inputs/buttons-only view misses
        # most real WebMCP tool effects, which change ordinary page content.
        return DOMCapture.capture_state(page_json, include_html=True, include_cookies=False)

    async def _compute_result_diff(
        self, before_state: dict, tool_name: str, origin_slug: str, result: Any, page
    ) -> Optional[dict]:
        """Capture the after-state and compute a before/after diff."""
        from .result_diffing import ResultDiffer

        after_state = await self._capture_diff_state(page)
        if after_state is None:
            return None

        state_diff = ResultDiffer.diff_dicts(before_state, after_state, tool_name, origin_slug, result)
        return state_diff.to_dict()

    async def _invoke_tool(self, tool: WebMCPTool, args: dict, page) -> Any:
        """
        Dispatch a tool call based on how it was discovered.

        Real WebMCP tools (imperative) have a captured `execute` callback.
        Declarative-tier tools (forms, JSON-LD Actions with an EntryPoint)
        have no such callback, so they're invoked differently - or, if
        genuinely uncallable (llms.txt, JSON-LD Actions with no EntryPoint),
        rejected with a clear reason rather than silently attempting an
        imperative call that could never work.
        """
        invocation = tool.invocation or {"type": "imperative"}
        invocation_type = invocation.get("type", "imperative")

        if invocation_type == "unsupported":
            raise RuntimeError(
                invocation.get("reason", "This tool has no callable endpoint")
            )

        if invocation_type == "form":
            return await self.browser.submit_form(invocation["selector"], args, page=page)

        if invocation_type == "json_ld_entrypoint":
            return await self.browser.call_json_ld_entrypoint(
                invocation["url_template"], invocation.get("http_method", "GET"), args, page=page
            )

        return await self.browser.call_tool(tool.name, args, page=page)

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

        source_origin = self._detect_cross_origin_source(origin_slug, args)
        if source_origin:
            cross_origin_allowed = await self.interceptor.cross_origin_check(
                source_origin, origin_slug, tool.name, data_preview=json.dumps(args)[:200]
            )
            if not cross_origin_allowed:
                error = (
                    f"Cross-origin data flow from '{source_origin}' to '{origin_slug}' "
                    f"blocked for tool '{tool.name}'"
                )
                self.security.log_tool_call(origin_slug, tool.name, False, error=error)
                return ToolCallResult(success=False, error=error)

        allowed, reason = await self.interceptor.before_tool_call(origin_slug, tool.name, args)
        if not allowed:
            error = reason or f"Tool call blocked by interceptor: {tool.name}"
            self.security.log_tool_call(origin_slug, tool.name, False, error=error)
            return ToolCallResult(success=False, error=error)

        page = await self.browser.get_page_for_origin(origin_slug)

        try:
            before_state = None
            if self.enable_result_diffing:
                before_state = await self._capture_diff_state(page)

            result = await self._invoke_tool(tool, args, page)
            self._record_result(origin_slug, result)

            diff = None
            if self.enable_result_diffing and before_state is not None:
                diff = await self._compute_result_diff(
                    before_state, tool.name, origin_slug, result, page
                )

            await self.interceptor.after_tool_call(origin_slug, tool.name, args, result)
            self.security.log_tool_call(origin_slug, tool.name, True)
            return ToolCallResult(success=True, result=result, diff=diff)
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
