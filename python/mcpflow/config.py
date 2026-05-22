"""Configuration management for MCPFlow."""

import os
import re
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, ConfigDict


def substitute_env_vars(value: Any) -> Any:
    """Recursively substitute environment variables in ${VAR} format.

    Args:
        value: Value to process (can be str, dict, list, etc.)

    Returns:
        Value with environment variables substituted
    """
    if isinstance(value, str):
        # Replace ${VAR} with environment variable value
        def replace_var(match: Any) -> str:
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))

        return re.sub(r"\$\{([^}]+)\}", replace_var, value)
    elif isinstance(value, dict):
        return {k: substitute_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [substitute_env_vars(item) for item in value]
    else:
        return value


class ModelConfig(BaseModel):
    """Configuration for an LLM model."""

    model_config = ConfigDict(extra="allow")

    provider: str = Field(description="Model provider (e.g., 'openai', 'anthropic')")
    name: str = Field(description="Model name")
    api_key: Optional[str] = Field(default=None, description="API key")
    base_url: Optional[str] = Field(default=None, description="Base URL for the API")


class AuthConfig(BaseModel):
    """Authentication configuration for an MCP server."""

    model_config = ConfigDict(extra="allow")

    type: str = Field(
        default="bearer",
        description="Auth type: 'bearer', 'basic', 'key', 'oauth', 'none'",
    )
    token: Optional[str] = Field(default=None, description="Bearer token")
    key: Optional[str] = Field(default=None, description="API key")
    username: Optional[str] = Field(default=None, description="Username")
    password: Optional[str] = Field(default=None, description="Password")


class MCPConfig(BaseModel):
    """Configuration for a single MCP server."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(description="MCP server name")
    url: str = Field(description="MCP server URL")
    auth: Optional[AuthConfig] = Field(default=None, description="Authentication config")
    tools: Optional[List[str]] = Field(
        default=None, description="Specific tools to enable"
    )
    timeout: float = Field(default=30.0, description="Request timeout in seconds")


class TeamConfig(BaseModel):
    """Configuration for a team with model and MCPs."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(description="Team name")
    model: ModelConfig = Field(description="LLM model configuration")
    mcps: List[MCPConfig] = Field(description="List of MCP servers")


class Config(BaseModel):
    """MCPFlow configuration."""

    model_config = ConfigDict(extra="allow")

    teams: List[TeamConfig] = Field(description="List of team configurations")

    @classmethod
    def from_yaml(cls, path: str) -> "Config":
        """Load configuration from a YAML file.

        Args:
            path: Path to YAML configuration file

        Returns:
            Config instance

        Raises:
            FileNotFoundError: If the file doesn't exist
            yaml.YAMLError: If the YAML is invalid
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path, "r") as f:
            data = yaml.safe_load(f)

        if data is None:
            data = {}

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Load configuration from a dictionary with environment variable substitution.

        Args:
            data: Configuration dictionary

        Returns:
            Config instance
        """
        # Recursively substitute environment variables
        data = substitute_env_vars(data)

        # Ensure 'teams' key exists
        if "teams" not in data:
            data["teams"] = []

        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Dictionary representation
        """
        return self.model_dump()

    def to_yaml(self) -> str:
        """Convert configuration to YAML string.

        Returns:
            YAML string representation
        """
        return yaml.dump(self.model_dump(), default_flow_style=False)

    def get_team(self, name: str) -> Optional[TeamConfig]:
        """Get a team configuration by name.

        Args:
            name: Team name

        Returns:
            TeamConfig or None if not found
        """
        for team in self.teams:
            if team.name == name:
                return team
        return None

    def get_mcp(self, team_name: str, mcp_name: str) -> Optional[MCPConfig]:
        """Get an MCP configuration from a team.

        Args:
            team_name: Team name
            mcp_name: MCP server name

        Returns:
            MCPConfig or None if not found
        """
        team = self.get_team(team_name)
        if team is None:
            return None

        for mcp in team.mcps:
            if mcp.name == mcp_name:
                return mcp
        return None
