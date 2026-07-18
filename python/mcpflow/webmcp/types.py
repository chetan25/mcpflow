"""WebMCP bridge data types and schemas."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class WebMCPTool(BaseModel):
    """Represents a WebMCP tool discovered on a page."""

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    input_schema: dict = Field(default_factory=dict, description="JSON Schema for tool input")
    origin: str = Field(..., description="Origin URL where tool was discovered")
    invocation: dict = Field(
        default_factory=lambda: {"type": "imperative"},
        description=(
            "How to invoke this tool: {'type': 'imperative'} for real WebMCP "
            "tools with a captured execute callback, {'type': 'form', "
            "'selector': ...} for declarative form-based tools, "
            "{'type': 'json_ld_entrypoint', 'url_template':..., 'http_method':...} "
            "for schema.org Actions with an EntryPoint target, or "
            "{'type': 'unsupported', 'reason': ...} for tools with no callable endpoint"
        ),
    )


class WebMCPManifest(BaseModel):
    """Manifest of all tools discovered on an origin."""

    origin: str = Field(..., description="Origin URL")
    tools: list[WebMCPTool] = Field(default_factory=list, description="Discovered tools")
    discovered_at: datetime = Field(default_factory=datetime.utcnow, description="Discovery timestamp")
    content_hash: Optional[str] = Field(default=None, description="Hash of page content for change detection")


class ToolCallRequest(BaseModel):
    """Request to invoke a WebMCP tool."""

    origin: str = Field(..., description="Origin of the tool")
    tool_name: str = Field(..., description="Name of the tool to invoke")
    args: dict = Field(default_factory=dict, description="Tool arguments")


class ToolCallResult(BaseModel):
    """Result of a tool invocation."""

    success: bool = Field(..., description="Whether the call succeeded")
    result: Optional[Any] = Field(None, description="Tool result if successful")
    error: Optional[str] = Field(None, description="Error message if failed")
    diff: Optional[dict] = Field(
        None, description="Before/after state diff, if result diffing was enabled"
    )


class SessionProfile(BaseModel):
    """Browser session profile for persistent authentication."""

    name: str = Field(..., description="Profile name (e.g., 'default', 'user@example.com')")
    persist: bool = Field(default=False, description="Whether to persist to disk")
    cookies: Optional[dict] = Field(None, description="Session cookies")
    local_storage: Optional[dict] = Field(None, description="LocalStorage state")


class SecurityPolicy(BaseModel):
    """Security policy for a WebMCP origin."""

    origin: str = Field(..., description="Origin URL")
    allowed_tools: list[str] = Field(default_factory=lambda: ["*"], description="Allowed tool patterns")
    destructive_tools: list[str] = Field(default_factory=list, description="Tools flagged as destructive")
    require_confirmation: bool = Field(default=True, description="Require confirmation for destructive tools")
    max_invocations_per_session: Optional[int] = Field(None, description="Max tool calls per session")
