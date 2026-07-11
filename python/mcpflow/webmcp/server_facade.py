"""MCP server facade for WebMCP bridge."""

import logging
from typing import Optional
import sys
import json

logger = logging.getLogger(__name__)


class WebMCPServer:
    """MCP server that exposes WebMCP tools."""

    def __init__(self, bridge, origin_slug: str):
        """
        Initialize MCP server.

        Args:
            bridge: WebMCPBridge instance
            origin_slug: Origin identifier
        """
        self.bridge = bridge
        self.origin_slug = origin_slug
        self.server = None

    async def initialize(self):
        """Initialize the MCP server with stdio transport."""
        try:
            # Import MCP SDK
            from mcp.server import Server
            from mcp.types import Tool, TextContent
            import mcp.types as types

            self.Server = Server
            self.Tool = Tool
            self.TextContent = TextContent
            self.types = types
        except ImportError:
            logger.error("MCP SDK not installed. Run: pip install mcp")
            raise

        # Create server
        self.server = self.Server("webmcp-bridge")

        @self.server.list_tools()
        async def list_tools():
            """List all available tools from WebMCP origin."""
            mcp_tools = self.bridge.get_mcp_tools(self.origin_slug)
            tools = []
            for tool_def in mcp_tools:
                tools.append(
                    self.Tool(
                        name=tool_def["name"],
                        description=tool_def.get("description", ""),
                        inputSchema=tool_def.get("inputSchema", {}),
                    )
                )
            return tools

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict):
            """Call a WebMCP tool."""
            logger.info(f"Tool called: {name} with args {arguments}")

            # For Phase 1, tools are read-only discovery (returning manifests)
            # Actual tool execution comes in Phase 2
            manifest = self.bridge.manifests.get(self.origin_slug)
            if not manifest:
                return self.TextContent(
                    text=json.dumps({"error": "Origin not discovered. Run discovery first."}),
                    type="text",
                )

            # Return tool info
            for tool in manifest.tools:
                mcp_name = f"{self.origin_slug}__{tool.name}".replace(".", "_").replace("-", "_")
                if mcp_name == name:
                    result = {
                        "name": tool.name,
                        "description": tool.description,
                        "schema": tool.input_schema,
                    }
                    self.bridge.security.log_tool_call(self.origin_slug, tool.name, True)
                    return self.TextContent(text=json.dumps(result), type="text")

            # Log failed call
            self.bridge.security.log_tool_call(self.origin_slug, name, False, error="Tool not found")
            return self.TextContent(
                text=json.dumps({"error": f"Tool not found: {name}"}),
                type="text",
            )

    async def run(self):
        """Run the server with stdio transport."""
        if not self.server:
            await self.initialize()

        try:
            async with self.server.stdio_session() as session:
                await session.wait()
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise
