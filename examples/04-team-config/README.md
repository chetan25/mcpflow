# Team Configuration Example

This example demonstrates production-ready configuration patterns:

- **Complete team setup** with multiple teams and agents
- **YAML configuration** for deployments
- **Environment variable substitution** for sensitive data
- **Multi-agent architecture** with different roles
- **Flexible MCP assignment** to agents

## Features

This example implements:

1. **ConfigManager** - Loads and parses YAML configurations
2. **TeamConfig** - Team definition with agents and MCPs
3. **AgentConfig** - Individual agent configuration
4. **TeamManager** - Manages multiple teams and provides status

## Running

### Installation and Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest test_team_config.py -v

# Run specific test class
pytest test_team_config.py::TestTeamManager -v

# Run with coverage
pytest test_team_config.py --cov=team_config
```

### Expected Output

```
test session starts ...
collected 39 items

test_team_config.py::TestConfigManager::test_config_manager_initialization PASSED [ 2%]
...
======================== 39 passed in 0.42s ========================
```

### Running the Example

```bash
python team_config.py
```

Output:
```
Team Configuration Example
============================================================

Creating example configuration: example_config.yaml
Loading configuration...

Teams Overview:
------------------------------------------------------------

support-team:
  Description: Customer support team
  Environment: production
  Agents: 2
    - support-agent-1
    - support-agent-2
  MCPs: 2
    - echo
    - database

analytics-team:
  Description: Data analytics team
  Environment: production
  Agents: 1
    - analyst-1
  MCPs: 2
    - database
    - weather

dev-team:
  Description: Development and testing team
  Environment: development
  Agents: 1
    - dev-agent
  MCPs: 2
    - echo
    - weather

============================================================
Agent Details:
------------------------------------------------------------

support-team:support-agent-1
  Model: gpt-4
  Description: Primary support agent
  MCPs: echo, database
  Max Tool Calls: 20

...
```

## Configuration File Format

### Basic Structure

```yaml
mcps:
  - name: service-name
    url: http://host:port
    timeout: 30.0
    auth:
      type: bearer
      token: ${ENV_VAR}
    tools:
      - tool1
      - tool2

teams:
  - name: team-name
    description: Team description
    environment: production
    mcps: [MCP definitions]
    agents:
      - name: agent-name
        model: gpt-4
        mcps:
          - service-name
        max_tool_calls: 10
```

### Environment Substitution

Use `${VAR}` or `${VAR:default}` syntax:

```yaml
auth:
  token: ${API_TOKEN}              # Uses $API_TOKEN env var
  password: ${DB_PASS:default}     # Uses $DB_PASS or "default"
```

### Example Teams

#### Support Team

```yaml
- name: support-team
  description: Customer support
  environment: production
  agents:
    - name: agent-1
      model: gpt-4
      mcps: [echo, database]
      max_tool_calls: 20
```

#### Analytics Team

```yaml
- name: analytics-team
  description: Data analysis
  environment: production
  agents:
    - name: analyst
      model: gpt-4
      mcps: [database, weather]
      max_tool_calls: 30
```

## Key Concepts

### 1. Configuration Hierarchy

```
MCPs (Global)
├── Team A
│   ├── Agent 1
│   ├── Agent 2
│   └── Team-specific MCPs
├── Team B
│   ├── Agent 3
│   └── Team-specific MCPs
```

### 2. Environment Variable Substitution

```python
# In YAML:
auth:
  token: ${API_TOKEN:dev-token-123}

# In Python:
manager._substitute_env_vars(config)
# Replaces with:
# - $API_TOKEN env var if set
# - "dev-token-123" if not set
```

### 3. Agent MCP Association

```python
# Get MCPs for an agent
mcps = config_manager.get_agent_mcps("team-name", "agent-name")

# Only MCPs listed in agent.mcps are returned
# These come from team.shared_mcps
```

### 4. Status Reporting

```python
# Team status
status = manager.get_team_status("team-name")
# Returns: name, description, environment, agents, mcps

# Agent status
status = manager.get_agent_status("team-name", "agent-name")
# Returns: name, model, description, mcps, max_tool_calls
```

## Usage Patterns

### 1. Basic Configuration Loading

```python
from team_config import ConfigManager

manager = ConfigManager("config.yaml")
manager.load_config()

# Access teams
team = manager.get_team("support-team")
print(f"Team: {team.name}")

# Access agents
agent = manager.get_agent("support-team", "agent-1")
print(f"Agent: {agent.name}, Model: {agent.model}")

# Get agent MCPs
mcps = manager.get_agent_mcps("support-team", "agent-1")
for mcp in mcps:
    print(f"MCP: {mcp.name} at {mcp.url}")
```

### 2. Team Management

```python
from team_config import TeamManager

manager = TeamManager("config.yaml")

# Get all teams
teams = manager.get_all_teams_status()
for team_name, status in teams.items():
    print(f"{team_name}: {status['description']}")

# Get specific team
team_status = manager.get_team_status("support-team")
print(f"Support team has {team_status['agents']} agents")
```

### 3. Agent Status

```python
# Get agent details
agent_status = manager.get_agent_status("support-team", "agent-1")

print(f"Agent: {agent_status['name']}")
print(f"Model: {agent_status['model']}")
print(f"Available MCPs: {agent_status['mcps']}")
print(f"Max tool calls: {agent_status['max_tool_calls']}")
```

### 4. Configuration Export

```python
# Export to dictionary
config_dict = manager.config_manager.to_dict()

# Use for API responses, logging, etc.
import json
print(json.dumps(config_dict, indent=2))
```

## Deployment Guide

### Development Environment

```bash
# Set local environment variables
export ECHO_API_TOKEN=dev-token-123
export WEATHER_API_TOKEN=dev-token-456
export DB_USERNAME=admin
export DB_PASSWORD=password

# Start with dev config
python -c "from team_config import TeamManager; m = TeamManager('config.yaml')"
```

### Production Environment

```bash
# Set production tokens (from secrets manager)
export SUPPORT_ECHO_TOKEN=$(aws secretsmanager get-secret-value --secret-id echo-token --query SecretString --output text)
export ANALYTICS_WEATHER_TOKEN=$(aws secretsmanager get-secret-value --secret-id weather-token --query SecretString --output text)
export DB_USERNAME=$(aws secretsmanager get-secret-value --secret-id db-user --query SecretString --output text)
export DB_PASSWORD=$(aws secretsmanager get-secret-value --secret-id db-pass --query SecretString --output text)

# Load production config
python service.py --config config.yaml
```

### Docker Deployment

```dockerfile
FROM python:3.11

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY team_config.py config.yaml ./

ENV ECHO_API_TOKEN=${ECHO_API_TOKEN}
ENV WEATHER_API_TOKEN=${WEATHER_API_TOKEN}
ENV DB_USERNAME=${DB_USERNAME}
ENV DB_PASSWORD=${DB_PASSWORD}

CMD ["python", "-c", "from team_config import main; main()"]
```

### Docker Compose

```yaml
version: '3'
services:
  app:
    build: .
    environment:
      - ECHO_API_TOKEN=${ECHO_API_TOKEN}
      - WEATHER_API_TOKEN=${WEATHER_API_TOKEN}
      - DB_USERNAME=${DB_USERNAME}
      - DB_PASSWORD=${DB_PASSWORD}
    depends_on:
      - echo-service
      - weather-service
      - db-service
```

## Testing Patterns

### Unit Tests

Test configuration parsing:

```python
def test_agent_config_creation(self):
    manager = ConfigManager("config.yaml")
    manager.load_config()
    agent = manager.get_agent("team", "agent")
    assert agent.name == "agent"
```

### Integration Tests

Test multi-team configuration:

```python
def test_multiple_teams_loaded(self):
    manager = TeamManager("config.yaml")
    teams = manager.get_all_teams_status()
    assert len(teams) > 0
```

### Environment Tests

Test variable substitution:

```python
def test_env_substitution(self):
    os.environ["TEST_VAR"] = "value"
    manager = ConfigManager()
    result = manager._substitute_env_vars({"key": "${TEST_VAR}"})
    assert result["key"] == "value"
```

## Advanced Topics

### Custom MCP Resolution

```python
class CustomConfigManager(ConfigManager):
    def resolve_mcp_url(self, mcp_name, environment):
        # Custom logic to select URL based on environment
        if environment == "production":
            return f"https://prod-{mcp_name}.example.com"
        else:
            return f"http://localhost:8000"
```

### Dynamic Configuration

```python
class DynamicConfigManager(ConfigManager):
    def load_config(self):
        # Load from Consul, etcd, or other service registry
        config = self.fetch_from_consul()
        self.config_data = config
        # Rest of loading...
```

### Configuration Validation

```python
class ValidatedConfigManager(ConfigManager):
    def validate_config(self):
        # Validate required fields
        # Check URL accessibility
        # Verify authentication tokens
        pass
```

## Next Steps

- Implement actual service instantiation from configuration
- Add configuration hot-reloading
- Integrate with service discovery
- Add metrics and monitoring configuration
- Implement configuration version control
