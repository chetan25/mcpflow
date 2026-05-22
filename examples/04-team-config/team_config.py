"""
Team Configuration Example

This example demonstrates:
- Complete team setup with configuration files
- Multiple teams with different agents
- Environment variable substitution
- Production-ready configuration patterns
"""

import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass
class ToolConfig:
    """Tool configuration."""

    name: str
    description: str
    enabled: bool = True
    rate_limit: Optional[int] = None


@dataclass
class MCPConfig:
    """MCP server configuration."""

    name: str
    url: str
    timeout: float = 30.0
    auth_type: str = "bearer"
    auth_token: Optional[str] = None
    tools: Optional[List[str]] = None
    enabled: bool = True


@dataclass
class AgentConfig:
    """Individual agent configuration."""

    name: str
    model: str
    description: str
    mcps: List[str]
    system_prompt: str
    max_tool_calls: int = 10
    enabled: bool = True


@dataclass
class TeamConfig:
    """Team configuration."""

    name: str
    description: str
    agents: List[AgentConfig]
    shared_mcps: List[MCPConfig]
    environment: str = "development"
    enabled: bool = True


class ConfigManager:
    """Manages team and agent configurations."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize config manager.

        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path or "config.yaml"
        self.config_data: Dict = {}
        self.teams: Dict[str, TeamConfig] = {}
        self.mcps: Dict[str, MCPConfig] = {}
        self.agents: Dict[str, AgentConfig] = {}

    def load_config(self) -> None:
        """Load configuration from file."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, "r") as f:
            raw_config = yaml.safe_load(f)

        # Substitute environment variables
        self.config_data = self._substitute_env_vars(raw_config)

        # Parse MCPs
        if "mcps" in self.config_data:
            for mcp_data in self.config_data["mcps"]:
                mcp_config = self._parse_mcp_config(mcp_data)
                self.mcps[mcp_config.name] = mcp_config

        # Parse teams
        if "teams" in self.config_data:
            for team_data in self.config_data["teams"]:
                team_config = self._parse_team_config(team_data)
                self.teams[team_config.name] = team_config

                # Index agents by name
                for agent in team_config.agents:
                    self.agents[f"{team_config.name}:{agent.name}"] = agent

    def _substitute_env_vars(self, obj: any) -> any:
        """Recursively substitute environment variables."""
        if isinstance(obj, str):
            # Replace ${VAR} with environment variable
            import re

            def replace_var(match):
                var_name = match.group(1)
                default_value = match.group(2) if match.group(2) else None
                return os.environ.get(var_name, default_value or f"${{{var_name}}}")

            # Support ${VAR} and ${VAR:default}
            return re.sub(
                r"\$\{([^}:]+)(?::([^}]*))?\}", replace_var, obj
            )
        elif isinstance(obj, dict):
            return {k: self._substitute_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute_env_vars(item) for item in obj]
        else:
            return obj

    def _parse_mcp_config(self, data: Dict) -> MCPConfig:
        """Parse MCP configuration."""
        auth_config = data.get("auth", {})
        return MCPConfig(
            name=data["name"],
            url=data["url"],
            timeout=data.get("timeout", 30.0),
            auth_type=auth_config.get("type", "bearer"),
            auth_token=auth_config.get("token"),
            tools=data.get("tools"),
            enabled=data.get("enabled", True),
        )

    def _parse_team_config(self, data: Dict) -> TeamConfig:
        """Parse team configuration."""
        # Parse agents
        agents = []
        for agent_data in data.get("agents", []):
            agent = AgentConfig(
                name=agent_data["name"],
                model=agent_data["model"],
                description=agent_data.get("description", ""),
                mcps=agent_data.get("mcps", []),
                system_prompt=agent_data.get(
                    "system_prompt",
                    "You are a helpful assistant.",
                ),
                max_tool_calls=agent_data.get("max_tool_calls", 10),
                enabled=agent_data.get("enabled", True),
            )
            agents.append(agent)

        # Parse MCPs
        mcps = []
        for mcp_data in data.get("mcps", []):
            mcp = self._parse_mcp_config(mcp_data)
            mcps.append(mcp)

        return TeamConfig(
            name=data["name"],
            description=data.get("description", ""),
            agents=agents,
            shared_mcps=mcps,
            environment=data.get("environment", "development"),
            enabled=data.get("enabled", True),
        )

    def get_team(self, team_name: str) -> Optional[TeamConfig]:
        """Get team configuration."""
        return self.teams.get(team_name)

    def get_agent(self, team_name: str, agent_name: str) -> Optional[AgentConfig]:
        """Get agent configuration."""
        key = f"{team_name}:{agent_name}"
        return self.agents.get(key)

    def get_agent_mcps(self, team_name: str, agent_name: str) -> List[MCPConfig]:
        """Get MCPs for an agent."""
        agent = self.get_agent(team_name, agent_name)
        if not agent:
            return []

        team = self.get_team(team_name)
        if not team:
            return []

        # Combine team MCPs with agent-specific MCPs
        agent_mcps = [mcp for mcp in team.shared_mcps if mcp.name in agent.mcps]
        return agent_mcps

    def list_teams(self) -> List[str]:
        """List all teams."""
        return list(self.teams.keys())

    def list_agents(self, team_name: str) -> List[str]:
        """List agents in a team."""
        team = self.get_team(team_name)
        return [agent.name for agent in team.agents] if team else []

    def to_dict(self) -> Dict:
        """Convert configuration to dictionary."""
        return {
            "teams": {
                name: {
                    "description": team.description,
                    "environment": team.environment,
                    "agents": {
                        agent.name: {
                            "model": agent.model,
                            "mcps": agent.mcps,
                            "max_tool_calls": agent.max_tool_calls,
                        }
                        for agent in team.agents
                    },
                }
                for name, team in self.teams.items()
            },
            "mcps": {
                mcp.name: {
                    "url": mcp.url,
                    "timeout": mcp.timeout,
                    "auth_type": mcp.auth_type,
                }
                for mcp in self.mcps.values()
            },
        }


class TeamManager:
    """Manages multiple teams and their agents."""

    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize team manager.

        Args:
            config_path: Path to configuration file
        """
        self.config_manager = ConfigManager(config_path)
        self.config_manager.load_config()

    def get_team_status(self, team_name: str) -> Dict:
        """Get status of a team."""
        team = self.config_manager.get_team(team_name)
        if not team:
            return {"error": f"Team not found: {team_name}"}

        agents = self.config_manager.list_agents(team_name)
        return {
            "name": team.name,
            "description": team.description,
            "environment": team.environment,
            "agents": len(agents),
            "agent_names": agents,
            "mcps": len(team.shared_mcps),
            "mcp_names": [mcp.name for mcp in team.shared_mcps],
        }

    def get_agent_status(self, team_name: str, agent_name: str) -> Dict:
        """Get status of an agent."""
        agent = self.config_manager.get_agent(team_name, agent_name)
        if not agent:
            return {"error": f"Agent not found: {team_name}:{agent_name}"}

        mcps = self.config_manager.get_agent_mcps(team_name, agent_name)
        return {
            "name": agent.name,
            "model": agent.model,
            "description": agent.description,
            "mcps": [mcp.name for mcp in mcps],
            "max_tool_calls": agent.max_tool_calls,
            "enabled": agent.enabled,
        }

    def get_all_teams_status(self) -> Dict:
        """Get status of all teams."""
        teams = {}
        for team_name in self.config_manager.list_teams():
            teams[team_name] = self.get_team_status(team_name)
        return teams


def create_example_config() -> str:
    """Create an example configuration file."""
    config = """
# MCPFlow Team Configuration Example

# Global MCPs available to teams
mcps:
  - name: echo
    url: http://localhost:8001
    timeout: 30.0
    auth:
      type: bearer
      token: ${ECHO_API_TOKEN:dev-token-123}
    tools:
      - echo
      - reverse
      - uppercase

  - name: weather
    url: http://localhost:8002
    timeout: 30.0
    auth:
      type: bearer
      token: ${WEATHER_API_TOKEN:dev-token-456}
    tools:
      - get_weather
      - get_forecast
      - list_available_cities

  - name: database
    url: http://localhost:8003
    timeout: 60.0
    auth:
      type: basic
      username: ${DB_USERNAME:admin}
      password: ${DB_PASSWORD:password}

# Teams with agents
teams:
  - name: support-team
    description: Customer support team
    environment: production
    mcps:
      - name: echo
        url: http://prod-echo:8001
        timeout: 30.0
        auth:
          type: bearer
          token: ${SUPPORT_ECHO_TOKEN}
      - name: database
        url: http://prod-db:8003
        timeout: 60.0
        auth:
          type: basic
          username: ${DB_USERNAME}
          password: ${DB_PASSWORD}

    agents:
      - name: support-agent-1
        model: gpt-4
        description: Primary support agent
        mcps:
          - echo
          - database
        system_prompt: |
          You are a helpful customer support agent.
          Use the database to look up customer information.
          Echo tools are available for testing.
        max_tool_calls: 20
        enabled: true

      - name: support-agent-2
        model: gpt-3.5-turbo
        description: Secondary support agent
        mcps:
          - echo
        system_prompt: |
          You are a backup support agent.
          Help with simpler queries using echo tools.
        max_tool_calls: 10
        enabled: true

  - name: analytics-team
    description: Data analytics team
    environment: production
    mcps:
      - name: database
        url: http://prod-db:8003
        timeout: 120.0
        auth:
          type: basic
          username: ${DB_USERNAME}
          password: ${DB_PASSWORD}
      - name: weather
        url: http://prod-weather:8002
        timeout: 30.0
        auth:
          type: bearer
          token: ${ANALYTICS_WEATHER_TOKEN}

    agents:
      - name: analyst-1
        model: gpt-4
        description: Senior data analyst
        mcps:
          - database
          - weather
        system_prompt: |
          You are a senior data analyst.
          Use the database and weather tools to generate insights.
        max_tool_calls: 30
        enabled: true

  - name: dev-team
    description: Development and testing team
    environment: development
    mcps:
      - name: echo
        url: http://localhost:8001
        timeout: 30.0
        auth:
          type: bearer
          token: ${ECHO_API_TOKEN:dev-token-123}
      - name: weather
        url: http://localhost:8002
        timeout: 30.0
        auth:
          type: bearer
          token: ${WEATHER_API_TOKEN:dev-token-456}

    agents:
      - name: dev-agent
        model: gpt-4
        description: Development assistant
        mcps:
          - echo
          - weather
        system_prompt: |
          You are a development assistant.
          Help with testing and debugging using available tools.
        max_tool_calls: 50
        enabled: true
"""
    return config


def main():
    """Run the team config example."""
    print("Team Configuration Example")
    print("=" * 60)

    # Create example config
    config_content = create_example_config()
    config_path = "example_config.yaml"

    print(f"\nCreating example configuration: {config_path}")
    with open(config_path, "w") as f:
        f.write(config_content)

    # Load and display config
    print("Loading configuration...")
    manager = TeamManager(config_path)

    print("\nTeams Overview:")
    print("-" * 60)
    all_teams = manager.get_all_teams_status()
    for team_name, status in all_teams.items():
        print(f"\n{team_name}:")
        print(f"  Description: {status['description']}")
        print(f"  Environment: {status['environment']}")
        print(f"  Agents: {status['agents']}")
        for agent_name in status["agent_names"]:
            print(f"    - {agent_name}")
        print(f"  MCPs: {status['mcps']}")
        for mcp_name in status["mcp_names"]:
            print(f"    - {mcp_name}")

    print("\n" + "=" * 60)
    print("Agent Details:")
    print("-" * 60)

    for team_name in manager.config_manager.list_teams():
        for agent_name in manager.config_manager.list_agents(team_name):
            agent_status = manager.get_agent_status(team_name, agent_name)
            print(f"\n{team_name}:{agent_name}")
            print(f"  Model: {agent_status['model']}")
            print(f"  Description: {agent_status['description']}")
            print(f"  MCPs: {', '.join(agent_status['mcps'])}")
            print(f"  Max Tool Calls: {agent_status['max_tool_calls']}")

    print("\n" + "=" * 60)
    print("Configuration Summary:")
    print("-" * 60)
    config_dict = manager.config_manager.to_dict()
    print(f"Teams: {len(config_dict['teams'])}")
    print(f"Total Agents: {sum(len(t['agents']) for t in config_dict['teams'].values())}")
    print(f"MCPs: {len(config_dict['mcps'])}")

    # Cleanup
    os.remove(config_path)
    print(f"\nCleaned up {config_path}")


if __name__ == "__main__":
    main()
