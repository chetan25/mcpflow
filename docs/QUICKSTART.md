# MCPFlow Quick Start Guide

Get up and running with MCPFlow in minutes! This guide walks you through creating your first MCP server and integrating it with an agent.

## Installation

### System Requirements

- Python 3.8 or higher
- pip or poetry

### Install MCPFlow

```bash
pip install mcpflow
```

Or with development dependencies:

```bash
pip install mcpflow[dev]
```

Verify the installation:

```bash
python -c "import mcpflow; print(f'MCPFlow {mcpflow.__version__} installed successfully')"
```

## Your First Project

### Initialize a Project

Create a new MCPFlow project using the CLI:

```bash
mcpflow init my-first-project
cd my-first-project
```

This creates a project structure with:

```
my-first-project/
├── config.yaml          # Configuration file
├── servers/
│   └── example/
│       └── server.py    # Example MCP server
├── agents/
│   └── example_agent.py # Example agent
└── tests/
    └── test_server.py   # Test file
```

### Understanding the Generated Structure

- **config.yaml**: Defines MCPs, models, and teams
- **servers/**: MCP server implementations
- **agents/**: Agent implementations that use MCPs
- **tests/**: Test files for your servers and agents

## Creating Your MCP Server

Let's create a simple calculator MCP server:

### 1. Create the Server File

Create `servers/calculator/server.py`:

```python
from mcpflow import MCPServerDecorator, tool

@MCPServerDecorator("calculator", "0.1.0", "A simple calculator MCP server")
class CalculatorServer:
    """Calculator MCP Server with basic math operations."""
    
    @tool("add", "Add two numbers")
    def add(self, a: float, b: float) -> float:
        """Add two numbers and return the result."""
        return a + b
    
    @tool("subtract", "Subtract two numbers")
    def subtract(self, a: float, b: float) -> float:
        """Subtract b from a."""
        return a - b
    
    @tool("multiply", "Multiply two numbers")
    def multiply(self, a: float, b: float) -> float:
        """Multiply two numbers."""
        return a * b
    
    @tool("divide", "Divide two numbers")
    def divide(self, a: float, b: float) -> float:
        """Divide a by b. Raises ValueError if b is 0."""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
```

### 2. Verify Tool Registration

The `@MCPServerDecorator` automatically discovers all `@tool` decorated methods:

```python
# Access server metadata
print(CalculatorServer.name)           # "calculator"
print(CalculatorServer.version)        # "0.1.0"
print(CalculatorServer.description)    # "A simple calculator MCP server"
print(CalculatorServer._tools.keys())  # ['add', 'subtract', 'multiply', 'divide']
```

## Using Your MCP in an Agent

### 1. Create a Configuration File

Create `config.yaml`:

```yaml
teams:
  - name: calculator-team
    model:
      provider: openai
      name: gpt-4
      api_key: ${OPENAI_API_KEY}
    mcps:
      - name: calculator
        url: http://localhost:8000
        auth:
          type: bearer
          token: ${CALCULATOR_TOKEN}
```

### 2. Create an Agent

Create `agents/calculator_agent.py`:

```python
import asyncio
from mcpflow import ChatManager, MCPRegistry
from mcpflow.config import Config, MCPConfig, AuthConfig

async def main():
    # Load configuration
    config = Config.from_yaml("config.yaml")
    
    # Create registry and register MCP
    registry = MCPRegistry()
    
    # Get calculator MCP config
    team = config.get_team("calculator-team")
    if not team:
        print("Team 'calculator-team' not found")
        return
    
    mcp_config = None
    for mcp in team.mcps:
        if mcp.name == "calculator":
            mcp_config = mcp
            break
    
    if not mcp_config:
        print("Calculator MCP not found in team")
        return
    
    # Register MCP and discover tools
    tools = await registry.register_mcp(mcp_config)
    print(f"Discovered {len(tools)} tools: {[t.name for t in tools]}")
    
    # Create chat manager
    chat_manager = ChatManager(
        model=team.model.name,
        registry=registry,
        system_prompt="You are a helpful math assistant. Use the calculator tools to solve math problems."
    )
    
    # Example conversation
    print("\n=== Chat Example ===")
    response = await chat_manager.send("What is 15 * 7?")
    print(f"Agent: {response}")
    
    # Clean up
    await registry.close_all()

if __name__ == "__main__":
    asyncio.run(main())
```

### 3. Run the Agent

```bash
# Set environment variables
export OPENAI_API_KEY="your-api-key"
export CALCULATOR_TOKEN="your-token"

# Run the agent
python agents/calculator_agent.py
```

## Running and Testing

### Starting an MCP Server

```python
# servers/calculator/run.py
import asyncio
from mcpflow import MCPServer
from server import CalculatorServer

async def main():
    # Create an instance of your server
    calc_server = CalculatorServer()
    
    # Create MCPServer wrapper
    server = MCPServer()
    
    # Register tools from the decorated class
    for tool_name, tool_def in CalculatorServer._tools.items():
        handler = getattr(calc_server, tool_name)
        server.register_tool(tool_def, handler)
    
    print(f"Server started with {len(server.get_tools())} tools")
    # Server would typically listen for HTTP requests or stdio

if __name__ == "__main__":
    asyncio.run(main())
```

### Testing Your Server

Create `tests/test_calculator.py`:

```python
import pytest
from mcpflow import MockServer, ToolDefinition
from servers.calculator.server import CalculatorServer

@pytest.mark.asyncio
async def test_calculator_server():
    """Test calculator server tools."""
    # Create server instance
    calc = CalculatorServer()
    
    # Test addition
    result = calc.add(5, 3)
    assert result == 8
    
    # Test division by zero
    with pytest.raises(ValueError):
        calc.divide(10, 0)
    
    # Test multiplication
    result = calc.multiply(4, 5)
    assert result == 20

@pytest.mark.asyncio
async def test_with_mock_server():
    """Test using MCPFlow's MockServer."""
    from mcpflow import create_test_server
    
    # Create a test server with calculator tools
    server = create_test_server()
    
    # Verify server created successfully
    assert server is not None
```

Run tests:

```bash
pytest tests/
pytest tests/ -v --cov=servers
```

## Common Patterns

### Custom JSON Schema

Define custom input schemas for your tools:

```python
from mcpflow import tool

@tool(
    "complex_math",
    "Performs complex math operations",
    input_schema={
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["sqrt", "pow", "log"]
            },
            "value": {"type": "number"},
            "exponent": {"type": "number"}
        },
        "required": ["operation", "value"]
    }
)
def complex_math(operation: str, value: float, exponent: float = 2.0) -> float:
    """Perform complex math operations."""
    if operation == "sqrt":
        return value ** 0.5
    elif operation == "pow":
        return value ** exponent
    elif operation == "log":
        import math
        return math.log(value)
    raise ValueError(f"Unknown operation: {operation}")
```

### Async Tool Handlers

MCPFlow supports both sync and async tool handlers:

```python
@tool("fetch_data", "Fetch data from an API")
async def fetch_data(url: str) -> dict:
    """Fetch JSON data from a URL."""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
```

### Error Handling

Return structured error responses:

```python
@tool("risky_operation", "An operation that might fail")
def risky_operation(input_data: str) -> dict:
    """Perform a risky operation."""
    try:
        # Your operation here
        result = process_data(input_data)
        return {"status": "success", "result": result}
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}
```

## Next Steps

- **[Read the Architecture Guide](ARCHITECTURE.md)** - Understand MCPFlow's system design
- **[API Reference](API-REFERENCE.md)** - Complete API documentation
- **[Advanced Examples](EXAMPLES.md)** - More complex use cases
- **[Contributing Guide](../CONTRIBUTING.md)** - Help improve MCPFlow

## Getting Help

- Check the [FAQ](#faq) section below
- Browse [GitHub Issues](https://github.com/mcpflow/mcpflow/issues)
- Join the community discussions

## FAQ

**Q: How do I connect to a real MCP server?**
A: Use the `MCPRegistry` to register an MCP server with its URL. MCPFlow will automatically discover available tools via HTTP.

**Q: Can I use MCPFlow with different LLM providers?**
A: Yes! MCPFlow's `ChatManager` supports any model name. You configure the provider and API key in your `config.yaml`.

**Q: How do I test my MCP servers?**
A: Use `MockServer` and `create_test_server()` from `mcpflow.testing`. See the testing examples above.

**Q: Is MCPFlow async?**
A: Yes, MCPFlow is fully async. Use `async def` for your tool handlers and `await` when calling async functions.

**Q: How do I enable tracing?**
A: MCPFlow has built-in OpenTelemetry support. Set `enable_tracing: true` in your config or use `setup_tracing()`.
