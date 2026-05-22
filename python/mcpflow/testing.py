"""Testing utilities for MCPFlow."""

from typing import Any, Dict, Optional

from .server import MCPServer
from .config import Config


class MockServer(MCPServer):
    """Mock MCP server for testing."""

    def __init__(self, config: Optional[Config] = None):
        """Initialize mock server.
        
        Args:
            config: Server configuration
        """
        super().__init__(config or Config())
        self.call_history = []

    async def call_tool(self, name: str, params: Dict[str, Any]) -> Any:
        """Call a tool and record the call.
        
        Args:
            name: Tool name
            params: Tool parameters
            
        Returns:
            Tool result
        """
        self.call_history.append({"tool": name, "params": params})
        return await super().call_tool(name, params)

    def get_call_history(self):
        """Get the history of tool calls.
        
        Returns:
            List of call records
        """
        return self.call_history

    def reset_call_history(self) -> None:
        """Reset the call history."""
        self.call_history = []


def create_test_server(debug: bool = True) -> MCPServer:
    """Create a test server instance.
    
    Args:
        debug: Enable debug logging
        
    Returns:
        MCPServer instance
    """
    config = Config(debug=debug, log_level="DEBUG")
    return MCPServer(config)
