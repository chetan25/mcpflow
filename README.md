# MCPFlow - Model Context Protocol Flow Orchestration

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](./python/tests)

MCPFlow is a comprehensive Python framework for orchestrating and managing Model Context Protocol (MCP) connections. It provides a unified interface for building intelligent agents that can dynamically discover and invoke tools from multiple MCP servers.

## 🎯 Overview

MCPFlow simplifies the complexity of working with MCP servers by providing:

- **Unified Tool Management**: Register, discover, and invoke tools across multiple MCP servers
- **Chat Orchestration**: Build multi-turn conversational agents with automatic tool routing
- **Async-First Architecture**: Fully async/await support for high-performance applications
- **Built-in Observability**: OpenTelemetry integration for tracing and monitoring
- **Type Safety**: Full type hints and Pydantic validation
- **Testing Support**: Comprehensive testing utilities and mock servers

## ✨ Features

### Core Features

- **Tool Registration & Discovery**: Automatic JSON schema generation and validation
- **Chat Session Management**: Multi-turn conversations with full history
- **HTTP Bridging**: Communicate with remote MCP servers via HTTP REST
- **Registry System**: Tool discovery, caching, and routing across MCPs
- **Configuration Management**: YAML-based configuration with environment variable support
- **Distributed Tracing**: OpenTelemetry OTLP exporter integration

### Developer Experience

- **CLI Tools**: `mcpflow` command for project initialization and management
- **Testing Framework**: `MockServer` and test fixtures for easy unit testing
- **Decorators**: Simple `@MCPServerDecorator` and `@tool` decorators for server definition
- **Type Hints**: Complete type annotations for IDE support and type checking
- **Documentation**: Comprehensive guides, API reference, and examples

## 🚀 Quick Start

### Installation

```bash
pip install mcpflow
```

### Create Your First MCP Server

```python
from mcpflow import MCPServerDecorator, tool

@MCPServerDecorator("my-server", "0.1.0", "My first MCP server")
class MyServer:
    @tool("add", "Add two numbers")
    def add(self, a: float, b: float) -> float:
        return a + b
    
    @tool("multiply", "Multiply two numbers")
    def multiply(self, a: float, b: float) -> float:
        return a * b
```

### Create an Agent

```python
import asyncio
from mcpflow import ChatManager, MCPRegistry
from mcpflow.config import MCPConfig

async def main():
    # Register MCP server
    registry = MCPRegistry()
    config = MCPConfig(name="my-server", url="http://localhost:8000")
    await registry.register_mcp(config)
    
    # Create agent
    chat = ChatManager(
        model="gpt-4",
        registry=registry,
        system_prompt="You are a helpful math assistant."
    )
    
    # Ask a question
    response = await chat.send("What is 15 * 7?")
    print(f"Agent: {response}")

if __name__ == "__main__":
    asyncio.run(main())
```

## 📚 Documentation

MCPFlow provides comprehensive documentation to get you started:

| Document | Description |
|----------|-------------|
| [**QUICKSTART.md**](docs/QUICKSTART.md) | Installation, basic setup, and first steps |
| [**ARCHITECTURE.md**](docs/ARCHITECTURE.md) | System design, component overview, data flows |
| [**API-REFERENCE.md**](docs/API-REFERENCE.md) | Complete API documentation for all classes and functions |
| [**EXAMPLES.md**](docs/EXAMPLES.md) | Practical examples and common patterns |
| [**CONTRIBUTING.md**](CONTRIBUTING.md) | Development setup and contribution guidelines |

## 🏗️ Project Structure

```
mcpflow/
├── python/
│   ├── mcpflow/                # Main package
│   │   ├── server.py           # MCPServer and @MCPServerDecorator
│   │   ├── chat.py             # ChatManager and Message types
│   │   ├── registry.py         # ToolRegistry and MCPRegistry
│   │   ├── config.py           # Configuration management
│   │   ├── http_bridge.py      # HTTP communication
│   │   ├── tracing.py          # OpenTelemetry integration
│   │   ├── cli.py              # Command-line interface
│   │   ├── testing.py          # Testing utilities
│   │   └── types.py            # Type definitions
│   ├── tests/                  # Test suite
│   └── pyproject.toml          # Project configuration
├── docs/                       # Documentation
│   ├── QUICKSTART.md
│   ├── ARCHITECTURE.md
│   ├── API-REFERENCE.md
│   └── EXAMPLES.md
└── CONTRIBUTING.md             # Contributing guidelines
```

## 💡 Core Concepts

### MCPServer & Decorators

Define MCP servers with simple Python decorators:

```python
@MCPServerDecorator("calculator", "1.0.0")
class CalculatorServer:
    @tool("add", "Add two numbers")
    def add(self, a: float, b: float) -> float:
        return a + b
```

### Registry System

Discover and route tools across multiple MCP servers:

```python
# Register MCPs
registry = MCPRegistry()
await registry.register_mcp(calculator_config)
await registry.register_mcp(weather_config)

# Call tools
result = await registry.call_tool("calculator", "add", {"a": 5, "b": 3})
```

### Chat Management

Build conversational agents with automatic tool execution:

```python
chat = ChatManager(model="gpt-4", registry=registry)
response = await chat.send("What's 15 + 7?")
```

### Configuration

YAML-based configuration with environment variable support:

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
```

## 🧪 Testing

MCPFlow includes comprehensive testing utilities:

```python
from mcpflow import MockServer, create_test_server

# Create test server
server = create_test_server()

# Register and test tools
result = await server.call_tool("add", {"a": 5, "b": 3})
assert result == 8
```

## 🔍 Observability

Built-in distributed tracing with OpenTelemetry:

```python
from mcpflow import setup_tracing, trace

setup_tracing(service_name="my-agent")

@trace("my_operation")
async def my_operation():
    # Your code here
    pass
```

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:

- Development setup
- Running tests
- Commit conventions
- Pull request process
- Code style requirements

## 📋 Development

### Setup

```bash
cd python
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=mcpflow

# Specific test file
pytest tests/test_server.py
```

### Code Quality

```bash
# Format with Black
black mcpflow tests

# Sort imports
isort mcpflow tests

# Lint with flake8
flake8 mcpflow tests

# Type check with mypy
mypy mcpflow
```

## 📦 Dependencies

### Core Dependencies

- **pydantic** - Data validation and serialization
- **pyyaml** - YAML configuration parsing
- **httpx** - Async HTTP client
- **click** - CLI framework

### Optional Dependencies

- **opentelemetry-api** - Tracing
- **opentelemetry-exporter-otlp** - OTLP exporter
- **pytest** - Testing (dev only)
- **black** - Code formatting (dev only)

## 📝 Examples

See [docs/EXAMPLES.md](docs/EXAMPLES.md) for detailed examples including:

- Simple echo MCP server
- Weather information service
- Multi-MCP agent orchestration
- Unit and integration testing
- Advanced patterns (async, error handling, composition)

## 🔐 Security

MCPFlow supports:

- Bearer token authentication
- Basic authentication
- Custom authentication headers
- Environment variable substitution
- HTTPS/TLS for remote MCPs
- Input validation via JSON schema

## 🎓 Learning Resources

1. **Start Here**: [Quick Start Guide](docs/QUICKSTART.md)
2. **Understand Architecture**: [Architecture Guide](docs/ARCHITECTURE.md)
3. **API Deep Dive**: [API Reference](docs/API-REFERENCE.md)
4. **Learn by Example**: [Examples](docs/EXAMPLES.md)
5. **Contribute**: [Contributing Guide](CONTRIBUTING.md)

## 📄 License

MCPFlow is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

MCPFlow is built on the Model Context Protocol specification and inspired by the broader AI and open-source communities.

## 🗺️ Roadmap

Future versions of MCPFlow will include:

- GraphQL support for tool definitions
- Built-in rate limiting and caching
- Streaming responses
- Multi-agent collaboration
- Enhanced error recovery
- Performance optimization
