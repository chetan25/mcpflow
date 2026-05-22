"""HTTP MCP Client Bridge for connecting to remote MCP servers."""

from typing import Any, Dict, List, Optional

import httpx

from .types import ToolDefinition


class MCPHTTPBridge:
    """HTTP client for connecting to and calling tools on remote MCP servers."""

    def __init__(self, url: str, auth_token: Optional[str] = None, timeout: float = 30.0):
        """Initialize MCPHTTPBridge.

        Args:
            url: Base URL of the MCP server
            auth_token: Optional authentication token (Bearer token)
            timeout: Request timeout in seconds
        """
        self.url = url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers including authentication.

        Returns:
            Dictionary of headers
        """
        headers: Dict[str, str] = {"Content-Type": "application/json"}

        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        return headers

    async def discover(self) -> List[ToolDefinition]:
        """Discover available tools from the MCP server.

        Returns:
            List of tool definitions

        Raises:
            httpx.HTTPError: If the request fails
        """
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)

        url = f"{self.url}/tools"
        headers = self._get_headers()

        response = await self._client.get(url, headers=headers)
        response.raise_for_status()

        data = response.json()
        tools = data.get("tools", [])

        return [ToolDefinition(**tool) for tool in tools]

    async def call_tool(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the remote MCP server.

        Args:
            tool_name: Name of the tool to call
            inputs: Tool input parameters

        Returns:
            Tool execution result

        Raises:
            httpx.HTTPError: If the request fails
        """
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)

        url = f"{self.url}/tools/{tool_name}/call"
        headers = self._get_headers()
        payload = {"inputs": inputs}

        response = await self._client.post(url, json=payload, headers=headers)
        response.raise_for_status()

        return response.json()

    async def close(self) -> None:
        """Close the HTTP client connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "MCPHTTPBridge":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
