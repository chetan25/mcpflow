"""Tests for Config Loader."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from mcpflow.config import (
    AuthConfig,
    Config,
    MCPConfig,
    ModelConfig,
    TeamConfig,
    substitute_env_vars,
)


class TestSubstituteEnvVars:
    """Tests for environment variable substitution."""

    def test_substitute_simple_string(self, monkeypatch):
        """Test substituting a simple environment variable."""
        monkeypatch.setenv("TEST_VAR", "test_value")

        result = substitute_env_vars("${TEST_VAR}")

        assert result == "test_value"

    def test_substitute_string_with_prefix_suffix(self, monkeypatch):
        """Test substituting variable with prefix and suffix."""
        monkeypatch.setenv("API_KEY", "secret123")

        result = substitute_env_vars("Bearer ${API_KEY}")

        assert result == "Bearer secret123"

    def test_substitute_multiple_vars(self, monkeypatch):
        """Test substituting multiple variables."""
        monkeypatch.setenv("USER", "alice")
        monkeypatch.setenv("HOST", "localhost")

        result = substitute_env_vars("${USER}@${HOST}")

        assert result == "alice@localhost"

    def test_substitute_nonexistent_var(self):
        """Test substitution with nonexistent variable."""
        result = substitute_env_vars("${NONEXISTENT_VAR}")

        # Should return the original placeholder if var doesn't exist
        assert result == "${NONEXISTENT_VAR}"

    def test_substitute_dict(self, monkeypatch):
        """Test substituting environment variables in a dictionary."""
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PORT", "5432")

        data = {"host": "${DB_HOST}", "port": "${DB_PORT}"}
        result = substitute_env_vars(data)

        assert result["host"] == "localhost"
        assert result["port"] == "5432"

    def test_substitute_list(self, monkeypatch):
        """Test substituting environment variables in a list."""
        monkeypatch.setenv("URL1", "http://server1")
        monkeypatch.setenv("URL2", "http://server2")

        data = ["${URL1}", "${URL2}"]
        result = substitute_env_vars(data)

        assert result == ["http://server1", "http://server2"]

    def test_substitute_nested_structure(self, monkeypatch):
        """Test substituting environment variables in nested structures."""
        monkeypatch.setenv("API_URL", "http://api.example.com")
        monkeypatch.setenv("API_KEY", "secret")

        data = {
            "services": [
                {"url": "${API_URL}", "key": "${API_KEY}"},
                {"url": "${API_URL}", "key": "${API_KEY}"},
            ]
        }
        result = substitute_env_vars(data)

        assert result["services"][0]["url"] == "http://api.example.com"
        assert result["services"][0]["key"] == "secret"

    def test_substitute_non_string_values(self):
        """Test that non-string values are returned as-is."""
        data = {"count": 42, "enabled": True, "ratio": 3.14}
        result = substitute_env_vars(data)

        assert result["count"] == 42
        assert result["enabled"] is True
        assert result["ratio"] == 3.14


class TestModelConfig:
    """Tests for ModelConfig."""

    def test_model_config_creation(self):
        """Test creating a ModelConfig."""
        config = ModelConfig(
            provider="openai",
            name="gpt-4",
            api_key="sk-123",
            base_url="https://api.openai.com/v1",
        )

        assert config.provider == "openai"
        assert config.name == "gpt-4"
        assert config.api_key == "sk-123"
        assert config.base_url == "https://api.openai.com/v1"

    def test_model_config_optional_fields(self):
        """Test ModelConfig with optional fields."""
        config = ModelConfig(provider="openai", name="gpt-4")

        assert config.provider == "openai"
        assert config.name == "gpt-4"
        assert config.api_key is None
        assert config.base_url is None


class TestAuthConfig:
    """Tests for AuthConfig."""

    def test_bearer_auth(self):
        """Test bearer token authentication."""
        auth = AuthConfig(type="bearer", token="test-token-123")

        assert auth.type == "bearer"
        assert auth.token == "test-token-123"

    def test_basic_auth(self):
        """Test basic authentication."""
        auth = AuthConfig(type="basic", username="user", password="pass")

        assert auth.type == "basic"
        assert auth.username == "user"
        assert auth.password == "pass"

    def test_api_key_auth(self):
        """Test API key authentication."""
        auth = AuthConfig(type="key", key="api-key-123")

        assert auth.type == "key"
        assert auth.key == "api-key-123"

    def test_default_auth_type(self):
        """Test default authentication type."""
        auth = AuthConfig(token="token")

        assert auth.type == "bearer"


class TestMCPConfig:
    """Tests for MCPConfig."""

    def test_mcp_config_minimal(self):
        """Test creating a minimal MCPConfig."""
        mcp = MCPConfig(name="server1", url="http://localhost:8000")

        assert mcp.name == "server1"
        assert mcp.url == "http://localhost:8000"
        assert mcp.auth is None
        assert mcp.tools is None
        assert mcp.timeout == 30.0

    def test_mcp_config_full(self):
        """Test creating a full MCPConfig."""
        auth = AuthConfig(type="bearer", token="token")
        mcp = MCPConfig(
            name="server1",
            url="http://localhost:8000",
            auth=auth,
            tools=["tool1", "tool2"],
            timeout=60.0,
        )

        assert mcp.name == "server1"
        assert mcp.url == "http://localhost:8000"
        assert mcp.auth is not None
        assert mcp.tools == ["tool1", "tool2"]
        assert mcp.timeout == 60.0


class TestTeamConfig:
    """Tests for TeamConfig."""

    def test_team_config_creation(self):
        """Test creating a TeamConfig."""
        model = ModelConfig(provider="openai", name="gpt-4")
        mcp1 = MCPConfig(name="server1", url="http://localhost:8000")
        mcp2 = MCPConfig(name="server2", url="http://localhost:8001")

        team = TeamConfig(name="team1", model=model, mcps=[mcp1, mcp2])

        assert team.name == "team1"
        assert team.model.provider == "openai"
        assert len(team.mcps) == 2
        assert team.mcps[0].name == "server1"


class TestConfig:
    """Tests for Config."""

    def test_config_from_dict(self):
        """Test creating Config from dictionary."""
        data = {
            "teams": [
                {
                    "name": "team1",
                    "model": {"provider": "openai", "name": "gpt-4"},
                    "mcps": [
                        {"name": "server1", "url": "http://localhost:8000"}
                    ],
                }
            ]
        }

        config = Config.from_dict(data)

        assert len(config.teams) == 1
        assert config.teams[0].name == "team1"
        assert config.teams[0].model.provider == "openai"

    def test_config_from_dict_empty(self):
        """Test creating Config from empty dictionary."""
        config = Config.from_dict({})

        assert len(config.teams) == 0

    def test_config_from_yaml(self):
        """Test loading Config from YAML file."""
        yaml_content = """
teams:
  - name: team1
    model:
      provider: openai
      name: gpt-4
    mcps:
      - name: server1
        url: http://localhost:8000
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            temp_path = f.name

        try:
            config = Config.from_yaml(temp_path)

            assert len(config.teams) == 1
            assert config.teams[0].name == "team1"
        finally:
            os.unlink(temp_path)

    def test_config_from_yaml_nonexistent(self):
        """Test loading Config from nonexistent file."""
        with pytest.raises(FileNotFoundError):
            Config.from_yaml("/nonexistent/config.yaml")

    def test_config_with_env_var_substitution(self, monkeypatch):
        """Test Config with environment variable substitution."""
        monkeypatch.setenv("API_KEY", "secret123")
        monkeypatch.setenv("SERVER_URL", "http://prod.example.com")

        data = {
            "teams": [
                {
                    "name": "team1",
                    "model": {
                        "provider": "openai",
                        "name": "gpt-4",
                        "api_key": "${API_KEY}",
                    },
                    "mcps": [
                        {
                            "name": "server1",
                            "url": "${SERVER_URL}",
                            "auth": {"type": "bearer", "token": "${API_KEY}"},
                        }
                    ],
                }
            ]
        }

        config = Config.from_dict(data)

        assert config.teams[0].model.api_key == "secret123"
        assert config.teams[0].mcps[0].url == "http://prod.example.com"
        assert config.teams[0].mcps[0].auth.token == "secret123"

    def test_config_to_dict(self):
        """Test converting Config to dictionary."""
        data = {
            "teams": [
                {
                    "name": "team1",
                    "model": {"provider": "openai", "name": "gpt-4"},
                    "mcps": [{"name": "server1", "url": "http://localhost:8000"}],
                }
            ]
        }

        config = Config.from_dict(data)
        result = config.to_dict()

        assert "teams" in result
        assert len(result["teams"]) == 1
        assert result["teams"][0]["name"] == "team1"

    def test_config_to_yaml(self):
        """Test converting Config to YAML."""
        data = {
            "teams": [
                {
                    "name": "team1",
                    "model": {"provider": "openai", "name": "gpt-4"},
                    "mcps": [{"name": "server1", "url": "http://localhost:8000"}],
                }
            ]
        }

        config = Config.from_dict(data)
        yaml_str = config.to_yaml()

        assert "team1" in yaml_str
        assert "openai" in yaml_str
        assert "server1" in yaml_str

    def test_config_get_team(self):
        """Test getting a team by name."""
        data = {
            "teams": [
                {
                    "name": "team1",
                    "model": {"provider": "openai", "name": "gpt-4"},
                    "mcps": [],
                },
                {
                    "name": "team2",
                    "model": {"provider": "anthropic", "name": "claude"},
                    "mcps": [],
                },
            ]
        }

        config = Config.from_dict(data)

        team1 = config.get_team("team1")
        assert team1 is not None
        assert team1.name == "team1"
        assert team1.model.provider == "openai"

        team2 = config.get_team("team2")
        assert team2 is not None
        assert team2.model.provider == "anthropic"

        nonexistent = config.get_team("team3")
        assert nonexistent is None

    def test_config_get_mcp(self):
        """Test getting an MCP from a team."""
        data = {
            "teams": [
                {
                    "name": "team1",
                    "model": {"provider": "openai", "name": "gpt-4"},
                    "mcps": [
                        {"name": "server1", "url": "http://localhost:8000"},
                        {"name": "server2", "url": "http://localhost:8001"},
                    ],
                }
            ]
        }

        config = Config.from_dict(data)

        mcp1 = config.get_mcp("team1", "server1")
        assert mcp1 is not None
        assert mcp1.url == "http://localhost:8000"

        mcp2 = config.get_mcp("team1", "server2")
        assert mcp2 is not None
        assert mcp2.url == "http://localhost:8001"

        nonexistent = config.get_mcp("team1", "server3")
        assert nonexistent is None

    def test_config_yaml_with_env_vars(self, monkeypatch):
        """Test loading YAML with environment variable substitution."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test123")
        monkeypatch.setenv("MCP_URL", "http://mcp.example.com")

        yaml_content = """
teams:
  - name: team1
    model:
      provider: openai
      name: gpt-4
      api_key: ${OPENAI_API_KEY}
    mcps:
      - name: server1
        url: ${MCP_URL}
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            temp_path = f.name

        try:
            config = Config.from_yaml(temp_path)

            assert config.teams[0].model.api_key == "sk-test123"
            assert config.teams[0].mcps[0].url == "http://mcp.example.com"
        finally:
            os.unlink(temp_path)
