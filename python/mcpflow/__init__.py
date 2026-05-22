"""MCPFlow - Model Context Protocol flow orchestration framework.

MCPFlow provides a unified framework for orchestrating and managing
Model Context Protocol (MCP) connections with support for:
- Tool registration and discovery
- Chat session management
- HTTP bridging
- Distributed tracing and observability
- Configuration management
"""

__version__ = "0.1.0"
__author__ = "MCPFlow Contributors"
__license__ = "MIT"

from .chat import ChatManager, Message, ToolCall
from .config import Config
from .registry import ToolRegistry, MCPRegistry
from .server import MCPServer, tool, MCPServerDecorator
from .tracing import Tracer, setup_tracing, get_tracer, trace, trace_tool_call
from .types import MCPRequest, MCPResponse, ToolDefinition
from .http_bridge import MCPHTTPBridge
from .testing import (
    MockServer,
    create_test_server,
    MCPFixture,
    MockToolExpectation,
    mock_tool,
)

# Define public API
__all__ = [
    # Core
    "MCPServer",
    "MCPServerDecorator",
    "ChatManager",
    "Config",
    # Types
    "MCPRequest",
    "MCPResponse",
    "ToolDefinition",
    "Message",
    "ToolCall",
    # Registry
    "ToolRegistry",
    "MCPRegistry",
    # HTTP
    "MCPHTTPBridge",
    # Observability
    "Tracer",
    "setup_tracing",
    "get_tracer",
    "trace",
    "trace_tool_call",
    # Testing
    "MockServer",
    "create_test_server",
    "MCPFixture",
    "MockToolExpectation",
    "mock_tool",
    # Decorators
    "tool",
]