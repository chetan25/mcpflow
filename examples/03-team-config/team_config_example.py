"""Example: Team Configuration with Multiple MCPs."""

from mcpflow import Config, ChatManager, MCPRegistry
import yaml
import asyncio


TEAM_CONFIG_YAML = """
teams:
  - name: "engineering"
    model:
      provider: "openai"
      name: "gpt-4"
      api_key: "${OPENAI_API_KEY}"
    mcps:
      - name: "echo"
        url: "http://localhost:8001"
        auth:
          type: "bearer"
          token: "${ECHO_TOKEN}"
        timeout: 10
      - name: "weather"
        url: "http://localhost:8002"
        timeout: 10
  
  - name: "data-science"
    model:
      provider: "anthropic"
      name: "claude-opus"
      api_key: "${ANTHROPIC_API_KEY}"
    mcps:
      - name: "analytics"
        url: "http://localhost:8003"
        timeout: 15
"""


def main():
    """Demonstrate team configuration loading."""
    print("=== MCPFlow Team Configuration Example ===\n")
    
    # Load config from YAML
    config_dict = yaml.safe_load(TEAM_CONFIG_YAML)
    config = Config.from_dict(config_dict)
    
    print("✓ Loaded team configuration\n")
    
    # Show teams
    print("Registered Teams:")
    for team in config.teams:
        print(f"  • {team.name}")
        print(f"    - Model: {team.model.name} ({team.model.provider})")
        print(f"    - MCPs: {len(team.mcps)}")
        for mcp in team.mcps:
            print(f"      - {mcp.name} @ {mcp.url}")
    
    print("\n✓ Configuration loaded successfully!")
    print(f"✓ Total teams: {len(config.teams)}")
    print(f"✓ Total MCPs: {sum(len(team.mcps) for team in config.teams)}")
    
    # Example: Get team config
    print("\n--- Accessing Team Config ---")
    eng_team = config.get_team("engineering")
    if eng_team:
        print(f"Engineering team model: {eng_team.model.name}")
        print(f"Available MCPs: {[m.name for m in eng_team.mcps]}")


if __name__ == "__main__":
    main()
