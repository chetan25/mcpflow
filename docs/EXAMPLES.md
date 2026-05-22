# MCPFlow Examples

Practical examples demonstrating MCPFlow's capabilities and patterns.

## Table of Contents

- [Simple Echo MCP](#simple-echo-mcp)
- [Weather MCP Example](#weather-mcp-example)
- [Multi-MCP Agent](#multi-mcp-agent)
- [Testing Patterns](#testing-patterns)
- [Advanced Patterns](#advanced-patterns)

## Simple Echo MCP

A minimal MCP server example that demonstrates basic tool registration.

### Server Implementation

```python
# servers/echo/server.py
from mcpflow import MCPServerDecorator, tool

@MCPServerDecorator("echo-server", "0.1.0", "A simple echo server")
class EchoServer:
    """Echoes messages back to the caller."""
    
    @tool("echo", "Echo a message back")
    def echo(self, message: str) -> str:
        """Echo the input message.
        
        Args:
            message: The message to echo
            
        Returns:
            The echoed message
        """
        return f"Echo: {message}"
    
    @tool("repeat", "Repeat a message N times")
    def repeat(self, message: str, count: int = 3) -> str:
        """Repeat a message multiple times.
        
        Args:
            message: The message to repeat
            count: Number of times to repeat
            
        Returns:
            The repeated message
        """
        return "\n".join([message] * count)
```

### Server Runtime

```python
# servers/echo/run.py
import asyncio
from mcpflow import MCPServer
from server import EchoServer

async def main():
    # Create server instance
    echo = EchoServer()
    
    # Create MCPServer wrapper
    server = MCPServer()
    
    # Register tools from decorated class
    for tool_name, tool_def in EchoServer._tools.items():
        handler = getattr(echo, tool_name)
        server.register_tool(tool_def, handler)
    
    # Print available tools
    tools = server.get_tools()
    print(f"✓ Echo server started with {len(tools)} tools:")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description}")
    
    # Simulate tool calls
    result = await server.call_tool("echo", {"message": "Hello, MCPFlow!"})
    print(f"\nTest call: echo('Hello, MCPFlow!') = {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Usage

```bash
python servers/echo/run.py
```

Output:

```
✓ Echo server started with 2 tools:
  - echo: Echo a message back
  - repeat: Repeat a message N times

Test call: echo('Hello, MCPFlow!') = Echo: Hello, MCPFlow!
```

## Weather MCP Example

A realistic MCP server that provides weather information.

### Server Implementation

```python
# servers/weather/server.py
from mcpflow import MCPServerDecorator, tool
from typing import Optional
import json

@MCPServerDecorator(
    "weather-server",
    "1.0.0",
    "Provides weather information for cities"
)
class WeatherServer:
    """Weather information service."""
    
    # Mock weather data
    MOCK_DATA = {
        "new-york": {
            "temperature": 72,
            "condition": "Sunny",
            "humidity": 65,
            "wind_speed": 10
        },
        "london": {
            "temperature": 59,
            "condition": "Rainy",
            "humidity": 85,
            "wind_speed": 15
        },
        "tokyo": {
            "temperature": 68,
            "condition": "Clear",
            "humidity": 55,
            "wind_speed": 5
        }
    }
    
    @tool("get_weather", "Get weather for a city")
    def get_weather(self, city: str) -> dict:
        """Get current weather for a city.
        
        Args:
            city: City name (lowercase, e.g., 'new-york')
            
        Returns:
            Dictionary with weather information
        """
        city_lower = city.lower()
        if city_lower not in self.MOCK_DATA:
            return {
                "error": f"Weather data not available for {city}",
                "available_cities": list(self.MOCK_DATA.keys())
            }
        
        return {
            "city": city,
            "data": self.MOCK_DATA[city_lower]
        }
    
    @tool("compare_weather", "Compare weather between two cities")
    def compare_weather(self, city1: str, city2: str) -> dict:
        """Compare weather between two cities.
        
        Args:
            city1: First city name
            city2: Second city name
            
        Returns:
            Comparison data
        """
        data1 = self.get_weather(city1)
        data2 = self.get_weather(city2)
        
        if "error" in data1 or "error" in data2:
            return {"error": "One or both cities not found"}
        
        return {
            "city1": city1,
            "city2": city2,
            "comparison": {
                "temperature_diff": data1["data"]["temperature"] - data2["data"]["temperature"],
                "city1_weather": data1["data"]["condition"],
                "city2_weather": data2["data"]["condition"]
            }
        }
    
    @tool(
        "alert_weather",
        "Check if weather alerts exist for a city",
        input_schema={
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "alert_type": {
                    "type": "string",
                    "enum": ["storm", "heat", "cold", "flood"]
                }
            },
            "required": ["city", "alert_type"]
        }
    )
    def alert_weather(self, city: str, alert_type: str) -> dict:
        """Check for weather alerts.
        
        Args:
            city: City name
            alert_type: Type of alert to check
            
        Returns:
            Alert status
        """
        return {
            "city": city,
            "alert_type": alert_type,
            "active": False,
            "message": f"No {alert_type} alerts for {city}"
        }
```

### Agent Using Weather MCP

```python
# agents/weather_advisor.py
import asyncio
from mcpflow import ChatManager, MCPRegistry
from mcpflow.config import Config, MCPConfig

async def main():
    # Create registry and register weather MCP
    registry = MCPRegistry()
    
    weather_config = MCPConfig(
        name="weather",
        url="http://localhost:8001"
    )
    
    tools = await registry.register_mcp(weather_config)
    print(f"Available tools: {[t.name for t in tools]}\n")
    
    # Create chat manager
    chat = ChatManager(
        model="gpt-4",
        registry=registry,
        system_prompt="You are a helpful weather advisor. Use the weather tools to provide weather information and recommendations."
    )
    
    # Example queries
    queries = [
        "What's the weather like in New York?",
        "Is it warmer in Tokyo than London?",
        "Tell me about the weather in Paris"
    ]
    
    for query in queries:
        print(f"User: {query}")
        response = await chat.send(query)
        print(f"Agent: {response}\n")
    
    await registry.close_all()

if __name__ == "__main__":
    asyncio.run(main())
```

## Multi-MCP Agent

An agent using multiple MCP servers simultaneously.

### Configuration

```yaml
# config.yaml
teams:
  - name: multi-service-team
    model:
      provider: openai
      name: gpt-4
      api_key: ${OPENAI_API_KEY}
    mcps:
      - name: calculator
        url: http://localhost:8000
      - name: weather
        url: http://localhost:8001
      - name: translator
        url: http://localhost:8002
```

### Agent Implementation

```python
# agents/multi_mcp_agent.py
import asyncio
from mcpflow import ChatManager, MCPRegistry
from mcpflow.config import Config

async def main():
    # Load configuration
    config = Config.from_yaml("config.yaml")
    team = config.get_team("multi-service-team")
    
    if not team:
        print("Team not found")
        return
    
    # Create registry and register all MCPs
    registry = MCPRegistry()
    
    print("Registering MCPs...")
    for mcp_config in team.mcps:
        try:
            tools = await registry.register_mcp(mcp_config)
            print(f"✓ {mcp_config.name}: {len(tools)} tools")
        except Exception as e:
            print(f"✗ {mcp_config.name}: {e}")
    
    # Get all available tools
    all_tools = registry.get_tools()
    print(f"\nTotal tools available: {len(all_tools)}")
    
    # Create chat manager
    chat = ChatManager(
        model=team.model.name,
        registry=registry,
        system_prompt="You are an intelligent assistant with access to multiple services. Use the available tools to help the user."
    )
    
    # Multi-turn conversation
    print("\n" + "="*50)
    print("Multi-MCP Agent Ready")
    print("="*50 + "\n")
    
    messages = [
        "What is 123 + 456?",
        "What's the weather in New York?",
        "Translate 'Hello' to Spanish"
    ]
    
    for msg in messages:
        print(f"User: {msg}")
        response = await chat.send(msg)
        print(f"Agent: {response}\n")
    
    # Show conversation history
    print("\n" + "="*50)
    print("Conversation History")
    print("="*50)
    
    history = chat.get_history_dict()
    for entry in history:
        role = entry["role"].upper()
        print(f"\n{role}:")
        print(f"  {entry['content']}")
        if entry['tool_calls']:
            print(f"  Tool calls: {len(entry['tool_calls'])}")
    
    await registry.close_all()

if __name__ == "__main__":
    asyncio.run(main())
```

## Testing Patterns

### Unit Testing Tools

```python
# tests/test_tools.py
import pytest
from servers.weather.server import WeatherServer

class TestWeatherServer:
    """Test weather server tools."""
    
    def setup_method(self):
        """Setup test server."""
        self.server = WeatherServer()
    
    def test_get_weather_valid_city(self):
        """Test getting weather for a valid city."""
        result = self.server.get_weather("new-york")
        assert result["city"] == "new-york"
        assert "data" in result
        assert "temperature" in result["data"]
    
    def test_get_weather_invalid_city(self):
        """Test getting weather for invalid city."""
        result = self.server.get_weather("unknown-city")
        assert "error" in result
        assert "available_cities" in result
    
    def test_compare_weather(self):
        """Test weather comparison."""
        result = self.server.compare_weather("new-york", "london")
        assert result["city1"] == "new-york"
        assert result["city2"] == "london"
        assert "comparison" in result
    
    def test_alert_weather(self):
        """Test weather alerts."""
        result = self.server.alert_weather("new-york", "storm")
        assert result["city"] == "new-york"
        assert result["alert_type"] == "storm"
        assert "message" in result
```

### Integration Testing with MockServer

```python
# tests/test_integration.py
import pytest
from mcpflow import MockServer, ToolDefinition, create_test_server
from servers.weather.server import WeatherServer

@pytest.mark.asyncio
async def test_weather_tool_execution():
    """Test tool execution with mock server."""
    server = create_test_server()
    
    # Manually register tools from WeatherServer
    weather = WeatherServer()
    
    for tool_name, tool_def in WeatherServer._tools.items():
        handler = getattr(weather, tool_name)
        tool_def_obj = ToolDefinition(
            name=tool_def["name"],
            description=tool_def["description"],
            input_schema=tool_def["input_schema"]
        )
        server.register_tool(tool_def_obj, handler)
    
    # Test tool execution
    result = await server.call_tool("get_weather", {"city": "new-york"})
    assert result["city"] == "new-york"
    
    # Check call history
    history = server.get_call_history()
    assert len(history) > 0
```

### Testing with Registry

```python
# tests/test_registry.py
import pytest
from mcpflow import MCPRegistry
from mcpflow.config import MCPConfig

@pytest.mark.asyncio
async def test_mcp_registry():
    """Test MCPRegistry tool discovery and caching."""
    async with MCPRegistry() as registry:
        # Register MCP
        config = MCPConfig(
            name="test-mcp",
            url="http://localhost:8000"
        )
        
        try:
            tools = await registry.register_mcp(config)
            
            # Verify tools are cached
            cached_tools = registry.get_tools("test-mcp")
            assert len(cached_tools) == len(tools)
            
            # Verify MCP is registered
            assert "test-mcp" in registry.get_registered_mcps()
            
        except Exception as e:
            pytest.skip(f"MCP server not available: {e}")
```

## Advanced Patterns

### Async Tool Handlers

```python
# servers/async_example/server.py
import asyncio
from mcpflow import MCPServerDecorator, tool

@MCPServerDecorator("async-server", "0.1.0", "Async operations")
class AsyncServer:
    """Server with async tool handlers."""
    
    @tool("fetch_data", "Fetch data asynchronously")
    async def fetch_data(self, delay: float = 1.0) -> str:
        """Simulate async data fetching.
        
        Args:
            delay: Delay in seconds
            
        Returns:
            Result string
        """
        await asyncio.sleep(delay)
        return f"Data fetched after {delay}s delay"
    
    @tool("parallel_tasks", "Execute multiple tasks in parallel")
    async def parallel_tasks(self, count: int = 3) -> list:
        """Execute multiple async tasks.
        
        Args:
            count: Number of tasks
            
        Returns:
            List of results
        """
        async def task(n):
            await asyncio.sleep(0.1 * n)
            return f"Task {n} complete"
        
        tasks = [task(i) for i in range(count)]
        results = await asyncio.gather(*tasks)
        return results
```

### Custom Error Handling

```python
# servers/robust_server/server.py
from mcpflow import MCPServerDecorator, tool
import traceback

@MCPServerDecorator("robust-server", "0.1.0", "Robust error handling")
class RobustServer:
    """Server with comprehensive error handling."""
    
    @tool("safe_divide", "Safely divide two numbers")
    def safe_divide(self, numerator: float, denominator: float) -> dict:
        """Divide with error handling.
        
        Returns:
            Result dict with status, value, or error
        """
        try:
            if denominator == 0:
                return {
                    "status": "error",
                    "code": "DIVISION_BY_ZERO",
                    "message": "Cannot divide by zero"
                }
            
            return {
                "status": "success",
                "result": numerator / denominator
            }
            
        except Exception as e:
            return {
                "status": "error",
                "code": "UNEXPECTED_ERROR",
                "message": str(e),
                "traceback": traceback.format_exc()
            }
```

### Tool Composition

```python
# servers/composed_server/server.py
from mcpflow import MCPServerDecorator, tool

@MCPServerDecorator("composed-server", "0.1.0", "Composed operations")
class ComposedServer:
    """Server demonstrating tool composition."""
    
    def _validate_email(self, email: str) -> bool:
        """Helper method for email validation."""
        return "@" in email and "." in email.split("@")[1]
    
    def _format_name(self, name: str) -> str:
        """Helper method for name formatting."""
        return name.strip().title()
    
    @tool("register_user", "Register a new user")
    def register_user(self, name: str, email: str) -> dict:
        """Register user using helper methods.
        
        Args:
            name: User name
            email: User email
            
        Returns:
            Registration result
        """
        try:
            if not self._validate_email(email):
                return {"status": "error", "message": "Invalid email"}
            
            formatted_name = self._format_name(name)
            
            return {
                "status": "success",
                "user": {
                    "name": formatted_name,
                    "email": email,
                    "registered": True
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
```

### Custom JSON Schema

```python
# servers/schema_server/server.py
from mcpflow import MCPServerDecorator, tool
from enum import Enum

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

@MCPServerDecorator("schema-server", "0.1.0", "Custom schemas")
class SchemaServer:
    """Server with custom JSON schemas."""
    
    @tool(
        "create_task",
        "Create a task with priority",
        input_schema={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 200
                },
                "description": {
                    "type": "string",
                    "maxLength": 1000
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "default": "medium"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 5
                }
            },
            "required": ["title"]
        }
    )
    def create_task(
        self,
        title: str,
        description: str = "",
        priority: str = "medium",
        tags: list = None
    ) -> dict:
        """Create a task with validation.
        
        Args:
            title: Task title
            description: Task description
            priority: Priority level
            tags: Task tags
            
        Returns:
            Created task
        """
        return {
            "id": "task-123",
            "title": title,
            "description": description,
            "priority": priority,
            "tags": tags or [],
            "created": True
        }
```

## Running Examples

To run any of these examples:

1. **Setup**:
   ```bash
   pip install mcpflow
   cd example-directory
   ```

2. **Run Server**:
   ```bash
   python servers/*/run.py
   ```

3. **Run Agent** (in another terminal):
   ```bash
   python agents/agent_name.py
   ```

4. **Run Tests**:
   ```bash
   pytest tests/
   ```

For more advanced examples and use cases, see the [full examples directory](https://github.com/mcpflow/mcpflow/tree/main/examples).
