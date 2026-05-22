# MCPFlow - Model Context Protocol Flow Orchestration

MCPFlow is a Python framework for orchestrating and managing Model Context Protocol (MCP) connections with support for tool registration, chat session management, HTTP bridging, and distributed tracing.

## Features

- **Tool Registration & Discovery**: Register and discover MCP tools with automatic schema validation
- **Chat Session Management**: Manage multi-turn conversations with session isolation
- **HTTP Bridging**: Expose MCP servers over HTTP REST endpoints
- **Distributed Tracing**: Built-in OpenTelemetry support for observability
- **Configuration Management**: Environment-based configuration with Pydantic
- **CLI Support**: Command-line tools for server management and administration
- **Testing Utilities**: Mock servers and test fixtures for easy testing

## Quick Start

### Installation

```bash
pip install mcpflow
```

### Basic Usage

```python
from mcpflow import MCPServer, Config, tool

# Create a server with configuration
config = Config(server_name="my-server", debug=True)
server = MCPServer(config)

# Register a tool
@tool("greet", "Greets a user")
def greet_handler(name: str) -> str:
    return f"Hello, {name}!"

from mcpflow import ToolDefinition
tool_def = ToolDefinition(
    name="greet",
    description="Greets a user",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string"}
        },
        "required": ["name"]
    }
)

server.register_tool(tool_def, greet_handler)

# Get all tools
tools = server.get_tools()
print(f"Registered tools: {[t.name for t in tools]}")
```

### Chat Management

```python
from mcpflow import ChatManager, Message

# Create a chat manager
chat = ChatManager()

# Create a session
chat.create_session("user123")

# Add messages
chat.add_message("user123", Message("user", "What is AI?"))
chat.add_message("user123", Message("assistant", "AI is..."))

# Get conversation history
history = chat.get_history("user123")
for msg in history:
    print(f"{msg['role']}: {msg['content']}")
```

### CLI Usage

```bash
# Start the server
mcpflow server --host localhost --port 8000 --debug

# Show version
mcpflow version

# Show server info
mcpflow info
```

## Configuration

MCPFlow uses environment variables prefixed with `MCPFLOW_`:

```bash
export MCPFLOW_SERVER_NAME=my-server
export MCPFLOW_DEBUG=true
export MCPFLOW_LOG_LEVEL=DEBUG
export MCPFLOW_ENABLE_TRACING=true
```

Or configure programmatically:

```python
from mcpflow import Config

config = Config(
    server_name="my-server",
    debug=True,
    log_level="DEBUG",
    enable_tracing=True,
    trace_exporter="otlp"
)
```

## Testing

MCPFlow provides testing utilities:

```python
from mcpflow import MockServer, create_test_server, ToolDefinition

# Create a mock server for testing
mock = MockServer(debug=True)

# Register tools
tool_def = ToolDefinition(name="test", description="Test tool")
async def handler():
    return "test result"

mock.register_tool(tool_def, handler)

# Call tools and inspect history
import asyncio
asyncio.run(mock.call_tool("test", {}))
print(mock.get_call_history())
```

## Architecture

```
mcpflow/
├── server.py       - MCPServer implementation
├── chat.py         - Chat session management
├── config.py       - Configuration management
├── types.py        - Type definitions and Pydantic models
├── registry.py     - Tool registration and discovery
├── http_bridge.py  - HTTP REST bridge
├── tracing.py      - Distributed tracing
├── cli.py          - Command-line interface
└── testing.py      - Testing utilities
```

## API Reference

### MCPServer

Main server class for managing MCP connections and tools.

**Methods:**
- `__init__(config: Optional[Config] = None)` - Initialize server
- `register_tool(tool: ToolDefinition, handler: Callable)` - Register a tool
- `get_tools() -> List[ToolDefinition]` - Get all registered tools
- `call_tool(name: str, params: Dict[str, Any]) -> Any` - Call a tool
- `start()` - Start the server
- `stop()` - Stop the server

### ChatManager

Manages chat sessions and conversation history.

**Methods:**
- `create_session(session_id: str)` - Create a new session
- `add_message(session_id: str, message: Message)` - Add message to session
- `get_history(session_id: str) -> List[Message]` - Get session history
- `clear_session(session_id: str)` - Clear session messages
- `delete_session(session_id: str)` - Delete a session

### Config

Configuration container with environment variable support.

**Fields:**
- `server_name: str` - Server name (default: "mcpflow")
- `server_version: str` - Server version (default: "0.1.0")
- `debug: bool` - Enable debug mode (default: False)
- `log_level: str` - Logging level (default: "INFO")
- `enable_tracing: bool` - Enable tracing (default: False)
- `trace_exporter: str` - Trace exporter type (default: "otlp")
- `max_message_size: int` - Max message size in bytes
- `timeout: float` - Request timeout in seconds (default: 30.0)

## Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/mcpflow/mcpflow.git
cd mcpflow/python

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=mcpflow
```

### Code Style

MCPFlow uses Black, isort, and flake8 for code quality:

```bash
# Format code
black mcpflow tests

# Sort imports
isort mcpflow tests

# Lint
flake8 mcpflow tests
```

### Type Checking

```bash
mypy mcpflow
```

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests to our repository.

## Support

- Documentation: https://mcpflow.dev/docs
- Issues: https://github.com/mcpflow/mcpflow/issues
- Discussions: https://github.com/mcpflow/mcpflow/discussions
