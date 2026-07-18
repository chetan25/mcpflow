"""MCP server facade for WebMCP bridge."""

import asyncio
import logging
from typing import Optional
import sys
import json
import uuid

# Meta-tools exposed alongside discovered WebMCP tools (spec section 3.7)
_META_TOOLS = {"webmcp_list_origins", "webmcp_rescan", "webmcp_screenshot", "webmcp_login"}

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

        # Forward bridge-level tool-set changes as MCP notifications/tools/list_changed
        def _on_tools_changed(origin_slug, manifest):
            if origin_slug != self.origin_slug:
                return
            asyncio.create_task(self._notify_tools_changed())

        self.bridge.on_tools_changed(_on_tools_changed)

        @self.server.list_tools()
        async def list_tools():
            """List all available tools from WebMCP origin, plus bridge meta-tools."""
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

            tools.append(
                self.Tool(
                    name="webmcp_list_origins",
                    description="List origins currently registered with this bridge",
                    inputSchema={"type": "object", "properties": {}},
                )
            )
            tools.append(
                self.Tool(
                    name="webmcp_rescan",
                    description=(
                        "Force a re-scan of this origin's WebMCP tools, "
                        "bypassing the manifest cache"
                    ),
                    inputSchema={"type": "object", "properties": {}},
                )
            )
            tools.append(
                self.Tool(
                    name="webmcp_screenshot",
                    description="Take a debug screenshot of the current page state",
                    inputSchema={
                        "type": "object",
                        "properties": {"filename": {"type": "string"}},
                        "required": ["filename"],
                    },
                )
            )
            tools.append(
                self.Tool(
                    name="webmcp_login",
                    description=(
                        "Open a headed browser window for the user to log in to this "
                        "origin, then save the session as a reusable profile"
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {"profile_name": {"type": "string"}},
                    },
                )
            )
            return tools

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict):
            """Call a WebMCP tool with streaming support, or a bridge meta-tool."""
            logger.info(f"Tool called: {name} with args {arguments}")

            if name in _META_TOOLS:
                return await self._call_meta_tool(name, arguments)

            tool = self.bridge._resolve_tool(self.origin_slug, name)
            if (
                tool
                and self.bridge.policy_enforcer
                and self.bridge.policy_enforcer.requires_confirmation(tool.name)
            ):
                confirmed = await self._confirm_destructive_call(tool.name, arguments)
                if not confirmed:
                    return self.TextContent(
                        text=json.dumps(
                            {"error": f"Tool call to '{tool.name}' was not confirmed by the user"}
                        ),
                        type="text",
                    )

            # Generate task ID for streaming
            task_id = str(uuid.uuid4())

            # Execute with streaming and collect chunks. stream_to_mcp_content_blocks
            # (via execute_streaming) already handles "origin not discovered" and
            # "tool not found" by yielding an error chunk, so there's no need to
            # duplicate that lookup here.
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

    async def _confirm_destructive_call(self, tool_name: str, arguments: dict) -> bool:
        """
        Request human confirmation via MCP elicitation before running a
        destructive-flagged tool (spec section 3.6.4).

        Fails closed: if the connected client doesn't support elicitation,
        declines, or cancels, the call is blocked rather than allowed to
        proceed silently.
        """
        try:
            session = self.server.request_context.session
            result = await session.elicit_form(
                message=(
                    f"Confirm: allow calling destructive tool '{tool_name}' "
                    f"with arguments {json.dumps(arguments)}?"
                ),
                requestedSchema={
                    "type": "object",
                    "properties": {
                        "confirm": {
                            "type": "boolean",
                            "description": "Allow this tool call?",
                        }
                    },
                    "required": ["confirm"],
                },
            )
            return result.action == "accept" and bool(
                result.content and result.content.get("confirm")
            )
        except Exception as e:
            logger.warning(
                f"Elicitation unavailable or failed for '{tool_name}'; failing closed: {e}"
            )
            return False

    async def _notify_tools_changed(self):
        """Best-effort notifications/tools/list_changed push to the connected client."""
        try:
            session = self.server.request_context.session
            await session.send_tool_list_changed()
        except Exception as e:
            logger.debug(f"Could not send tools/list_changed notification: {e}")

    async def _call_meta_tool(self, name: str, arguments: dict):
        """Handle bridge meta-tools (webmcp_list_origins/rescan/screenshot/login)."""
        if name == "webmcp_list_origins":
            origins = list(self.bridge.manifests.keys())
            return self.TextContent(text=json.dumps({"origins": origins}), type="text")

        if name == "webmcp_rescan":
            try:
                manifest = await self.bridge.rescan(self.origin_slug)
            except ValueError as e:
                return self.TextContent(text=json.dumps({"error": str(e)}), type="text")
            tool_names = [t.name for t in manifest.tools] if manifest else []
            return self.TextContent(
                text=json.dumps({"origin": self.origin_slug, "tools": tool_names}),
                type="text",
            )

        if name == "webmcp_screenshot":
            filename = arguments.get("filename", "webmcp_debug.png")
            page = await self.bridge.browser.get_page_for_origin(self.origin_slug)
            await self.bridge.browser.screenshot(filename, page=page)
            return self.TextContent(text=json.dumps({"screenshot": filename}), type="text")

        if name == "webmcp_login":
            profile_name = arguments.get("profile_name", self.origin_slug)
            url = self.bridge._origin_urls.get(self.origin_slug)
            if not url:
                return self.TextContent(
                    text=json.dumps({"error": f"No known URL for origin '{self.origin_slug}'"}),
                    type="text",
                )
            ok = await self.bridge.session_manager.create_profile(
                profile_name, self.bridge.browser, url, headed=True
            )
            return self.TextContent(
                text=json.dumps({"success": ok, "profile": profile_name}), type="text"
            )

        return self.TextContent(
            text=json.dumps({"error": f"Unknown meta-tool: {name}"}), type="text"
        )

    async def run(self):
        """Run the server with stdio transport."""
        if not self.server:
            await self.initialize()

        from mcp.server.stdio import stdio_server

        try:
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    self.server.create_initialization_options(),
                )
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise
