"""Multi-origin configuration for serving multiple WebMCP sites."""

import logging
from typing import Dict, List, Optional, Set
from pathlib import Path
from dataclasses import dataclass
import yaml

logger = logging.getLogger(__name__)


@dataclass
class OriginConfig:
    """Configuration for a single origin."""

    origin: str  # Full URL or slug
    enabled: bool = True
    description: str = ""
    session_profile: Optional[str] = None  # Reference to saved session
    require_headed_for: Optional[List[str]] = None  # Tool patterns requiring headed browser
    policy_file: Optional[Path] = None  # Security policy file
    cache_ttl_seconds: int = 3600  # Discovery cache TTL
    metadata: Optional[Dict] = None

    def to_dict(self) -> dict:
        """Convert to dict."""
        return {
            "origin": self.origin,
            "enabled": self.enabled,
            "description": self.description,
            "session_profile": self.session_profile,
            "require_headed_for": self.require_headed_for or [],
            "policy_file": str(self.policy_file) if self.policy_file else None,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "metadata": self.metadata or {},
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Create from dict."""
        origin = data.get("origin", "unknown")
        return cls(
            origin=origin,
            enabled=data.get("enabled", True),
            description=data.get("description", ""),
            session_profile=data.get("session_profile"),
            require_headed_for=data.get("require_headed_for"),
            policy_file=Path(data["policy_file"]) if data.get("policy_file") else None,
            cache_ttl_seconds=data.get("cache_ttl_seconds", 3600),
            metadata=data.get("metadata"),
        )


class MultiOriginConfig:
    """
    Manages configuration for multiple WebMCP origins.

    Allows serving multiple sites from one bridge with per-origin settings.

    Format:
    ```yaml
    version: 1
    origins:
      - origin: "https://shop.example.com"
        enabled: true
        session_profile: "chetan-shop"
        policy_file: "policies/shop.yaml"

      - origin: "https://travel.example.com"
        enabled: true
        session_profile: "chetan-travel"
        require_headed_for: ["booking*", "payment*"]
    ```
    """

    def __init__(self, config_file: Optional[Path] = None):
        """
        Load multi-origin configuration.

        Args:
            config_file: Path to YAML configuration file
        """
        self.origins: Dict[str, OriginConfig] = {}
        self.default_config = OriginConfig(origin="default", enabled=True)

        if config_file:
            self.load(config_file)

    def load(self, config_file: Path):
        """Load configuration from YAML file."""
        try:
            with open(config_file, "r") as f:
                data = yaml.safe_load(f)

            if not data:
                logger.warning(f"Empty config file: {config_file}")
                return

            for origin_data in data.get("origins", []):
                config = OriginConfig.from_dict(origin_data)
                self.add_origin(config)

            logger.info(f"Loaded {len(self.origins)} origins from {config_file}")

        except Exception as e:
            logger.error(f"Failed to load config: {e}")

    def add_origin(self, config: OriginConfig) -> None:
        """Add or update an origin configuration."""
        self.origins[config.origin] = config
        logger.info(f"Added origin: {config.origin}")

    def remove_origin(self, origin: str) -> bool:
        """Remove an origin configuration."""
        if origin in self.origins:
            del self.origins[origin]
            logger.info(f"Removed origin: {origin}")
            return True
        return False

    def get_origin(self, origin: str) -> OriginConfig:
        """Get configuration for an origin (returns default if not found)."""
        if origin in self.origins:
            return self.origins[origin]

        # Return default with origin preset
        default = OriginConfig(origin=origin)
        return default

    def is_enabled(self, origin: str) -> bool:
        """Check if origin is enabled."""
        config = self.get_origin(origin)
        return config.enabled

    def list_origins(self, enabled_only: bool = False) -> List[str]:
        """List all configured origins."""
        origins = list(self.origins.keys())

        if enabled_only:
            origins = [o for o in origins if self.is_enabled(o)]

        return sorted(origins)

    def get_session_profile(self, origin: str) -> Optional[str]:
        """Get session profile for origin."""
        config = self.get_origin(origin)
        return config.session_profile

    def get_policy_file(self, origin: str) -> Optional[Path]:
        """Get policy file for origin."""
        config = self.get_origin(origin)
        return config.policy_file

    def requires_headed(self, origin: str, tool_name: str) -> bool:
        """Check if a tool requires headed browser."""
        config = self.get_origin(origin)
        if not config.require_headed_for:
            return False

        from fnmatch import fnmatch

        for pattern in config.require_headed_for:
            if fnmatch(tool_name, pattern):
                return True

        return False

    def to_yaml(self) -> str:
        """Export as YAML string."""
        data = {
            "version": 1,
            "origins": [config.to_dict() for config in self.origins.values()],
        }
        return yaml.dump(data, default_flow_style=False)

    def to_dict(self) -> dict:
        """Export as dict."""
        return {
            "version": 1,
            "origins": [config.to_dict() for config in self.origins.values()],
        }


def create_default_multi_origin_config(origins: List[str]) -> str:
    """Create a default multi-origin configuration template."""
    template = """# Multi-origin configuration for WebMCP bridge
version: 1

origins:
"""

    for origin in origins:
        origin_slug = origin.replace("https://", "").replace("http://", "").split("/")[0]
        template += f"""
  - origin: "{origin}"
    enabled: true
    description: "WebMCP tools from {origin_slug}"
    session_profile: NULL  # Set to saved profile name to reuse auth
    policy_file: NULL  # Set to path/to/policy.yaml for fine-grained control
    require_headed_for: []  # Tool patterns requiring headed browser
    cache_ttl_seconds: 3600
"""

    return template
