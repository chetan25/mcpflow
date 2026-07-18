"""MCP Registry for managing and routing tool calls across multiple MCP servers."""

from typing import Any, Callable, Dict, List, Optional

from .config import MCPConfig
from .http_bridge import MCPHTTPBridge
from .types import ToolDefinition


class ToolRegistry:
    """Registry for managing tool definitions and handlers.
    
    This is the original tool registry for local tool registration.
    """

    def __init__(self):
        """Initialize tool registry."""
        self._tools: Dict[str, ToolDefinition] = {}
        self._handlers: Dict[str, Callable] = {}
        self._namespaces: Dict[str, List[str]] = {}

    def register(
        self, tool: ToolDefinition, handler: Callable, namespace: str = "default"
    ) -> None:
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


class MCPRegistry:
    """Registry for managing MCP server connections and tool discovery/routing."""

    def __init__(self):
        """Initialize the MCP registry."""
        self._bridges: Dict[str, MCPHTTPBridge] = {}
        self._webmcp_bridges: Dict[str, Any] = {}  # origin_slug -> WebMCPBridge
        self._tools_cache: Dict[str, List[ToolDefinition]] = {}
        self._mcp_configs: Dict[str, MCPConfig] = {}

    async def register_mcp(self, config: MCPConfig) -> List[ToolDefinition]:
        """Register an MCP server and discover its tools.

        Args:
            config: MCPConfig with MCP server details

        Returns:
            List of discovered tools

        Raises:
            httpx.HTTPError: If discovery fails
        """
        # Create bridge for this MCP
        auth_token = None
        if config.auth and config.auth.type == "bearer" and config.auth.token:
            auth_token = config.auth.token

        bridge = MCPHTTPBridge(
            url=config.url,
            auth_token=auth_token,
            timeout=config.timeout,
        )

        # Discover tools
        tools = await bridge.discover()

        # Cache the bridge and configuration
        self._bridges[config.name] = bridge
        self._mcp_configs[config.name] = config

        # Filter tools if specified
        if config.tools:
            tools = [t for t in tools if t.name in config.tools]

        # Cache tools
        self._tools_cache[config.name] = tools

        return tools

    async def register_webmcp(
        self, bridge: Any, url: str, origin_slug: Optional[str] = None
    ) -> List[ToolDefinition]:
        """Register a WebMCPBridge and discover its tools.

        Makes WebMCP tools discovered on a live page first-class registry
        entries alongside server MCPs, so `call_tool`/`get_tools` work the
        same way regardless of whether a tool came from a server MCP or a
        WebMCP-enabled page.

        Args:
            bridge: A `mcpflow.webmcp.WebMCPBridge` instance (already
                constructed by the caller, e.g. with its own origins
                allowlist / interceptor / session profile)
            url: Full URL to discover WebMCP tools on
            origin_slug: Short origin identifier; defaults to the domain
                parsed from `url`

        Returns:
            List of discovered tools, translated to ToolDefinition

        Raises:
            ValueError: If discovery fails or the origin isn't allowed by
                the bridge's own origin allowlist
        """
        from urllib.parse import urlparse

        if not origin_slug:
            parsed = urlparse(url)
            origin_slug = parsed.netloc.replace("www.", "").replace(".", "_")

        manifest = await bridge.discover(url, origin_slug=origin_slug)
        if manifest is None:
            raise ValueError(f"WebMCP discovery failed or origin not allowed: {url}")

        mcp_tools = bridge.get_mcp_tools(origin_slug)
        tools = [
            ToolDefinition(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
            )
            for t in mcp_tools
        ]

        self._webmcp_bridges[origin_slug] = bridge
        self._tools_cache[origin_slug] = tools

        return tools

    def get_tools(self, mcp_name: Optional[str] = None) -> List[ToolDefinition]:
        """Get tools from registry.

        Args:
            mcp_name: Optional MCP name to get tools from. If None, returns all tools.

        Returns:
            List of tool definitions
        """
        if mcp_name:
            return self._tools_cache.get(mcp_name, [])

        # Return all tools from all MCPs
        all_tools = []
        for tools in self._tools_cache.values():
            all_tools.extend(tools)
        return all_tools

    async def call_tool(
        self, mcp_name: str, tool_name: str, inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a tool on a specific MCP server.

        Args:
            mcp_name: Name of the MCP server
            tool_name: Name of the tool to call
            inputs: Tool input parameters

        Returns:
            Tool execution result

        Raises:
            ValueError: If MCP or tool not found, or the WebMCP tool call fails
            httpx.HTTPError: If the call fails
        """
        if mcp_name in self._webmcp_bridges:
            webmcp_bridge = self._webmcp_bridges[mcp_name]
            result = await webmcp_bridge.call_tool(mcp_name, tool_name, inputs)
            if not result.success:
                raise ValueError(f"WebMCP tool call failed: {result.error}")
            return {"success": result.success, "result": result.result, "error": result.error}

        if mcp_name not in self._bridges:
            raise ValueError(f"MCP '{mcp_name}' not found in registry")

        bridge = self._bridges[mcp_name]

        # Verify tool exists (optional validation)
        tools = self._tools_cache.get(mcp_name, [])
        tool_names = [t.name for t in tools]
        if tool_name not in tool_names:
            raise ValueError(
                f"Tool '{tool_name}' not found in MCP '{mcp_name}'. "
                f"Available tools: {tool_names}"
            )

        # Call the tool
        result = await bridge.call_tool(tool_name, inputs)
        return result

    def get_registered_mcps(self) -> List[str]:
        """Get list of registered MCP names.

        Returns:
            List of MCP server names, including registered WebMCP origins
        """
        return list(self._bridges.keys()) + list(self._webmcp_bridges.keys())

    def get_mcp_config(self, mcp_name: str) -> Optional[MCPConfig]:
        """Get the configuration for an MCP server.

        Args:
            mcp_name: MCP server name

        Returns:
            MCPConfig or None if not found
        """
        return self._mcp_configs.get(mcp_name)

    async def close_all(self) -> None:
        """Close all MCP server connections.

        This should be called when the registry is no longer needed
        to properly clean up resources.
        """
        for bridge in self._bridges.values():
            await bridge.close()
        for webmcp_bridge in self._webmcp_bridges.values():
            await webmcp_bridge.close()

        self._bridges.clear()
        self._webmcp_bridges.clear()
        self._tools_cache.clear()
        self._mcp_configs.clear()

    async def __aenter__(self) -> "MCPRegistry":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close_all()
