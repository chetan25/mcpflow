"""MCP Server implementation."""

from typing import Any, Callable, Dict, List, Optional

from .config import Config
from .types import ToolDefinition


class MCPServer:
    """MCPFlow Server for managing Model Context Protocol connections."""

    def __init__(self, config: Optional[Config] = None):
        """Initialize MCPFlow server.
        
        Args:
            config: Server configuration
        """
        self.config = config or Config()
        self._tools: Dict[str, ToolDefinition] = {}
        self._handlers: Dict[str, Callable] = {}

    def register_tool(self, tool: ToolDefinition, handler: Callable) -> None:
        """Register a tool with the server.
        
        Args:
            tool: Tool definition
            handler: Handler function for tool invocation
        """
        self._tools[tool.name] = tool
        self._handlers[tool.name] = handler

    def get_tools(self) -> List[ToolDefinition]:
        """Get all registered tools.
        
        Returns:
            List of tool definitions
        """
        return list(self._tools.values())

    async def call_tool(self, name: str, params: Dict[str, Any]) -> Any:
        """Call a registered tool.
        
        Args:
            name: Tool name
            params: Tool parameters
            
        Returns:
            Tool result
            
        Raises:
            ValueError: If tool not found
        """
        if name not in self._handlers:
            raise ValueError(f"Tool '{name}' not found")
        handler = self._handlers[name]
        return await handler(**params) if callable(handler) else handler

    async def start(self) -> None:
        """Start the server."""
        raise NotImplementedError("Server start not yet implemented")

    async def stop(self) -> None:
        """Stop the server."""
        raise NotImplementedError("Server stop not yet implemented")
