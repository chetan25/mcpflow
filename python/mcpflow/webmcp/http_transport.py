"""HTTP transport with Streamable HTTP and SSE support."""

import asyncio
import json
import logging
from typing import Optional, Callable, Any
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class StreamableHTTPTransport:
    """
    Streamable HTTP transport supporting Server-Sent Events (SSE).
    
    Implements MCP transport over HTTP with streaming support via SSE,
    enabling multi-client deployments and long-running operations.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        use_sse: bool = True,
        enable_cors: bool = False,
    ):
        """
        Initialize HTTP transport.

        Args:
            host: HTTP server host
            port: HTTP server port
            use_sse: Use Server-Sent Events for streaming (vs. long-polling)
            enable_cors: Enable CORS headers
        """
        self.host = host
        self.port = port
        self.use_sse = use_sse
        self.enable_cors = enable_cors
        self.server = None
        self.request_handlers = {}
        self.sse_connections = {}  # track active SSE connections
        self.app = None

    def register_handler(self, method: str, handler: Callable):
        """
        Register a request handler.

        Args:
            method: HTTP method / endpoint (e.g., "POST /mcp/call_tool")
            handler: Async callable (request_data) -> response_data
        """
        self.request_handlers[method] = handler

    def build_app(self):
        """
        Build (or return the already-built) FastAPI ASGI app with all
        routes registered, without starting a real server.

        Split out from start() so the app can be exercised directly by an
        ASGI-level test client (e.g. httpx.ASGITransport) without binding a
        real port or blocking on uvicorn.serve().

        Returns:
            The FastAPI app instance
        """
        if self.app is not None:
            return self.app

        try:
            from fastapi import FastAPI, Request, Response
            from fastapi.responses import StreamingResponse
            from fastapi.middleware.cors import CORSMiddleware
        except ImportError:
            logger.error("FastAPI not installed. Run: pip install fastapi uvicorn")
            raise

        self.app = FastAPI(title="WebMCP Bridge HTTP")

        # Add CORS if enabled
        if self.enable_cors:
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

        @self.app.post("/mcp/initialize")
        async def initialize(request: Request):
            """Initialize MCP session."""
            data = await request.json()
            handler = self.request_handlers.get("POST /mcp/initialize")
            if handler:
                result = await handler(data)
                return result
            return {"initialized": True}

        @self.app.post("/discover")
        async def discover(request: Request):
            """Discover WebMCP tools on an origin."""
            data = await request.json()
            handler = self.request_handlers.get("POST /discover")
            if not handler:
                return {"error": "No handler registered"}
            return await handler(data)

        @self.app.post("/mcp/call_tool")
        async def call_tool(request: Request):
            """Call a tool (with streaming via SSE if supported)."""
            data = await request.json()
            tool_name = data.get("tool")
            args = data.get("arguments", {})
            stream_id = str(uuid.uuid4())

            handler = self.request_handlers.get("POST /mcp/call_tool")
            if not handler:
                return {"error": "No handler registered"}

            # Check if client supports streaming (SSE)
            if self.use_sse and request.headers.get("Accept") == "text/event-stream":
                return StreamingResponse(
                    self._stream_sse(stream_id, handler, data),
                    media_type="text/event-stream",
                )
            else:
                # Standard request/response
                result = await handler(data)
                return result

        @self.app.get("/mcp/stream/{stream_id}")
        async def get_stream(stream_id: str, request: Request):
            """SSE endpoint for streaming responses."""
            if stream_id not in self.request_handlers:
                return {"error": "Stream not found"}

            async def event_generator():
                try:
                    async for event in self._sse_generator(stream_id):
                        yield event
                except asyncio.CancelledError:
                    logger.info(f"Stream {stream_id} cancelled")
                finally:
                    if stream_id in self.sse_connections:
                        del self.sse_connections[stream_id]

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
            )

        @self.app.get("/mcp/health")
        async def health():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "sse_enabled": self.use_sse,
                "active_streams": len(self.sse_connections),
            }

        return self.app

    async def start(self):
        """Build the app (if not already built) and serve it with uvicorn."""
        app = self.build_app()

        import uvicorn

        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="info")
        server = uvicorn.Server(config)
        logger.info(f"Starting HTTP transport on http://{self.host}:{self.port}")

        # Run in background
        self.server = server
        await server.serve()

    async def _stream_sse(self, stream_id: str, handler: Callable, request_data: dict):
        """Stream response via SSE."""
        try:
            yield f"data: {json.dumps({'stream_id': stream_id})}\n\n"

            # Call handler and stream chunks
            result = await handler(request_data)

            if isinstance(result, dict) and "chunks" in result:
                for chunk in result["chunks"]:
                    yield f"data: {json.dumps(chunk)}\n\n"
                    await asyncio.sleep(0.01)  # Small delay between chunks
            else:
                yield f"data: {json.dumps(result)}\n\n"

            yield 'data: {"type": "complete"}\n\n'

        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            yield f'data: {{"error": "{str(e)}"}}\n\n'

    async def _sse_generator(self, stream_id: str):
        """Generator for SSE events."""
        while stream_id in self.sse_connections:
            connection = self.sse_connections[stream_id]
            if connection.get("events"):
                event = connection["events"].pop(0)
                yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(0.01)

    async def stop(self):
        """Stop the HTTP transport server."""
        if self.server:
            await self.server.shutdown()
            logger.info("HTTP transport stopped")


class HTTPBridgeServer:
    """
    HTTP server wrapper for WebMCP bridge with streaming support.

    Exposes discovery and tool calls over HTTP with optional SSE streaming.
    """

    def __init__(
        self,
        bridge,
        host: str = "127.0.0.1",
        port: int = 8000,
        use_sse: bool = True,
    ):
        """
        Initialize HTTP bridge server.

        Args:
            bridge: WebMCPBridge instance
            host: Server host
            port: Server port
            use_sse: Enable SSE streaming
        """
        self.bridge = bridge
        self.transport = StreamableHTTPTransport(
            host=host,
            port=port,
            use_sse=use_sse,
        )
        self.setup_routes()

    def setup_routes(self):
        """Register request handlers."""

        async def handle_discover(data):
            """Handle discovery request."""
            origin = data.get("origin")
            origin_slug = data.get("origin_slug")
            if not origin:
                return {"error": "origin required"}

            try:
                manifest = await self.bridge.discover(origin, origin_slug=origin_slug)
                return {
                    "origin": origin,
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "input_schema": tool.input_schema,
                        }
                        for tool in manifest.tools
                    ],
                    "discovered_at": datetime.utcnow().isoformat(),
                }
            except Exception as e:
                return {"error": str(e)}

        async def handle_call_tool(data):
            """Handle tool call."""
            origin = data.get("origin")
            tool_name = data.get("tool")
            args = data.get("arguments", {})

            if not origin or not tool_name:
                return {"error": "origin and tool required"}

            try:
                # Get streaming executor
                executor = self.bridge.get_streaming_executor()

                # Collect streamed chunks
                chunks = []
                async for chunk in executor.execute_streaming(
                    origin=origin,
                    tool_name=tool_name,
                    args=args,
                    task_id=str(uuid.uuid4()),
                ):
                    chunks.append({
                        "content": chunk.content,
                        "type": chunk.chunk_type,
                        "final": chunk.is_final,
                    })

                return {
                    "origin": origin,
                    "tool": tool_name,
                    "chunks": chunks,
                    "completed_at": datetime.utcnow().isoformat(),
                }
            except Exception as e:
                return {"error": str(e), "origin": origin, "tool": tool_name}

        self.transport.register_handler("POST /discover", handle_discover)
        self.transport.register_handler("POST /mcp/call_tool", handle_call_tool)

    async def start(self):
        """Start the HTTP server."""
        await self.transport.start()

    async def stop(self):
        """Stop the HTTP server."""
        await self.transport.stop()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
