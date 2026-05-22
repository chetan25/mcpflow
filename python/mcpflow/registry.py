"""Tool registration and discovery registry."""

from typing import Any, Callable, Dict, List, Optional

from .types import ToolDefinition


class ToolRegistry:
    """Registry for managing tool definitions and handlers."""

    def __init__(self):
        """Initialize tool registry."""
        self._tools: Dict[str, ToolDefinition] = {}
        self._handlers: Dict[str, Callable] = {}
        self._namespaces: Dict[str, List[str]] = {}

    def register(self, tool: ToolDefinition, handler: Callable, namespace: str = "default") -> None:
        """Register a tool.
        
        Args:
            tool: Tool definition
            handler: Handler function
            namespace: Tool namespace
        """
        self._tools[tool.name] = tool
        self._handlers[tool.name] = handler
        if namespace not in self._namespaces:
            self._namespaces[namespace] = []
        self._namespaces[namespace].append(tool.name)

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool definition.
        
        Args:
            name: Tool name
            
        Returns:
            Tool definition or None
        """
        return self._tools.get(name)

    def get_handler(self, name: str) -> Optional[Callable]:
        """Get a tool handler.
        
        Args:
            name: Tool name
            
        Returns:
            Handler function or None
        """
        return self._handlers.get(name)

    def list_tools(self, namespace: Optional[str] = None) -> List[ToolDefinition]:
        """List all tools, optionally filtered by namespace.
        
        Args:
            namespace: Optional namespace filter
            
        Returns:
            List of tool definitions
        """
        if namespace:
            names = self._namespaces.get(namespace, [])
            return [self._tools[name] for name in names if name in self._tools]
        return list(self._tools.values())

    def list_namespaces(self) -> List[str]:
        """List all namespaces.
        
        Returns:
            List of namespace names
        """
        return list(self._namespaces.keys())
