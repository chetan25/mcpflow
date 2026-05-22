"""Tests for the Team Configuration example."""

import os
import tempfile
import pytest
import yaml
from team_config import (
    ConfigManager,
    TeamManager,
    MCPConfig,
    AgentConfig,
    TeamConfig,
)


@pytest.fixture
def sample_config():
    """Create a sample configuration for testing."""
    return {
        "mcps": [
            {
                "name": "echo",
                "url": "http://localhost:8001",
                "timeout": 30.0,
                "auth": {"type": "bearer", "token": "test-token-echo"},
                "tools": ["echo", "reverse"],
            },
            {
                "name": "weather",
                "url": "http://localhost:8002",
                "timeout": 30.0,
                "auth": {"type": "bearer", "token": "test-token-weather"},
                "tools": ["get_weather", "get_forecast"],
            },
        ],
        "teams": [
            {
                "name": "support-team",
                "description": "Support team",
                "environment": "production",
                "mcps": [
                    {
                        "name": "echo",
                        "url": "http://localhost:8001",
                        "auth": {"type": "bearer", "token": "test-token"},
                    }
                ],
                "agents": [
                    {
                        "name": "agent-1",
                        "model": "gpt-4",
                        "description": "Agent 1",
                        "mcps": ["echo"],
                        "system_prompt": "You are helpful",
                        "max_tool_calls": 10,
                    }
                ],
            }
        ],
    }


@pytest.fixture
def config_file(sample_config):
    """Create a temporary config file."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        yaml.dump(sample_config, f)
        path = f.name
    yield path
    os.unlink(path)


class TestConfigManager:
    """Tests for ConfigManager."""

    def test_config_manager_initialization(self, config_file):
        """Test ConfigManager initialization."""
        manager = ConfigManager(config_file)
        assert manager.config_path == config_file

    def test_load_config(self, config_file):
        """Test loading configuration."""
        manager = ConfigManager(config_file)
        manager.load_config()
        assert len(manager.mcps) > 0
        assert len(manager.teams) > 0

    def test_load_config_file_not_found(self):
        """Test error handling for missing config file."""
        manager = ConfigManager("nonexistent.yaml")
        with pytest.raises(FileNotFoundError):
            manager.load_config()

    def test_mcps_loaded(self, config_file):
        """Test that MCPs are loaded."""
        manager = ConfigManager(config_file)
        manager.load_config()
        assert "echo" in manager.mcps
        assert "weather" in manager.mcps

    def test_teams_loaded(self, config_file):
        """Test that teams are loaded."""
        manager = ConfigManager(config_file)
        manager.load_config()
        assert "support-team" in manager.teams

    def test_agents_indexed(self, config_file):
        """Test that agents are indexed correctly."""
        manager = ConfigManager(config_file)
        manager.load_config()
        assert "support-team:agent-1" in manager.agents


class TestEnvironmentSubstitution:
    """Tests for environment variable substitution."""

    def test_env_var_substitution(self):
        """Test environment variable substitution."""
        os.environ["TEST_VAR"] = "test-value"

        config_data = {"key": "${TEST_VAR}"}
        manager = ConfigManager()
        result = manager._substitute_env_vars(config_data)
        assert result["key"] == "test-value"

    def test_env_var_with_default(self):
        """Test environment variable with default value."""
        # Make sure var doesn't exist
        if "NONEXISTENT_VAR" in os.environ:
            del os.environ["NONEXISTENT_VAR"]

        config_data = {"key": "${NONEXISTENT_VAR:default-value}"}
        manager = ConfigManager()
        result = manager._substitute_env_vars(config_data)
        assert result["key"] == "default-value"

    def test_env_var_nested_in_dict(self):
        """Test environment variable substitution in nested dict."""
        os.environ["DB_HOST"] = "localhost"

        config_data = {
            "database": {"host": "${DB_HOST}", "port": 5432}
        }
        manager = ConfigManager()
        result = manager._substitute_env_vars(config_data)
        assert result["database"]["host"] == "localhost"
        assert result["database"]["port"] == 5432

    def test_env_var_in_list(self):
        """Test environment variable substitution in list."""
        os.environ["TOKEN"] = "secret-token"

        config_data = {"tokens": ["${TOKEN}", "other-token"]}
        manager = ConfigManager()
        result = manager._substitute_env_vars(config_data)
        assert result["tokens"][0] == "secret-token"
        assert result["tokens"][1] == "other-token"


class TestMCPConfig:
    """Tests for MCP configuration."""

    def test_mcp_config_creation(self, config_file):
        """Test MCP configuration parsing."""
        manager = ConfigManager(config_file)
        manager.load_config()

        mcp = manager.mcps["echo"]
        assert mcp.name == "echo"
        assert mcp.url == "http://localhost:8001"
        assert mcp.timeout == 30.0

    def test_mcp_config_with_auth(self, config_file):
        """Test MCP configuration with authentication."""
        manager = ConfigManager(config_file)
        manager.load_config()

        mcp = manager.mcps["echo"]
        assert mcp.auth_type == "bearer"
        assert mcp.auth_token == "test-token-echo"

    def test_mcp_config_with_tools(self, config_file):
        """Test MCP configuration with specific tools."""
        manager = ConfigManager(config_file)
        manager.load_config()

        mcp = manager.mcps["echo"]
        assert mcp.tools == ["echo", "reverse"]


class TestAgentConfig:
    """Tests for agent configuration."""

    def test_agent_config_creation(self, config_file):
        """Test agent configuration parsing."""
        manager = ConfigManager(config_file)
        manager.load_config()

        agent = manager.get_agent("support-team", "agent-1")
        assert agent.name == "agent-1"
        assert agent.model == "gpt-4"
        assert "echo" in agent.mcps

    def test_agent_config_defaults(self, config_file):
        """Test agent configuration defaults."""
        manager = ConfigManager(config_file)
        manager.load_config()

        agent = manager.get_agent("support-team", "agent-1")
        assert agent.max_tool_calls == 10
        assert agent.enabled is True

    def test_get_nonexistent_agent(self, config_file):
        """Test getting nonexistent agent."""
        manager = ConfigManager(config_file)
        manager.load_config()

        agent = manager.get_agent("support-team", "nonexistent")
        assert agent is None


class TestTeamConfig:
    """Tests for team configuration."""

    def test_team_config_creation(self, config_file):
        """Test team configuration parsing."""
        manager = ConfigManager(config_file)
        manager.load_config()

        team = manager.get_team("support-team")
        assert team.name == "support-team"
        assert team.description == "Support team"
        assert team.environment == "production"

    def test_team_has_agents(self, config_file):
        """Test that team has agents."""
        manager = ConfigManager(config_file)
        manager.load_config()

        team = manager.get_team("support-team")
        assert len(team.agents) > 0

    def test_list_teams(self, config_file):
        """Test listing teams."""
        manager = ConfigManager(config_file)
        manager.load_config()

        teams = manager.list_teams()
        assert "support-team" in teams

    def test_list_agents_in_team(self, config_file):
        """Test listing agents in a team."""
        manager = ConfigManager(config_file)
        manager.load_config()

        agents = manager.list_agents("support-team")
        assert "agent-1" in agents


class TestTeamManager:
    """Tests for TeamManager."""

    def test_team_manager_initialization(self, config_file):
        """Test TeamManager initialization."""
        manager = TeamManager(config_file)
        assert manager.config_manager is not None

    def test_get_team_status(self, config_file):
        """Test getting team status."""
        manager = TeamManager(config_file)
        status = manager.get_team_status("support-team")

        assert status["name"] == "support-team"
        assert status["environment"] == "production"
        assert "agents" in status
        assert "mcps" in status

    def test_get_agent_status(self, config_file):
        """Test getting agent status."""
        manager = TeamManager(config_file)
        status = manager.get_agent_status("support-team", "agent-1")

        assert status["name"] == "agent-1"
        assert status["model"] == "gpt-4"
        assert "mcps" in status

    def test_get_nonexistent_team_status(self, config_file):
        """Test getting status of nonexistent team."""
        manager = TeamManager(config_file)
        status = manager.get_team_status("nonexistent")

        assert "error" in status

    def test_get_all_teams_status(self, config_file):
        """Test getting all teams status."""
        manager = TeamManager(config_file)
        status = manager.get_all_teams_status()

        assert "support-team" in status

    def test_config_to_dict(self, config_file):
        """Test converting configuration to dictionary."""
        manager = TeamManager(config_file)
        config_dict = manager.config_manager.to_dict()

        assert "teams" in config_dict
        assert "mcps" in config_dict
        assert "support-team" in config_dict["teams"]


class TestAgentMCPAssociation:
    """Tests for agent to MCP association."""

    def test_get_agent_mcps(self, config_file):
        """Test getting MCPs for an agent."""
        manager = ConfigManager(config_file)
        manager.load_config()

        mcps = manager.get_agent_mcps("support-team", "agent-1")
        assert len(mcps) > 0
        assert any(mcp.name == "echo" for mcp in mcps)

    def test_agent_mcps_match_config(self, config_file):
        """Test that agent MCPs match configuration."""
        manager = ConfigManager(config_file)
        manager.load_config()

        agent = manager.get_agent("support-team", "agent-1")
        mcps = manager.get_agent_mcps("support-team", "agent-1")

        mcp_names = {mcp.name for mcp in mcps}
        assert mcp_names == set(agent.mcps)


class TestConfigIntegration:
    """Integration tests for configuration."""

    def test_multiple_teams_multiple_agents(self):
        """Test loading multiple teams with multiple agents."""
        config = {
            "mcps": [
                {
                    "name": "tool1",
                    "url": "http://localhost:8001",
                    "auth": {"type": "bearer", "token": "token1"},
                },
                {
                    "name": "tool2",
                    "url": "http://localhost:8002",
                    "auth": {"type": "bearer", "token": "token2"},
                },
            ],
            "teams": [
                {
                    "name": "team-a",
                    "description": "Team A",
                    "environment": "production",
                    "mcps": [
                        {
                            "name": "tool1",
                            "url": "http://localhost:8001",
                            "auth": {"type": "bearer", "token": "token1"},
                        }
                    ],
                    "agents": [
                        {
                            "name": "agent-a1",
                            "model": "gpt-4",
                            "mcps": ["tool1"],
                            "system_prompt": "Test",
                        },
                        {
                            "name": "agent-a2",
                            "model": "gpt-3.5",
                            "mcps": ["tool1"],
                            "system_prompt": "Test",
                        },
                    ],
                },
                {
                    "name": "team-b",
                    "description": "Team B",
                    "environment": "staging",
                    "mcps": [
                        {
                            "name": "tool2",
                            "url": "http://localhost:8002",
                            "auth": {"type": "bearer", "token": "token2"},
                        }
                    ],
                    "agents": [
                        {
                            "name": "agent-b1",
                            "model": "gpt-4",
                            "mcps": ["tool2"],
                            "system_prompt": "Test",
                        }
                    ],
                },
            ],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config, f)
            path = f.name

        try:
            manager = TeamManager(path)
            teams = manager.get_all_teams_status()

            assert len(teams) == 2
            assert "team-a" in teams
            assert "team-b" in teams
            assert teams["team-a"]["agents"] == 2
            assert teams["team-b"]["agents"] == 1
        finally:
            os.unlink(path)
