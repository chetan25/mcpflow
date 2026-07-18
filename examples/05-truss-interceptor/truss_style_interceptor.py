"""Illustrative example of a production-grade InterceptorProtocol implementation.

Truss (https://github.com/<org>/truss - a separate project, not an mcpflow
dependency) is the intended production interceptor referenced in the WebMCP
bridge spec: `WebMCPBridge(interceptor=TrussInterceptor(manifest="scope.yaml"))`.
Since Truss is an external project this example doesn't depend on it - instead
it implements the exact same seam (InterceptorProtocol) with a small,
self-contained scope-manifest model, so you can see precisely what a
production interceptor needs to provide and swap in a real one later.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ScopeManifest:
    """A minimal stand-in for a Truss-style scope manifest.

    Real manifests would be loaded from YAML (e.g. "scope.yaml") and support
    much richer rules; this is just enough to demonstrate the interceptor
    seam actually gating decisions.
    """

    def __init__(self, allowed_tool_patterns: List[str], allowed_cross_origin_pairs: Optional[List[tuple]] = None):
        self.allowed_tool_patterns = allowed_tool_patterns
        self.allowed_cross_origin_pairs = set(allowed_cross_origin_pairs or [])

    def allows_tool(self, tool_name: str) -> bool:
        from fnmatch import fnmatch

        return any(fnmatch(tool_name, pattern) for pattern in self.allowed_tool_patterns)

    def allows_cross_origin(self, source_origin: str, target_origin: str) -> bool:
        return (source_origin, target_origin) in self.allowed_cross_origin_pairs


class ExampleTrussStyleInterceptor:
    """
    Example production-shaped interceptor implementing InterceptorProtocol.

    A real Truss integration would replace this class entirely - the point
    of InterceptorProtocol is that mcpflow never needs to know Truss exists.
    Pass an instance of this (or a real TrussInterceptor) to WebMCPBridge:

        bridge = WebMCPBridge(
            interceptor=ExampleTrussStyleInterceptor(ScopeManifest([...])),
        )
    """

    def __init__(self, manifest: ScopeManifest):
        self.manifest = manifest
        self.audit_events: List[Dict[str, Any]] = []

    async def before_tool_call(
        self, origin: str, tool_name: str, arguments: Dict[str, Any]
    ) -> tuple:
        if not self.manifest.allows_tool(tool_name):
            reason = f"Tool '{tool_name}' is not in the allowed scope manifest"
            await self.log_event("before_tool_call", origin, tool_name, {"allowed": False})
            return False, reason

        await self.log_event("before_tool_call", origin, tool_name, {"allowed": True})
        return True, None

    async def after_tool_call(
        self,
        origin: str,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        error: Optional[str] = None,
    ) -> bool:
        await self.log_event(
            "after_tool_call", origin, tool_name, {"success": error is None, "error": error}
        )
        return True

    async def cross_origin_check(
        self,
        source_origin: str,
        target_origin: str,
        tool_name: str,
        data_preview: Optional[str] = None,
    ) -> bool:
        if source_origin == target_origin:
            return True

        allowed = self.manifest.allows_cross_origin(source_origin, target_origin)
        await self.log_event(
            "cross_origin_flow",
            target_origin,
            tool_name,
            {"source": source_origin, "allowed": allowed},
        )
        return allowed

    async def log_event(
        self,
        event_type: str,
        origin: str,
        tool_name: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        event = {"type": event_type, "origin": origin, "tool": tool_name, "details": details or {}}
        self.audit_events.append(event)
        logger.info(f"[truss-style audit] {event}")
