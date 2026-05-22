# Simple Echo Server Example

This is the simplest MCPFlow example, demonstrating the core concepts:

- **MCPServer class**: Base class for creating MCP servers
- **@tool decorator**: For registering tools with automatic schema generation
- **Tool implementation**: Simple methods that become callable tools

## Features

This example implements a text manipulation server with 6 tools:

1. **echo** - Echo back input text
2. **reverse** - Reverse text characters
3. **uppercase** - Convert to uppercase
4. **lowercase** - Convert to lowercase
5. **char_count** - Count characters
6. **word_count** - Count words

## Running

### Basic Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest test_echo.py -v

# Use the server in your application
python -c "from echo_server import EchoServer; s = EchoServer('test'); print(s.echo('hello'))"
```

### Expected Output

```
test session starts ...
collected 20 items

test_echo.py::TestEchoTool::test_echo_returns_input PASSED           [  5%]
test_echo.py::TestEchoTool::test_echo_with_empty_string PASSED       [ 10%]
...
======================== 20 passed in 0.12s ========================
```

## Key Concepts

### 1. MCPServer Class

```python
class EchoServer(MCPServer):
    @tool("echo", "Echo back the input text")
    def echo(self, text: str) -> str:
        return text
```

The `MCPServer` base class:
- Inherits from MCP protocol implementation
- Automatically registers decorated methods as tools
- Generates JSON schemas from type hints
- Handles tool invocation and routing

### 2. @tool Decorator

```python
@tool("tool_name", "Tool description")
def tool_func(param: str) -> str:
    return result
```

The decorator:
- Takes tool name and description
- Generates JSON schema from type hints
- Supports required and optional parameters
- Maps Python types to JSON schema types

### 3. Type Annotations

The decorator automatically generates schemas from type hints:

```python
def char_count(self, text: str) -> int:
```

Generates schema:
```json
{
  "type": "object",
  "properties": {
    "text": {"type": "string"}
  },
  "required": ["text"]
}
```

### 4. Tools Testing

Tools can be tested directly:

```python
server = EchoServer(name="test")
result = server.echo("hello")
assert result == "hello"
```

## Next Steps

- See `02-weather-mcp` for tools with multiple parameters
- See `03-multi-mcp-agent` for using multiple MCP servers with ChatManager
- See `04-team-config` for configuration-based setup
