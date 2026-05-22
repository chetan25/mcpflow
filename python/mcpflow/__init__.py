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

from .chat import ChatManager, Message
from .config import Config
from .registry import ToolRegistry
from .server import MCPServer
from .tracing import Tracer
from .types import MCPRequest, MCPResponse, ToolDefinition
from .http_bridge import HTTPBridge
from .testing import MockServer, create_test_server

# Define public API
__all__ = [
    # Core
    "MCPServer",
    "ChatManager",
    "Config",
    # Types
    "MCPRequest",
    "MCPResponse",
    "ToolDefinition",
    "Message",
    # Registry
    "ToolRegistry",
    # HTTP
    "HTTPBridge",
    # Observability
    "Tracer",
    # Testing
    "MockServer",
    "create_test_server",
]


def tool(name: str, description: str, input_schema=None):
    """Decorator for registering a tool.
    
    Usage:
        @tool("my_tool", "Does something useful")
        def my_tool_impl(param1: str) -> str:
            return f"Result: {param1}"
    
    Args:
        name: Tool name
        description: Tool description
        input_schema: JSON schema for input parameters
        
    Returns:
        Decorator function
    """

    def decorator(func):
        # Store metadata on function
        func._tool_name = name
        func._tool_description = description
        func._tool_input_schema = input_schema or {}
        return func

    return decorator
