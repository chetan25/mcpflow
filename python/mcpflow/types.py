"""Type definitions and models for MCPFlow."""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class MCPRequest(BaseModel):
    """Model Context Protocol request."""

    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None


class MCPResponse(BaseModel):
    """Model Context Protocol response."""

    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None


class ToolDefinition(BaseModel):
    """Definition of a tool that can be called via MCP."""

    name: str
    description: str
    input_schema: Dict[str, Any] = Field(default_factory=dict)


class ServerConfig(BaseModel):
    """Configuration for MCPFlow server."""

    name: str = "mcpflow-server"
    version: str = "0.1.0"
    debug: bool = False
