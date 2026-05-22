"""HTTP bridge for MCPFlow server."""

from typing import Any, Dict, Optional


class HTTPBridge:
    """HTTP bridge for exposing MCPFlow server over HTTP."""

    def __init__(self, server: Any, host: str = "localhost", port: int = 8000):
        """Initialize HTTP bridge.
        
        Args:
            server: MCPFlow server instance
            host: Server host
            port: Server port
        """
        self.server = server
        self.host = host
        self.port = port
        self._is_running = False

    async def start(self) -> None:
        """Start the HTTP server."""
        self._is_running = True
        raise NotImplementedError("HTTP server implementation pending")

    async def stop(self) -> None:
        """Stop the HTTP server."""
        self._is_running = False

    async def handle_request(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle an HTTP request.
        
        Args:
            method: HTTP method
            path: Request path
            body: Request body
            
        Returns:
            Response dictionary
        """
        raise NotImplementedError("Request handling not yet implemented")
