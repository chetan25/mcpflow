# MCPFlow Architecture

This document provides a detailed overview of MCPFlow's system architecture, core components, and data flows.

## System Overview

MCPFlow is a distributed system for orchestrating Model Context Protocol (MCP) servers with AI agents. The architecture follows a layered design:

```
┌─────────────────────────────────────────────────────┐
│           Application Layer (Agents)                │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│         ChatManager & Orchestration                 │
│  - Session management                               │
│  - Tool execution routing                           │
│  - Message history                                  │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│            MCPRegistry (Discovery)                  │
│  - Server registration                              │
│  - Tool discovery & caching                         │
│  - Tool routing                                     │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│      HTTP Bridge & Protocol Layer                   │
│  - HTTP/REST communication                          │
│  - JSON serialization                               │
│  - Error handling                                   │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│    External MCP Servers & Services                  │
│  - Tool implementations                             │
│  - Async handlers                                   │
└─────────────────────────────────────────────────────┘
```

## Core Components

### 1. MCPServer

**Location**: `mcpflow/server.py`

The `MCPServer` class is the base server implementation for MCP connections.

**Key Responsibilities**:
- Tool registration and management
- Tool discovery and enumeration
- Tool invocation and routing
- Configuration management

**Key Methods**:

```python
class MCPServer:
    def __init__(self, config: Optional[Config] = None)
    def register_tool(self, tool: ToolDefinition, handler: Callable) -> None
    def get_tools(self) -> List[ToolDefinition]
    async def call_tool(self, name: str, params: Dict[str, Any]) -> Any
    async def start(self) -> None
    async def stop(self) -> None
```

**Decorator Support**:

MCPFlow provides decorators for simplified server definition:

- `@MCPServerDecorator(name, version, description)` - Class-level decorator for automatic tool discovery
- `@tool(name, description, input_schema)` - Method-level decorator for tool registration

Example:

```python
@MCPServerDecorator("math-server", "1.0.0", "Mathematical operations")
class MathServer:
    @tool("add", "Add two numbers")
    def add(self, a: float, b: float) -> float:
        return a + b
```

### 2. Registry System

The registry system manages tool discovery and routing across multiple MCP servers.

#### ToolRegistry

**Location**: `mcpflow/registry.py` (lines 10-80)

Local tool registry for direct Python tool registration:

```python
class ToolRegistry:
    def register(self, tool: ToolDefinition, handler: Callable, namespace: str = "default")
    def get(self, name: str) -> Optional[ToolDefinition]
    def get_handler(self, name: str) -> Optional[Callable]
    def list_tools(self, namespace: Optional[str] = None) -> List[ToolDefinition]
    def list_namespaces(self) -> List[str]
```

**Use Cases**:
- Local tool registration
- Namespace-based organization
- Direct handler invocation

#### MCPRegistry

**Location**: `mcpflow/registry.py` (lines 83-222)

Distributed registry for managing MCP server connections:

```python
class MCPRegistry:
    async def register_mcp(self, config: MCPConfig) -> List[ToolDefinition]
    def get_tools(self, mcp_name: Optional[str] = None) -> List[ToolDefinition]
    async def call_tool(self, mcp_name: str, tool_name: str, inputs: Dict) -> Dict
    def get_registered_mcps(self) -> List[str]
    def get_mcp_config(self, mcp_name: str) -> Optional[MCPConfig]
    async def close_all(self) -> None
```

**Features**:
- HTTP bridge creation for each MCP
- Automatic tool discovery
- Tool caching for performance
- Connection lifecycle management
- Async context manager support

### 3. ChatManager

**Location**: `mcpflow/chat.py`

Orchestrates chat sessions and manages message flow with tool integration.

**Key Classes**:

```python
@dataclass
class Message:
    role: str                              # "user", "assistant", "system"
    content: str                           # Message text
    timestamp: datetime                    # When sent
    tool_calls: List[ToolCall] = []       # Associated tool calls

@dataclass
class ToolCall:
    tool_name: str                         # Name of the tool
    mcp_name: str                          # Which MCP server
    inputs: Dict[str, Any]                 # Tool parameters
    result: Optional[Dict[str, Any]]      # Execution result
    error: Optional[str]                   # Error message if failed
```

**ChatManager Methods**:

```python
class ChatManager:
    def __init__(
        self,
        model: Optional[str] = None,
        registry: Optional[MCPRegistry] = None,
        system_prompt: Optional[str] = None,
        max_tool_calls: int = 10
    )
    
    async def send(
        self,
        message: str,
        model_override: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str
    
    def clear_history(self) -> None
    def get_history(self) -> List[Message]
    def get_history_dict(self) -> List[Dict[str, Any]]
```

**Message Flow**:

1. User sends message via `send()`
2. Message added to history
3. Response generated using configured model
4. Assistant response added to history
5. Response returned to caller

### 4. HTTP Bridge

**Location**: `mcpflow/http_bridge.py`

Provides HTTP/REST communication with remote MCP servers.

```python
class MCPHTTPBridge:
    def __init__(
        self,
        url: str,
        auth_token: Optional[str] = None,
        timeout: float = 30.0
    )
    
    async def discover(self) -> List[ToolDefinition]
    async def call_tool(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]
    async def close(self) -> None
```

**Features**:
- Bearer token authentication
- Custom timeout configuration
- Error handling and retry logic
- Connection pooling
- Automatic serialization/deserialization

### 5. Configuration System

**Location**: `mcpflow/config.py`

Hierarchical, environment-variable aware configuration:

```python
# Atomic config classes
class ModelConfig(BaseModel)           # LLM configuration
class AuthConfig(BaseModel)            # Auth configuration
class MCPConfig(BaseModel)             # Single MCP server config

# Composite configs
class TeamConfig(BaseModel)            # Team with model + MCPs
class Config(BaseModel)                # Top-level configuration

# Example structure
Config
├── teams[]
    ├── TeamConfig
        ├── model: ModelConfig
        └── mcps[]: MCPConfig
            └── auth: AuthConfig
```

**Key Features**:
- Environment variable substitution (`${VAR_NAME}`)
- YAML loading with validation
- Pydantic-based type checking
- Hierarchical team configuration

Example:

```yaml
teams:
  - name: main-team
    model:
      provider: openai
      name: gpt-4
      api_key: ${OPENAI_API_KEY}
    mcps:
      - name: calculator
        url: http://localhost:8000
        auth:
          type: bearer
          token: ${CALC_TOKEN}
        timeout: 30.0
```

### 6. Tracing & Observability

**Location**: `mcpflow/tracing.py`

Built-in OpenTelemetry integration for distributed tracing:

```python
class Tracer:
    def start_span(self, name: str, attributes: Optional[Dict] = None)
    def set_attribute(self, key: str, value: Any)
    def add_event(self, name: str, attributes: Optional[Dict] = None)

def setup_tracing(service_name: str, exporter: str = "otlp")
def get_tracer() -> Tracer
def trace(name: str, **attributes)              # Decorator
def trace_tool_call(tool_name: str, **attrs)   # Decorator
```

**Features**:
- OpenTelemetry OTLP exporter
- Automatic span creation
- Attribute tracking
- Tool call instrumentation
- Error span marking

### 7. Testing Utilities

**Location**: `mcpflow/testing.py`

Mock servers and fixtures for testing:

```python
class MockServer:
    def register_tool(self, tool: ToolDefinition, handler: Callable)
    async def call_tool(self, name: str, params: Dict) -> Any
    def get_call_history(self) -> List[ToolCall]
    
def create_test_server() -> MockServer
def mock_tool(name: str, **kwargs) -> Callable  # Decorator

@dataclass
class MockToolExpectation:
    tool_name: str
    inputs: Dict[str, Any]
    result: Any
    call_count: int = 0

class MCPFixture:
    async def __aenter__(self)
    async def __aexit__(self, exc_type, exc_val, exc_tb)
```

## Data Flow

### Tool Discovery Flow

```
┌────────────────────────────────────────────────────────┐
│ MCPRegistry.register_mcp(config: MCPConfig)           │
└────────────────┬──────────────────────────────────────┘
                 │
                 ├─ Create MCPHTTPBridge(config.url, auth_token)
                 │
                 ├─ Call bridge.discover()
                 │
                 ├─ HTTP GET /tools  (or MCP discovery endpoint)
                 │
                 ├─ Parse response → List[ToolDefinition]
                 │
                 └─ Cache in registry._tools_cache[mcp_name]
                 
Returns: List[ToolDefinition]
```

### Tool Execution Flow

```
┌────────────────────────────────────────────────────────┐
│ ChatManager.send(message: str)                         │
└────────────────┬──────────────────────────────────────┘
                 │
                 ├─ Add Message(role="user", content=message) to history
                 │
                 ├─ Call _generate_response(model, context)
                 │
                 └─ Extract tool_calls from response
                 
┌────────────────────────────────────────────────────────┐
│ For each tool_call in response:                        │
└────────────────┬──────────────────────────────────────┘
                 │
                 ├─ MCPRegistry.call_tool(mcp_name, tool_name, inputs)
                 │
                 ├─ Get bridge from registry._bridges[mcp_name]
                 │
                 ├─ Call bridge.call_tool(tool_name, inputs)
                 │
                 ├─ HTTP POST /execute with tool_name and inputs
                 │
                 ├─ Receive result
                 │
                 └─ Store in tool_call.result
                 
┌────────────────────────────────────────────────────────┐
│ Add Message(role="assistant", content=response)        │
└────────────────────────────────────────────────────────┘
```

### Configuration Loading Flow

```
┌────────────────────────────────────────────────────────┐
│ Config.from_yaml(path)                                │
└────────────────┬──────────────────────────────────────┘
                 │
                 ├─ Read YAML file
                 │
                 ├─ Parse to dict
                 │
                 ├─ Call Config.from_dict(dict)
                 │
                 └─ Substitute environment variables
                    (${VAR_NAME} → os.environ.get(VAR_NAME))
                    
Returns: Config instance
```

## Async Patterns

MCPFlow uses async/await throughout for non-blocking I/O:

### Async Context Manager Pattern

```python
async with MCPRegistry() as registry:
    # Register MCPs
    await registry.register_mcp(config)
    # Use MCPs
    await registry.call_tool("mcp_name", "tool_name", {})
    # Auto cleanup on exit
```

### Async Tool Handlers

```python
@tool("async_operation", "Does async work")
async def async_operation(data: str) -> str:
    # MCPFlow automatically awaits async handlers
    result = await some_async_operation(data)
    return result
```

### ChatManager Async Patterns

```python
# All ChatManager methods are async
async with aiohttp.ClientSession() as session:
    response = await chat_manager.send("Hello!")
    history = chat_manager.get_history()
```

## Extension Points

MCPFlow is designed for extensibility:

### Custom Handlers

Implement the `Callable[[Dict[str, Any]], Any]` protocol:

```python
async def my_handler(name: str, age: int) -> str:
    return f"{name} is {age} years old"

tool_def = ToolDefinition(
    name="greet",
    description="Greet someone",
    input_schema={...}
)

registry.register(tool_def, my_handler)
```

### Custom Configuration

Extend the base `BaseModel` from Pydantic:

```python
from pydantic import BaseModel

class CustomMCPConfig(MCPConfig):
    custom_field: str = "default"
```

### Custom Tracing

Integrate with existing OpenTelemetry setups:

```python
from mcpflow import setup_tracing

setup_tracing(
    service_name="my-agent",
    exporter="otlp"  # or "jaeger", "zipkin"
)
```

## Performance Considerations

1. **Tool Discovery Caching**: Tools are cached after discovery to avoid repeated HTTP calls
2. **Connection Pooling**: HTTP bridges use connection pooling for efficiency
3. **Async I/O**: All I/O operations are async to prevent blocking
4. **Message History**: Consider pagination for long chat histories
5. **Timeout Configuration**: Adjust MCPConfig.timeout based on MCP performance

## Security Considerations

1. **Authentication**: Support for bearer token, basic auth, and custom auth
2. **Environment Variables**: Never commit credentials; use environment variable substitution
3. **Input Validation**: Tool inputs are validated against JSON schema
4. **Error Handling**: Errors don't expose sensitive information by default
5. **TLS/HTTPS**: HTTP bridge supports HTTPS for secure communication

## Deployment Patterns

### Standalone Agent

```python
async def run_agent():
    config = Config.from_yaml("config.yaml")
    registry = MCPRegistry()
    # Register MCPs and run
```

### Agent Service

```python
# FastAPI app with MCPFlow integration
from fastapi import FastAPI
app = FastAPI()

# Initialize registry at startup
@app.on_event("startup")
async def startup():
    app.state.registry = MCPRegistry()
    # Register MCPs
```

### Serverless

```python
# AWS Lambda handler
async def handler(event, context):
    config = Config.from_dict(event["config"])
    registry = MCPRegistry()
    # Process request
    await registry.close_all()
```
