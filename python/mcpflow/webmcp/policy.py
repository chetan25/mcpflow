"""Security policy files for fine-grained tool access control."""

import logging
import yaml
from pathlib import Path
from typing import Optional, Dict, List, Set
from dataclasses import dataclass
from fnmatch import fnmatch

logger = logging.getLogger(__name__)


@dataclass
class ToolPolicy:
    """Policy for a single tool."""

    name_pattern: str  # Glob pattern (e.g., "add*", "delete_*")
    allowed: bool = True
    destructive: bool = False
    max_calls_per_session: Optional[int] = None
    requires_confirmation: bool = False
    description: str = ""


class PolicyFile:
    """
    Manages security policies from YAML files.

    Format:
    ```yaml
    version: 1
    origin: "https://example.com"
    policies:
      - name_pattern: "add*"
        allowed: true
        destructive: false
        max_calls_per_session: 100

      - name_pattern: "delete*"
        allowed: true
        destructive: true
        requires_confirmation: true

      - name_pattern: "*"  # Deny everything else
        allowed: false
    ```
    """

    def __init__(self, policy_file: Optional[Path] = None):
        """
        Load policies from YAML file.

        Args:
            policy_file: Path to policy file
        """
        self.policies: List[ToolPolicy] = []
        self.origin = None

        if policy_file and Path(policy_file).exists():
            self.load(policy_file)

    def load(self, policy_file: Path):
        """Load policies from YAML file."""
        try:
            with open(policy_file, "r") as f:
                data = yaml.safe_load(f)

            if not data:
                logger.warning(f"Empty policy file: {policy_file}")
                return

            self.origin = data.get("origin")

            for policy_data in data.get("policies", []):
                policy = ToolPolicy(
                    name_pattern=policy_data.get("name_pattern", "*"),
                    allowed=policy_data.get("allowed", True),
                    destructive=policy_data.get("destructive", False),
                    max_calls_per_session=policy_data.get("max_calls_per_session"),
                    requires_confirmation=policy_data.get("requires_confirmation", False),
                    description=policy_data.get("description", ""),
                )
                self.policies.append(policy)
                logger.debug(f"Loaded policy: {policy.name_pattern}")

            logger.info(f"Loaded {len(self.policies)} policies from {policy_file}")

        except Exception as e:
            logger.error(f"Failed to load policy file: {e}")

    def to_dict(self) -> Dict:
        """Export as dict (for serialization)."""
        return {
            "version": 1,
            "origin": self.origin,
            "policies": [
                {
                    "name_pattern": p.name_pattern,
                    "allowed": p.allowed,
                    "destructive": p.destructive,
                    "max_calls_per_session": p.max_calls_per_session,
                    "requires_confirmation": p.requires_confirmation,
                    "description": p.description,
                }
                for p in self.policies
            ],
        }

    def to_yaml(self) -> str:
        """Export as YAML string."""
        return yaml.dump(self.to_dict(), default_flow_style=False)


class PolicyEnforcer:
    """
    Enforces security policies on tool calls.

    Tracks call counts, checks permissions, flags destructive operations.
    """

    def __init__(self, policy_file: Optional[PolicyFile] = None):
        """
        Initialize policy enforcer.

        Args:
            policy_file: PolicyFile instance
        """
        self.policy = policy_file or PolicyFile()
        self.call_counts: Dict[str, int] = {}  # tool name -> count

    def is_allowed(self, tool_name: str) -> bool:
        """
        Check if a tool is allowed.

        Args:
            tool_name: Tool name

        Returns:
            True if allowed, False otherwise
        """
        for policy in self.policy.policies:
            if fnmatch(tool_name, policy.name_pattern):
                return policy.allowed

        # Default: deny if no matching policy
        logger.warning(f"No policy found for {tool_name}; denying by default")
        return False

    def is_destructive(self, tool_name: str) -> bool:
        """
        Check if a tool is marked destructive.

        Args:
            tool_name: Tool name

        Returns:
            True if destructive, False otherwise
        """
        for policy in self.policy.policies:
            if fnmatch(tool_name, policy.name_pattern):
                return policy.destructive

        return False

    def requires_confirmation(self, tool_name: str) -> bool:
        """
        Check if a tool requires human confirmation before calling.

        Args:
            tool_name: Tool name

        Returns:
            True if confirmation required, False otherwise
        """
        for policy in self.policy.policies:
            if fnmatch(tool_name, policy.name_pattern):
                return policy.requires_confirmation

        return False

    def can_call(self, tool_name: str) -> tuple[bool, Optional[str]]:
        """
        Comprehensive check for whether a tool can be called.

        Args:
            tool_name: Tool name

        Returns:
            Tuple of (allowed: bool, reason: str or None)
        """
        # Check if allowed
        if not self.is_allowed(tool_name):
            return False, f"Tool {tool_name} is not allowed by policy"

        # Check call limit
        for policy in self.policy.policies:
            if fnmatch(tool_name, policy.name_pattern):
                if policy.max_calls_per_session:
                    count = self.call_counts.get(tool_name, 0)
                    if count >= policy.max_calls_per_session:
                        return False, f"Tool {tool_name} call limit ({policy.max_calls_per_session}) exceeded"

        return True, None

    def record_call(self, tool_name: str):
        """
        Record a tool call for counting.

        Args:
            tool_name: Tool name
        """
        self.call_counts[tool_name] = self.call_counts.get(tool_name, 0) + 1

    def get_policy_for_tool(self, tool_name: str) -> Optional[ToolPolicy]:
        """
        Get the policy applicable to a tool.

        Args:
            tool_name: Tool name

        Returns:
            ToolPolicy or None
        """
        for policy in self.policy.policies:
            if fnmatch(tool_name, policy.name_pattern):
                return policy

        return None


def create_default_policy_yaml(origin: str) -> str:
    """
    Create a default policy file template for an origin.

    Args:
        origin: Origin URL

    Returns:
        YAML string
    """
    template = f"""# Security policy for {origin}
version: 1
origin: "{origin}"

policies:
  # Allow read-only tools (GET-like)
  - name_pattern: "list*"
    allowed: true
    destructive: false
    description: "List operations (non-destructive)"

  - name_pattern: "get*"
    allowed: true
    destructive: false
    description: "Get operations (non-destructive)"

  - name_pattern: "search*"
    allowed: true
    destructive: false
    description: "Search operations (non-destructive)"

  # Restrict write operations
  - name_pattern: "add*"
    allowed: true
    destructive: false
    max_calls_per_session: 50
    description: "Add operations (rate-limited)"

  - name_pattern: "update*"
    allowed: true
    destructive: false
    max_calls_per_session: 50
    description: "Update operations (rate-limited)"

  # Require confirmation for dangerous operations
  - name_pattern: "delete*"
    allowed: true
    destructive: true
    requires_confirmation: true
    max_calls_per_session: 5
    description: "Delete operations (requires confirmation, rate-limited)"

  - name_pattern: "pay*"
    allowed: true
    destructive: true
    requires_confirmation: true
    max_calls_per_session: 1
    description: "Payment operations (requires confirmation, one per session)"

  - name_pattern: "checkout*"
    allowed: true
    destructive: true
    requires_confirmation: true
    description: "Checkout operations (requires confirmation)"

  # Deny everything else by default
  - name_pattern: "*"
    allowed: false
    description: "Default deny policy"
"""
    return template
