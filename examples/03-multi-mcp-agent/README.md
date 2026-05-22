# Multi-MCP Agent Example

This example demonstrates building an intelligent agent that:

- **Orchestrates multiple MCP servers** (echo and weather)
- **Routes tool calls** to the appropriate MCP
- **Discovers available tools** from multiple sources
- **Integrates with ChatManager** for conversation
- **Manages tool execution** across MCPs

## Features

This example builds an agent with:

1. **MCP Registry** - Tracks available MCPs
2. **Tool Registry** - Maintains tools from all MCPs
3. **Chat Manager** - Handles conversations with tool integration
4. **Tool Routing** - Routes calls to correct MCP

## MCPs Used

### Echo MCP (3 tools)

- `echo` - Echo text back
- `reverse` - Reverse text
- `uppercase` - Convert to uppercase

### Weather MCP (3 tools)

- `get_weather` - Current weather for a city
- `get_forecast` - Multi-day forecast
- `list_available_cities` - List supported cities

Total: **6 tools** available to the agent

## Running

### Installation and Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest test_agent.py -v

# Run specific test class
pytest test_agent.py::TestToolDiscovery -v

# Run with verbose output
pytest test_agent.py -vv
```

### Expected Output

```
test session starts ...
collected 26 items

test_agent.py::TestAgentInitialization::test_agent_creates_successfully PASSED [ 3%]
test_agent.py::TestAgentInitialization::test_agent_has_registries PASSED [ 7%]
...
======================== 26 passed in 0.23s ========================
```

### Running the Agent

```bash
python agent.py
```

Output:
```
Multi-MCP Agent Example
==================================================

Available MCPs:

ECHO MCP (3 tools):
  - echo: Echo text
  - reverse: Reverse text
  - uppercase: Convert text to uppercase

WEATHER MCP (3 tools):
  - get_weather: Get current weather for a city
  - get_forecast: Get weather forecast
  - list_available_cities: List available cities

==================================================
Example Operations:
==================================================

1. Echo 'hello' using echo MCP:
   Result: {'result': 'hello', 'mcp': 'echo', 'tool': 'echo'}

2. Reverse 'hello' using echo MCP:
   Result: {'result': 'olleh', 'mcp': 'echo', 'tool': 'reverse'}

...
```

## Key Concepts

### 1. Registry Pattern

The agent maintains two registries:

```python
class MultiMCPAgent:
    def __init__(self):
        self.registry = MCPRegistry()      # MCP servers
        self.tool_registry = ToolRegistry() # Tools from all MCPs
```

### 2. Tool Discovery

Discover tools from a specific MCP:

```python
def get_tools_by_mcp(self, mcp_name: str) -> List[Dict]:
    return [
        tool.to_dict()
        for tool in self.tool_registry.list_tools()
        if tool.mcp == mcp_name
    ]
```

### 3. Tool Routing

Route tool calls to the appropriate MCP:

```python
def simulate_tool_call(self, tool_name: str, mcp_name: str, inputs: Dict):
    if mcp_name == "echo":
        return self._simulate_echo_tool(tool_name, inputs)
    elif mcp_name == "weather":
        return self._simulate_weather_tool(tool_name, inputs)
```

### 4. ChatManager Integration

The ChatManager orchestrates conversations:

```python
self.chat_manager = ChatManager(
    model="gpt-4",
    registry=self.registry
)
```

In production, ChatManager:
- Sends user messages to the LLM
- Parses tool calls from LLM responses
- Executes tools via the MCPs
- Returns results to the LLM
- Manages conversation history

## Configuration

Create an `agent_config.yaml`:

```yaml
agent:
  model: gpt-4
  max_tool_calls: 10
  system_prompt: "You are a helpful assistant with access to multiple services"

mcps:
  - name: echo
    url: http://localhost:8001
    auth:
      type: bearer
      token: ${ECHO_TOKEN}

  - name: weather
    url: http://localhost:8002
    auth:
      type: bearer
      token: ${WEATHER_TOKEN}

  - name: database
    url: http://localhost:8003
```

## Usage Patterns

### 1. Simple Query

```python
agent = MultiMCPAgent()

# Get available tools
tools = agent.get_available_tools()
print(f"Available tools: {len(tools)}")

# Call a specific tool
result = agent.simulate_tool_call(
    "get_weather",
    "weather",
    {"city": "London"}
)
```

### 2. Multi-Step Operations

```python
# Chain multiple tool calls
echo_result = agent.simulate_tool_call("echo", "echo", {"text": "test"})
weather_result = agent.simulate_tool_call("get_weather", "weather", {"city": "Tokyo"})

# Process results
print(f"Echo: {echo_result['result']}")
print(f"Weather: {weather_result['temperature']}°")
```

### 3. Tool Discovery and Selection

```python
# Find tools for a specific purpose
weather_tools = agent.get_tools_by_mcp("weather")
echo_tools = agent.get_tools_by_mcp("echo")

# List available options
for tool in weather_tools:
    print(f"{tool['name']}: {tool['description']}")
```

## Testing Patterns

### Unit Tests

Test individual components:

```python
def test_agent_creates_successfully(self):
    agent = MultiMCPAgent()
    assert agent is not None
```

### Integration Tests

Test tool routing:

```python
def test_tool_routing(self):
    # Echo tools only in echo MCP
    echo_tools = agent.get_tools_by_mcp("echo")
    assert "echo" in {t["name"] for t in echo_tools}
    assert "get_weather" not in {t["name"] for t in echo_tools}
```

### End-to-End Tests

Test agent workflows:

```python
def test_mixed_mcp_operations(self):
    echo_result = agent.simulate_tool_call("echo", "echo", {"text": "weather"})
    weather_result = agent.simulate_tool_call("get_weather", "weather", {"city": "Tokyo"})
    assert "error" not in echo_result
    assert "error" not in weather_result
```

## Advanced Topics

### Custom Tool Resolution

Implement tool resolvers for dynamic lookup:

```python
class CustomAgentAgent(MultiMCPAgent):
    def resolve_tool(self, tool_name: str):
        # Custom logic to find the best MCP for a tool
        pass
```

### Error Recovery

Handle MCP failures gracefully:

```python
def safe_tool_call(self, tool_name, mcp_name, inputs):
    try:
        return self.simulate_tool_call(tool_name, mcp_name, inputs)
    except Exception as e:
        return {"error": str(e), "fallback": True}
```

### Performance Optimization

Cache tool metadata:

```python
class CachedAgent(MultiMCPAgent):
    def __init__(self):
        super().__init__()
        self._tool_cache = {}
        self._cache_tools()
```

## Next Steps

- See `04-team-config` for production configuration patterns
- Implement actual LLM integration with ChatManager
- Add persistence for agent state
- Implement tool execution tracing
