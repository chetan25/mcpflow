"""Translate WebMCP tool schemas to MCP tool schemas."""

import logging
from typing import Any

from .types import WebMCPTool

logger = logging.getLogger(__name__)


class SchemaTranslator:
    """Translates WebMCP schemas to MCP-compatible schemas."""

    def __init__(self):
        """Initialize the translator."""
        self.tool_name_registry = {}  # Track namespaced tool names

    def translate_tool(self, tool: WebMCPTool, origin_slug: str) -> dict:
        """
        Convert a WebMCP tool to MCP tool format.

        Args:
            tool: WebMCPTool to translate
            origin_slug: Origin identifier for namespacing

        Returns:
            MCP-compatible tool definition dict
        """
        # Namespace tool name to avoid collisions
        namespaced_name = self._namespace_tool_name(tool.name, origin_slug)

        # Sanitize description
        sanitized_description = self._sanitize_description(tool.description)

        # Normalize input schema
        normalized_schema = self._normalize_input_schema(tool.input_schema)

        mcp_tool = {
            "name": namespaced_name,
            "description": sanitized_description,
            "inputSchema": normalized_schema,
        }

        logger.debug(f"Translated tool: {tool.name} -> {namespaced_name}")
        return mcp_tool

    def _namespace_tool_name(self, tool_name: str, origin_slug: str) -> str:
        """
        Create a namespaced tool name to avoid collisions.

        Args:
            tool_name: Original tool name
            origin_slug: Origin identifier

        Returns:
            Namespaced name in format {origin}__{toolName}
        """
        namespaced = f"{origin_slug}__{tool_name}".replace(".", "_").replace("-", "_")

        # Check for collisions
        if namespaced in self.tool_name_registry:
            collision_count = 2
            while f"{namespaced}__{collision_count}" in self.tool_name_registry:
                collision_count += 1
            namespaced = f"{namespaced}__{collision_count}"

        self.tool_name_registry[namespaced] = True
        return namespaced

    def _sanitize_description(self, description: str) -> str:
        """
        Sanitize tool description to remove injection risks.

        Args:
            description: Original description

        Returns:
            Sanitized description
        """
        if not description:
            return ""

        # Remove imperative language patterns
        dangerous_patterns = [
            r"\balways\b",
            r"\bignore\b",
            r"\boverride\b",
            r"\bforget\b",
            r"\bprevious\b",
            r"\b(https?|ftp)://\S+",  # Remove URLs
        ]

        import re

        sanitized = description
        for pattern in dangerous_patterns:
            sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)

        # Remove markdown links
        sanitized = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", sanitized)

        # Remove invisible unicode patterns
        sanitized = "".join(c for c in sanitized if ord(c) > 31 or c in "\n\t")

        return sanitized.strip()

    def _normalize_input_schema(self, schema: dict) -> dict:
        """
        Normalize input schema to MCP JSON Schema format.

        Args:
            schema: Original schema

        Returns:
            Normalized schema
        """
        if not schema:
            return {"type": "object", "properties": {}}

        # Ensure schema has required MCP fields
        normalized = {
            "type": schema.get("type", "object"),
            "properties": schema.get("properties", {}),
            "required": schema.get("required", []),
        }

        # Clean up property definitions
        for prop_name, prop_def in normalized["properties"].items():
            if not isinstance(prop_def, dict):
                normalized["properties"][prop_name] = {"type": "string"}
            elif "type" not in prop_def:
                prop_def["type"] = "string"

        return normalized
