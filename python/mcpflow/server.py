"""MCP Server implementation."""

import inspect
from typing import Any, Callable, Dict, List, Optional, get_type_hints

from .config import Config
from .types import ToolDefinition


def _get_json_schema_type(python_type: Any) -> str:
    """Map Python type to JSON schema type.
    
    Args:
        python_type: Python type annotation
        
    Returns:
        JSON schema type string
    """
    # Handle None/NoneType
    if python_type is None or python_type is type(None):
        return "null"
    
    # Get the origin for generic types
    origin = getattr(python_type, "__origin__", None)
    
    # Handle basic types
    if python_type is int or origin is int:
        return "integer"
    elif python_type is float or origin is float:
        return "number"
    elif python_type is str or origin is str:
        return "string"
    elif python_type is bool or origin is bool:
        return "boolean"
    elif python_type is list or origin is list:
        return "array"
    elif python_type is dict or origin is dict:
        return "object"
    else:
        # Default to string for unknown types
        return "string"


def _generate_json_schema(func: Callable, description: Optional[str] = None) -> Dict[str, Any]:
    """Generate JSON schema from function signature and type hints.
    
    Args:
        func: Function to generate schema from
        description: Optional function description
        
    Returns:
        JSON schema dictionary
    """
    schema: Dict[str, Any] = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    
    # Add description if provided
    if description:
        schema["description"] = description
    
    # Get function signature and type hints
    try:
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)
    except (ValueError, TypeError):
        # If we can't get type hints, return basic schema
        return schema
    
    # Process parameters
    for param_name, param in sig.parameters.items():
        # Skip 'self' parameter for methods
        if param_name == "self":
            continue
        
        # Get type from type hints
        param_type = type_hints.get(param_name, str)
        
        # Add to properties
        schema["properties"][param_name] = {
            "type": _get_json_schema_type(param_type)
        }
        
        # Check if parameter is required (no default value)
        if param.default is inspect.Parameter.empty:
            schema["required"].append(param_name)
    
    return schema


def tool(name: Optional[str] = None, description: Optional[str] = None, input_schema: Optional[Dict[str, Any]] = None):
    """Decorator for registering a tool with automatic JSON schema generation.
    
    Usage:
        @tool("my_tool", "Does something useful")
        def my_tool_impl(param1: str, param2: int = 5) -> str:
            return f"Result: {param1} x {param2}"
    
    Args:
        name: Tool name (defaults to function name if not provided)
        description: Tool description
        input_schema: Optional custom JSON schema for input parameters
        
    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        # Use function name as tool name if not provided
        tool_name = name if name is not None else func.__name__
        tool_description = description if description is not None else func.__doc__ or ""
        
        # Generate schema if not provided
        if input_schema is None:
            generated_schema = _generate_json_schema(func, tool_description)
        else:
            generated_schema = input_schema
        
        # Store metadata on function
        func._mcp_tool = {
            "name": tool_name,
            "description": tool_description,
            "input_schema": generated_schema,
        }
        
        # Also store old attributes for backward compatibility
        func._tool_name = tool_name
        func._tool_description = tool_description
        func._tool_input_schema = generated_schema
        
        return func

    return decorator


class MCPServerDef:
    """Definition/metadata for an MCP server."""
    
    def __init__(self, name: str, version: str, description: str, tools: Dict[str, Dict[str, Any]]):
        """Initialize server definition.
        
        Args:
            name: Server name
            version: Server version
            description: Server description
            tools: Dictionary of tool definitions
        """
        self.name = name
        self.version = version
        self.description = description
        self.tools = tools


def MCPServerDecorator(name: Optional[str] = None, version: Optional[str] = None, description: Optional[str] = None):
    """Class decorator for MCP servers with automatic tool discovery.
    
    Usage:
        @MCPServerDecorator("my-server", "1.0.0", "My MCP Server")
        class MyServer:
            @tool("add", "Add two numbers")
            def add(self, a: int, b: int) -> int:
                return a + b
                
            @tool("greet", "Greet a person")
            def greet(self, name: str) -> str:
                return f"Hello, {name}!"
    
    Args:
        name: Server name
        version: Server version (defaults to "0.1.0")
        description: Server description
        
    Returns:
        Class decorator function
    """
    def class_decorator(cls):
        # Set default values
        server_name = name if name is not None else cls.__name__
        server_version = version if version is not None else "0.1.0"
        server_description = description if description is not None else cls.__doc__ or ""
        
        # Collect all @tool decorated methods
        tools_dict: Dict[str, Dict[str, Any]] = {}
        tool_methods: Dict[str, Callable] = {}
        
        for attr_name in dir(cls):
            # Skip private attributes
            if attr_name.startswith("_"):
                continue
            
            try:
                attr = getattr(cls, attr_name)
            except AttributeError:
                continue
            
            # Check if it's a tool-decorated method
            if callable(attr) and hasattr(attr, "_mcp_tool"):
                tool_meta = attr._mcp_tool
                tool_key = tool_meta["name"]
                
                tools_dict[tool_key] = {
                    "name": tool_meta["name"],
                    "description": tool_meta["description"],
                    "input_schema": tool_meta["input_schema"],
                }
                
                tool_methods[tool_key] = attr
        
        # Store metadata on class
        cls.name = server_name
        cls.version = server_version
        cls.description = server_description
        cls._tools = tools_dict
        cls._tool_methods = tool_methods
        cls._server_def = MCPServerDef(
            name=server_name,
            version=server_version,
            description=server_description,
            tools=tools_dict,
        )
        
        return cls
    
    return class_decorator


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
