# MCPFlow API Reference

Complete API documentation for MCPFlow v0.1.0.

## Table of Contents

- [Decorators](#decorators)
- [Core Classes](#core-classes)
- [Registry](#registry)
- [Chat Management](#chat-management)
- [Configuration](#configuration)
- [HTTP Bridge](#http-bridge)
- [Tracing](#tracing)
- [Testing](#testing)
- [CLI](#cli)
- [Types](#types)

## Decorators

### @tool

Decorator for registering individual tools with automatic JSON schema generation.

**Signature**:

```python
def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    input_schema: Optional[Dict[str, Any]] = None
) -> Callable
```

**Parameters**:

- `name` (Optional[str]): Tool name. Defaults to function name if not provided.
- `description` (Optional[str]): Tool description. Defaults to function docstring.
- `input_schema` (Optional[Dict[str, Any]]): Custom JSON schema for inputs. Auto-generated from type hints if not provided.

**Returns**: Decorator function that adds MCP metadata to the function.

**Example**:

```python
from mcpflow import tool

@tool("add", "Add two numbers")
def add(a: float, b: float) -> float:
    """Add two numbers and return the result."""
    return a + b

@tool("greet", input_schema={
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer", "minimum": 0}
    },
    "required": ["name"]
})
def greet(name: str, age: int = 0) -> str:
    if age > 0:
        return f"Hello {name}, you are {age} years old!"
    return f"Hello {name}!"
```

**Metadata Storage**:

The decorator stores metadata on the function:

```python
func._mcp_tool = {
    "name": str,
    "description": str,
    "input_schema": Dict[str, Any]
}
```

### @MCPServerDecorator

Class-level decorator for automatic MCP server definition and tool discovery.

**Signature**:

```python
def MCPServerDecorator(
    name: Optional[str] = None,
    version: Optional[str] = None,
    description: Optional[str] = None
) -> Callable
```

**Parameters**:

- `name` (Optional[str]): Server name. Defaults to class name if not provided.
- `version` (Optional[str]): Server version. Defaults to "0.1.0".
- `description` (Optional[str]): Server description. Defaults to class docstring.

**Returns**: Class decorator that registers all `@tool` decorated methods.

**Class Attributes Added**:

- `name` (str): Server name
- `version` (str): Server version
- `description` (str): Server description
- `_tools` (Dict[str, Dict[str, Any]]): Dictionary of tool definitions
- `_tool_methods` (Dict[str, Callable]): Dictionary of tool handler methods
- `_server_def` (MCPServerDef): Server definition object

**Example**:

```python
from mcpflow import MCPServerDecorator, tool

@MCPServerDecorator("math-server", "1.0.0", "Mathematical operations")
class MathServer:
    """A server for mathematical calculations."""
    
    @tool("add", "Add two numbers")
    def add(self, a: float, b: float) -> float:
        return a + b
    
    @tool("multiply", "Multiply two numbers")
    def multiply(self, a: float, b: float) -> float:
        return a * b
    
    # Access metadata
    # MathServer.name == "math-server"
    # MathServer.version == "1.0.0"
    # list(MathServer._tools.keys()) == ["add", "multiply"]
```

## Core Classes

### MCPServer

Main server class for managing MCP connections and tools.

**Signature**:

```python
class MCPServer:
    def __init__(self, config: Optional[Config] = None) -> None
```

**Parameters**:

- `config` (Optional[Config]): Server configuration. Creates default Config if not provided.

**Methods**:

#### register_tool(tool, handler)

Register a tool with the server.

```python
def register_tool(self, tool: ToolDefinition, handler: Callable) -> None
```

**Parameters**:

- `tool` (ToolDefinition): Tool definition
- `handler` (Callable): Function/coroutine to handle tool invocation

**Example**:

```python
from mcpflow import MCPServer, ToolDefinition

server = MCPServer()

tool_def = ToolDefinition(
    name="echo",
    description="Echo a message",
    input_schema={"type": "object", "properties": {"message": {"type": "string"}}}
)

def echo_handler(message: str) -> str:
    return message

server.register_tool(tool_def, echo_handler)
```

#### get_tools()

Get all registered tools.

```python
def get_tools(self) -> List[ToolDefinition]
```

**Returns**: List of ToolDefinition objects.

**Example**:

```python
tools = server.get_tools()
for tool in tools:
    print(f"{tool.name}: {tool.description}")
```

#### call_tool(name, params)

Call a registered tool.

```python
async def call_tool(self, name: str, params: Dict[str, Any]) -> Any
```

**Parameters**:

- `name` (str): Tool name
- `params` (Dict[str, Any]): Tool parameters

**Returns**: Tool result

**Raises**: 
- `ValueError`: If tool not found

**Example**:

```python
result = await server.call_tool("echo", {"message": "Hello"})
print(result)  # "Hello"
```

#### start()

Start the server (not yet implemented in v0.1.0).

```python
async def start(self) -> None
```

#### stop()

Stop the server (not yet implemented in v0.1.0).

```python
async def stop(self) -> None
```

### Message

Represents a message in a chat conversation.

**Signature**:

```python
@dataclass
class Message:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tool_calls: List[ToolCall] = field(default_factory=list)
```

**Attributes**:

- `role` (str): Message role ("user", "assistant", "system")
- `content` (str): Message text
- `timestamp` (datetime): When the message was created
- `tool_calls` (List[ToolCall]): Associated tool calls

**Methods**:

#### to_dict()

Convert message to dictionary.

```python
def to_dict(self) -> Dict[str, Any]
```

**Returns**: Dictionary representation with ISO format timestamp.

**Example**:

```python
from mcpflow import Message

msg = Message(role="user", content="Hello!")
print(msg.to_dict())
# {
#     "role": "user",
#     "content": "Hello!",
#     "timestamp": "2024-05-22T12:40:00.000000",
#     "tool_calls": []
# }
```

### ToolCall

Represents a tool call within a message.

**Signature**:

```python
@dataclass
class ToolCall:
    tool_name: str
    mcp_name: str
    inputs: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
```

**Attributes**:

- `tool_name` (str): Name of the tool
- `mcp_name` (str): Name of the MCP server
- `inputs` (Dict[str, Any]): Tool input parameters
- `result` (Optional[Dict[str, Any]]): Tool execution result
- `error` (Optional[str]): Error message if execution failed

## Registry

### ToolRegistry

Local tool registry for direct Python tool registration.

**Signature**:

```python
class ToolRegistry:
    def __init__(self) -> None
```

**Methods**:

#### register(tool, handler, namespace="default")

Register a tool.

```python
def register(
    self,
    tool: ToolDefinition,
    handler: Callable,
    namespace: str = "default"
) -> None
```

**Parameters**:

- `tool` (ToolDefinition): Tool definition
- `handler` (Callable): Handler function
- `namespace` (str): Optional namespace for organization

#### get(name)

Get a tool definition.

```python
def get(self, name: str) -> Optional[ToolDefinition]
```

**Returns**: ToolDefinition or None if not found.

#### get_handler(name)

Get a tool handler.

```python
def get_handler(self, name: str) -> Optional[Callable]
```

**Returns**: Handler function or None if not found.

#### list_tools(namespace=None)

List all tools, optionally filtered by namespace.

```python
def list_tools(self, namespace: Optional[str] = None) -> List[ToolDefinition]
```

**Returns**: List of ToolDefinition objects.

#### list_namespaces()

List all namespaces.

```python
def list_namespaces(self) -> List[str]
```

**Returns**: List of namespace names.

### MCPRegistry

Registry for managing MCP server connections and tool discovery.

**Signature**:

```python
class MCPRegistry:
    def __init__(self) -> None
```

**Methods**:

#### register_mcp(config)

Register an MCP server and discover its tools.

```python
async def register_mcp(self, config: MCPConfig) -> List[ToolDefinition]
```

**Parameters**:

- `config` (MCPConfig): MCP server configuration

**Returns**: List of discovered tools

**Raises**: 
- `httpx.HTTPError`: If discovery fails

**Example**:

```python
from mcpflow import MCPRegistry
from mcpflow.config import MCPConfig

registry = MCPRegistry()
config = MCPConfig(
    name="calculator",
    url="http://localhost:8000"
)
tools = await registry.register_mcp(config)
```

#### get_tools(mcp_name=None)

Get tools from registry.

```python
def get_tools(self, mcp_name: Optional[str] = None) -> List[ToolDefinition]
```

**Parameters**:

- `mcp_name` (Optional[str]): Specific MCP name. If None, returns all tools.

**Returns**: List of ToolDefinition objects.

#### call_tool(mcp_name, tool_name, inputs)

Call a tool on a specific MCP server.

```python
async def call_tool(
    self,
    mcp_name: str,
    tool_name: str,
    inputs: Dict[str, Any]
) -> Dict[str, Any]
```

**Parameters**:

- `mcp_name` (str): Name of the MCP server
- `tool_name` (str): Name of the tool
- `inputs` (Dict[str, Any]): Tool input parameters

**Returns**: Tool execution result

**Raises**:
- `ValueError`: If MCP or tool not found

#### get_registered_mcps()

Get list of registered MCP names.

```python
def get_registered_mcps(self) -> List[str]
```

**Returns**: List of MCP server names.

#### get_mcp_config(mcp_name)

Get the configuration for an MCP server.

```python
def get_mcp_config(self, mcp_name: str) -> Optional[MCPConfig]
```

**Returns**: MCPConfig or None if not found.

#### close_all()

Close all MCP server connections.

```python
async def close_all(self) -> None
```

#### Async Context Manager

```python
async with MCPRegistry() as registry:
    await registry.register_mcp(config)
    # Use registry
    # Auto cleanup on exit
```

## Chat Management

### ChatManager

Manages chat sessions and message flow with tool execution.

**Signature**:

```python
class ChatManager:
    def __init__(
        self,
        model: Optional[str] = None,
        registry: Optional[MCPRegistry] = None,
        system_prompt: Optional[str] = None,
        max_tool_calls: int = 10
    ) -> None
```

**Parameters**:

- `model` (Optional[str]): Model name/ID for LLM inference
- `registry` (Optional[MCPRegistry]): MCPRegistry instance for tool execution
- `system_prompt` (Optional[str]): System prompt for the chat
- `max_tool_calls` (int): Maximum number of tool calls per message

**Methods**:

#### send(message, model_override=None, context=None)

Send a message to the chat and get a response.

```python
async def send(
    self,
    message: str,
    model_override: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> str
```

**Parameters**:

- `message` (str): User message
- `model_override` (Optional[str]): Override model for this request
- `context` (Optional[Dict[str, Any]]): Additional context for the request

**Returns**: Assistant response string

**Raises**:
- `ValueError`: If no model configured and no override provided

**Example**:

```python
from mcpflow import ChatManager

chat = ChatManager(model="gpt-4")
response = await chat.send("What is the capital of France?")
print(response)
```

#### clear_history()

Clear all message history.

```python
def clear_history(self) -> None
```

#### get_history()

Get the full message history.

```python
def get_history(self) -> List[Message]
```

**Returns**: List of Message objects.

#### get_history_dict()

Get the message history as dictionaries.

```python
def get_history_dict(self) -> List[Dict[str, Any]]
```

**Returns**: List of message dictionaries.

## Configuration

### Config Classes

All config classes inherit from Pydantic's `BaseModel` and support extra fields.

#### ModelConfig

Configuration for an LLM model.

```python
class ModelConfig(BaseModel):
    provider: str  # "openai", "anthropic", etc.
    name: str      # Model name
    api_key: Optional[str] = None
    base_url: Optional[str] = None
```

#### AuthConfig

Authentication configuration for an MCP server.

```python
class AuthConfig(BaseModel):
    type: str = "bearer"  # "bearer", "basic", "key", "oauth", "none"
    token: Optional[str] = None  # Bearer token
    key: Optional[str] = None  # API key
    username: Optional[str] = None  # Username
    password: Optional[str] = None  # Password
```

#### MCPConfig

Configuration for a single MCP server.

```python
class MCPConfig(BaseModel):
    name: str  # MCP server name
    url: str   # MCP server URL
    auth: Optional[AuthConfig] = None  # Authentication config
    tools: Optional[List[str]] = None  # Specific tools to enable
    timeout: float = 30.0  # Request timeout in seconds
```

#### TeamConfig

Configuration for a team with model and MCPs.

```python
class TeamConfig(BaseModel):
    name: str  # Team name
    model: ModelConfig  # LLM model configuration
    mcps: List[MCPConfig]  # List of MCP servers
```

#### Config

Top-level MCPFlow configuration.

```python
class Config(BaseModel):
    teams: List[TeamConfig]  # List of team configurations
```

**Class Methods**:

#### from_yaml(path)

Load configuration from a YAML file.

```python
@classmethod
def from_yaml(cls, path: str) -> "Config"
```

**Parameters**:

- `path` (str): Path to YAML configuration file

**Returns**: Config instance

**Raises**:
- `FileNotFoundError`: If the file doesn't exist
- `yaml.YAMLError`: If the YAML is invalid

#### from_dict(data)

Load configuration from a dictionary with environment variable substitution.

```python
@classmethod
def from_dict(cls, data: Dict[str, Any]) -> "Config"
```

**Parameters**:

- `data` (Dict[str, Any]): Configuration dictionary

**Returns**: Config instance

**Instance Methods**:

#### to_dict()

Convert configuration to dictionary.

```python
def to_dict(self) -> Dict[str, Any]
```

#### to_yaml()

Convert configuration to YAML string.

```python
def to_yaml(self) -> str
```

#### get_team(name)

Get a team configuration by name.

```python
def get_team(self, name: str) -> Optional[TeamConfig]
```

#### get_mcp(team_name, mcp_name)

Get an MCP configuration from a team.

```python
def get_mcp(self, team_name: str, mcp_name: str) -> Optional[MCPConfig]
```

**Example Configuration**:

```python
from mcpflow.config import Config, ModelConfig, MCPConfig, AuthConfig, TeamConfig

config = Config(teams=[
    TeamConfig(
        name="main-team",
        model=ModelConfig(
            provider="openai",
            name="gpt-4",
            api_key="sk-xxx"
        ),
        mcps=[
            MCPConfig(
                name="calculator",
                url="http://localhost:8000",
                auth=AuthConfig(type="bearer", token="token-xxx")
            )
        ]
    )
])
```

## HTTP Bridge

### MCPHTTPBridge

Provides HTTP/REST communication with remote MCP servers.

**Signature**:

```python
class MCPHTTPBridge:
    def __init__(
        self,
        url: str,
        auth_token: Optional[str] = None,
        timeout: float = 30.0
    ) -> None
```

**Parameters**:

- `url` (str): MCP server URL
- `auth_token` (Optional[str]): Bearer token for authentication
- `timeout` (float): Request timeout in seconds

**Methods**:

#### discover()

Discover tools from the MCP server.

```python
async def discover(self) -> List[ToolDefinition]
```

**Returns**: List of available tools

#### call_tool(tool_name, inputs)

Call a tool on the MCP server.

```python
async def call_tool(
    self,
    tool_name: str,
    inputs: Dict[str, Any]
) -> Dict[str, Any]
```

**Parameters**:

- `tool_name` (str): Tool name
- `inputs` (Dict[str, Any]): Tool inputs

**Returns**: Tool execution result

#### close()

Close the connection.

```python
async def close(self) -> None
```

## Tracing

### Tracer

Distributed tracing support.

**Methods**:

#### start_span(name, attributes=None)

Start a new tracing span.

```python
def start_span(
    self,
    name: str,
    attributes: Optional[Dict[str, Any]] = None
) -> ContextManager
```

**Parameters**:

- `name` (str): Span name
- `attributes` (Optional[Dict]): Span attributes

**Example**:

```python
tracer = get_tracer()
with tracer.start_span("tool_execution", {"tool_name": "add"}):
    # Do work
    pass
```

### Functions

#### setup_tracing(service_name, exporter="otlp")

Setup tracing for the application.

```python
def setup_tracing(service_name: str, exporter: str = "otlp") -> None
```

**Parameters**:

- `service_name` (str): Service name for traces
- `exporter` (str): Exporter type ("otlp", "jaeger", "zipkin")

#### get_tracer()

Get the current tracer instance.

```python
def get_tracer() -> Tracer
```

#### @trace(name, **attributes)

Decorator for tracing function execution.

```python
@trace("my_function", version="1.0")
def my_function(x, y):
    return x + y
```

#### @trace_tool_call(tool_name, **attributes)

Decorator for tracing tool calls.

```python
@trace_tool_call("calculator_add")
async def add_handler(a, b):
    return a + b
```

## Testing

### MockServer

Mock MCP server for testing.

**Signature**:

```python
class MockServer:
    def register_tool(self, tool: ToolDefinition, handler: Callable) -> None
    async def call_tool(self, name: str, params: Dict[str, Any]) -> Any
    def get_call_history(self) -> List[ToolCall]
```

### Functions

#### create_test_server()

Create a test server instance.

```python
def create_test_server() -> MockServer
```

**Example**:

```python
from mcpflow import create_test_server, ToolDefinition

server = create_test_server()

tool_def = ToolDefinition(
    name="test",
    description="Test tool",
    input_schema={"type": "object", "properties": {"x": {"type": "integer"}}}
)

async def handler(x: int) -> int:
    return x * 2

server.register_tool(tool_def, handler)
result = await server.call_tool("test", {"x": 5})
assert result == 10
```

#### @mock_tool(name, **kwargs)

Decorator for creating mock tool handlers.

```python
@mock_tool("test_tool")
def test_handler(data: str) -> str:
    return f"Processed: {data}"
```

### MCPFixture

Async context manager for test fixtures.

```python
async def test_with_fixture():
    async with MCPFixture() as fixture:
        # fixture is an MCPRegistry
        await fixture.register_mcp(config)
```

### MockToolExpectation

Expectation for mock tool calls.

```python
@dataclass
class MockToolExpectation:
    tool_name: str
    inputs: Dict[str, Any]
    result: Any
    call_count: int = 0
```

## CLI

### Commands

#### mcpflow init

Initialize a new MCPFlow project.

```bash
mcpflow init <project_name>
```

Creates a project with:
- `config.yaml` - Configuration file
- `servers/` - MCP server implementations
- `agents/` - Agent implementations
- `tests/` - Test files

#### mcpflow version

Show MCPFlow version.

```bash
mcpflow version
```

#### mcpflow info

Show server information.

```bash
mcpflow info
```

## Types

### ToolDefinition

```python
@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
```

### MCPRequest

```python
@dataclass
class MCPRequest:
    method: str  # "GET", "POST", etc.
    path: str    # "/tools", "/execute", etc.
    params: Optional[Dict[str, Any]] = None
    body: Optional[Dict[str, Any]] = None
```

### MCPResponse

```python
@dataclass
class MCPResponse:
    status: int
    data: Any
    error: Optional[str] = None
```
