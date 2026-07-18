"""Security layer for WebMCP bridge."""

import logging
import json
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SecurityManager:
    """Handles security policies for WebMCP origins."""

    def __init__(self, audit_dir: Optional[str] = None):
        """
        Initialize security manager.

        Args:
            audit_dir: Directory for audit logs (defaults to ~/.mcpflow/)
        """
        if audit_dir is None:
            audit_dir = str(Path.home() / ".mcpflow")
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.audit_log = self.audit_dir / "audit.jsonl"
        self.origin_allowlist = set()

    def set_allowed_origins(self, origins: list[str]):
        """
        Set allowed origins (deny by default).

        Args:
            origins: List of allowed origin URLs
        """
        self.origin_allowlist = set(origins)
        logger.info(f"Allowed origins: {origins}")

    def check_origin_allowed(self, origin: str) -> bool:
        """
        Check if an origin is allowed.

        Args:
            origin: Origin URL to check

        Returns:
            True if allowed, False otherwise
        """
        allowed = origin in self.origin_allowlist or "*" in self.origin_allowlist
        if not allowed:
            logger.warning(f"Origin not allowed: {origin}")
        return allowed

    def check_tool_call(self, origin: str, tool_name: str) -> tuple[bool, Optional[str]]:
        """
        Security-manager-level check before a tool call proceeds.

        Origin admission is enforced once at discovery time
        (check_origin_allowed); this hook is the security-manager-level gate
        InterceptorProtocol implementations call before executing a tool, and
        is where future rules (rate limits, kill switches) would live.
        Fine-grained per-tool allow/deny/destructive rules live in
        PolicyEnforcer (see WebMCPBridge.policy_enforcer).

        Args:
            origin: Origin identifier
            tool_name: Tool name being called

        Returns:
            Tuple of (allowed, reason)
        """
        return True, None

    def sanitize_tool_description(self, description: str) -> tuple[str, bool]:
        """
        Sanitize tool description and flag suspicious patterns.

        Args:
            description: Tool description

        Returns:
            Tuple of (sanitized_description, has_injection_risk)
        """
        if not description:
            return "", False

        import re

        original = description
        has_risk = False

        # Check for injection patterns
        injection_patterns = [
            r"\b(always|never|must|ignore)\b",
            r"previous\s+(instruction|prompt|message|conversation)",
            r"override.*permission",
            r"\[.*\]\(.*\)",  # Markdown links
            r"https?://",  # URLs
        ]

        for pattern in injection_patterns:
            if re.search(pattern, original, re.IGNORECASE):
                has_risk = True
                logger.warning(f"Injection risk detected in description: {pattern}")

        # Sanitize
        sanitized = original
        for pattern in injection_patterns:
            sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)

        sanitized = sanitized.strip()
        return sanitized, has_risk

    def log_discovery(self, origin: str, tool_count: int, tool_names: list[str]):
        """
        Log a discovery event.

        Args:
            origin: Origin URL
            tool_count: Number of tools discovered
            tool_names: List of tool names
        """
        import time

        event = {
            "event": "discovery",
            "timestamp": time.time(),
            "origin": origin,
            "tool_count": tool_count,
            "tools": tool_names,
        }
        self._append_audit_log(event)

    def log_tool_call(
        self,
        origin: str,
        tool_name: str,
        success: bool,
        error: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        """
        Log a tool invocation.

        Args:
            origin: Origin URL
            tool_name: Tool name
            success: Whether the call succeeded
            error: Error message if failed
            metadata: Additional context to attach to the audit entry (e.g.
                which InterceptorProtocol event triggered this log line)
        """
        import time

        event = {
            "event": "tool_call",
            "timestamp": time.time(),
            "origin": origin,
            "tool": tool_name,
            "success": success,
        }
        if error:
            event["error"] = error
        if metadata:
            event["metadata"] = metadata

        self._append_audit_log(event)

    def _append_audit_log(self, event: dict):
        """
        Append an event to the audit log.

        Args:
            event: Event dict to log
        """
        try:
            with open(self.audit_log, "a") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
