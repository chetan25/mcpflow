"""InterceptorProtocol for pluggable security interceptors."""

import logging
from typing import Protocol, Optional, Dict, Any, List, runtime_checkable
from abc import abstractmethod

logger = logging.getLogger(__name__)


@runtime_checkable
class InterceptorProtocol(Protocol):
    """
    Protocol for security interceptors.

    Allows plugging in production security systems (like Truss MCP Interceptor)
    without coupling mcpflow to specific implementations.

    Usage:
        bridge = WebMCPBridge(interceptor=TrussInterceptor(manifest="scope.yaml"))
    """

    @abstractmethod
    async def before_tool_call(
        self,
        origin: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> tuple[bool, Optional[str]]:
        """
        Called before a tool is executed.

        Args:
            origin: Origin identifier
            tool_name: Tool name
            arguments: Tool arguments

        Returns:
            Tuple of (allowed: bool, reason: str or None)

        If allowed=False, the tool call is blocked with the given reason.
        """
        ...

    @abstractmethod
    async def after_tool_call(
        self,
        origin: str,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        error: Optional[str] = None,
    ) -> bool:
        """
        Called after a tool completes.

        Args:
            origin: Origin identifier
            tool_name: Tool name
            arguments: Original arguments
            result: Tool result (or None if error)
            error: Error message if call failed

        Returns:
            True if the result is acceptable, False to reject

        If False, the result is scrubbed/blocked from reaching the client.
        """
        ...

    @abstractmethod
    async def cross_origin_check(
        self,
        source_origin: str,
        target_origin: str,
        tool_name: str,
        data_preview: Optional[str] = None,
    ) -> bool:
        """
        Called when data from one origin is about to cross to another.

        This is the exfiltration protection gate.

        Args:
            source_origin: Origin where data came from
            target_origin: Origin where data is going
            tool_name: Target tool name
            data_preview: Preview of data being sent (for logging)

        Returns:
            True if cross-origin data flow is allowed
        """
        ...

    @abstractmethod
    async def log_event(
        self,
        event_type: str,
        origin: str,
        tool_name: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Called to log security events.

        Args:
            event_type: Event type (e.g., "tool_call", "policy_violation", "discovery")
            origin: Origin identifier
            tool_name: Tool name
            details: Additional event details
        """
        ...


class DefaultInterceptor:
    """
    Default in-tree interceptor using mcpflow's built-in security.

    Implements InterceptorProtocol using PolicyEnforcer and SecurityManager.
    """

    def __init__(self, bridge):
        """
        Initialize default interceptor.

        Args:
            bridge: WebMCPBridge instance
        """
        self.bridge = bridge

    async def before_tool_call(
        self,
        origin: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> tuple[bool, Optional[str]]:
        """Check if tool call is allowed."""
        # Check security policy
        allowed, reason = self.bridge.security.check_tool_call(origin, tool_name)

        if allowed and hasattr(self.bridge, "policy_enforcer") and self.bridge.policy_enforcer:
            # Check policy file if enabled
            allowed, reason = self.bridge.policy_enforcer.can_call(tool_name)

        await self.log_event(
            "before_tool_call",
            origin,
            tool_name,
            {"allowed": allowed, "reason": reason},
        )

        return allowed, reason

    async def after_tool_call(
        self,
        origin: str,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        error: Optional[str] = None,
    ) -> bool:
        """Validate tool result."""
        # Log the result (result validation happens in security manager)
        self.bridge.security.log_tool_call(
            origin, tool_name, error is None, error=error
        )

        await self.log_event(
            "after_tool_call",
            origin,
            tool_name,
            {"success": error is None, "error": error},
        )

        # Accept all results — the security layer already filtered them
        return True

    async def cross_origin_check(
        self,
        source_origin: str,
        target_origin: str,
        tool_name: str,
        data_preview: Optional[str] = None,
    ) -> bool:
        """Check cross-origin data flow."""
        if source_origin == target_origin:
            return True  # Same origin, always allowed

        # Log cross-origin call
        logger.warning(
            f"Cross-origin data flow: {source_origin} -> {target_origin} (tool: {tool_name})"
        )

        await self.log_event(
            "cross_origin_flow",
            target_origin,
            tool_name,
            {"source": source_origin, "data_preview": data_preview},
        )

        # Allow with logging (production systems like Truss will override this)
        return True

    async def log_event(
        self,
        event_type: str,
        origin: str,
        tool_name: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a security event."""
        logger.info(
            f"Security event: {event_type} | {origin} | {tool_name} | {details}"
        )

        self.bridge.security.log_tool_call(
            origin, tool_name, True, metadata={"event_type": event_type}
        )


class CompositeInterceptor:
    """
    Composite interceptor that chains multiple interceptors.

    Calls each interceptor in sequence; fails fast if any rejects.
    """

    def __init__(self, interceptors: List[InterceptorProtocol]):
        """
        Initialize composite interceptor.

        Args:
            interceptors: List of interceptors to chain
        """
        self.interceptors = interceptors

    async def before_tool_call(
        self,
        origin: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> tuple[bool, Optional[str]]:
        """Call all interceptors: fail on first rejection."""
        for interceptor in self.interceptors:
            allowed, reason = await interceptor.before_tool_call(
                origin, tool_name, arguments
            )
            if not allowed:
                return False, reason

        return True, None

    async def after_tool_call(
        self,
        origin: str,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        error: Optional[str] = None,
    ) -> bool:
        """Call all interceptors: reject on first False."""
        for interceptor in self.interceptors:
            accepted = await interceptor.after_tool_call(
                origin, tool_name, arguments, result, error
            )
            if not accepted:
                return False

        return True

    async def cross_origin_check(
        self,
        source_origin: str,
        target_origin: str,
        tool_name: str,
        data_preview: Optional[str] = None,
    ) -> bool:
        """Call all interceptors: reject on first False."""
        for interceptor in self.interceptors:
            allowed = await interceptor.cross_origin_check(
                source_origin, target_origin, tool_name, data_preview
            )
            if not allowed:
                return False

        return True

    async def log_event(
        self,
        event_type: str,
        origin: str,
        tool_name: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Call all interceptors to log."""
        for interceptor in self.interceptors:
            await interceptor.log_event(event_type, origin, tool_name, details)
