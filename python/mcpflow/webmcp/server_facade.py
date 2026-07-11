"""MCP server facade for WebMCP bridge."""

import logging
from typing import Optional
import sys
import json
import uuid

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

        # Import streaming support
        from .streaming import StreamingToolExecutor

        self.streaming = StreamingToolExecutor(self.bridge)

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
            """Call a WebMCP tool with streaming support."""
            logger.info(f"Tool called: {name} with args {arguments}")

            # Generate task ID for streaming
            task_id = str(uuid.uuid4())

            # Get tool info
            manifest = self.bridge.manifests.get(self.origin_slug)
            if not manifest:
                return self.TextContent(
                    text=json.dumps({"error": "Origin not discovered. Run discovery first."}),
                    type="text",
                )

            # Check if tool exists
            found = False
            for tool in manifest.tools:
                mcp_name = f"{self.origin_slug}__{tool.name}".replace(".", "_").replace("-", "_")
                if mcp_name == name:
                    found = True
                    break

            if not found:
                self.bridge.security.log_tool_call(self.origin_slug, name, False, error="Tool not found")
                return self.TextContent(
                    text=json.dumps({"error": f"Tool not found: {name}"}),
                    type="text",
                )

            # Execute with streaming and collect chunks
            chunks = await self.streaming.stream_to_mcp_content_blocks(
                origin=self.origin_slug,
                tool_name=name,
                args=arguments,
                task_id=task_id,
            )

            # Return streamed content
            if chunks:
                # Combine all chunks into one response
                combined_text = "\n".join(c.get("text", "") for c in chunks)
                return self.TextContent(text=combined_text, type="text")
            else:
                return self.TextContent(
                    text=json.dumps({"error": "No response from tool"}),
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
