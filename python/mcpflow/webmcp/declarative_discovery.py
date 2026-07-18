"""Declarative tool discovery from JSON-LD and HTML forms."""

import logging
import json
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class DeclarativeDiscovery:
    """
    Discover tools from declarative page markup.

    Supports:
    - JSON-LD structured data (`@context` = "https://schema.org" or "https://webml.org")
    - HTML forms with tool annotations
    - Fallback tier for non-WebMCP sites
    """

    @staticmethod
    async def discover_from_json_ld(page) -> List[Dict[str, Any]]:
        """
        Discover tools from JSON-LD structured data.

        Looks for:
        - Action objects with WebMCP context
        - tool:action schema.org markup
        - Nested in scripts with type="application/ld+json"

        Args:
            page: Playwright page instance

        Returns:
            List of discovered tools
        """
        tools = []

        try:
            # Extract all JSON-LD blocks
            json_ld_blocks = await page.evaluate(
                """() => {
                    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                    return Array.from(scripts).map(s => s.textContent);
                }""",
            )

            for block_str in json_ld_blocks:
                try:
                    data = json.loads(block_str)

                    # Check if it's an Action or has @type: Action
                    if isinstance(data, dict):
                        tools.extend(
                            DeclarativeDiscovery._extract_actions_from_ld(data)
                        )
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item,dict):
                                tools.extend(
                                    DeclarativeDiscovery._extract_actions_from_ld(item)
                                )
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON-LD block: {e}")

        except Exception as e:
            logger.warning(f"Could not extract JSON-LD: {e}")

        return tools

    @staticmethod
    def _extract_actions_from_ld(data: dict) -> List[Dict[str, Any]]:
        """Extract Action items from JSON-LD data."""
        actions = []

        # Check if this is an Action
        item_type = data.get("@type", "")
        if isinstance(item_type, list):
            item_type = " ".join(item_type)

        if "Action" in item_type:
            tool = {
                "name": data.get("name", "unknown_action"),
                "description": data.get("description", ""),
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                "invocation": {
                    "type": "unsupported",
                    "reason": "No EntryPoint target with a urlTemplate was found for this Action",
                },
            }

            # Extract input properties from object or result
            if "object" in data and isinstance(data["object"], dict):
                obj = data["object"]
                for prop, prop_data in obj.items():
                    if not prop.startswith("@"):
                        tool["input_schema"]["properties"][prop] = {
                            "type": "string",
                            "description": f"{prop}",
                        }

            # schema.org Actions may declare a callable EntryPoint target -
            # if present, this tool can actually be invoked via HTTP fetch
            # inside the page (so the user's session cookies apply).
            target = data.get("target")
            if isinstance(target, dict) and target.get("urlTemplate"):
                tool["invocation"] = {
                    "type": "json_ld_entrypoint",
                    "url_template": target["urlTemplate"],
                    "http_method": target.get("httpMethod", "GET"),
                }

            actions.append(tool)

        # Recursively check nested structures
        for key, value in data.items():
            if isinstance(value, dict) and "@type" in value:
                actions.extend(DeclarativeDiscovery._extract_actions_from_ld(value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and "@type" in item:
                        actions.extend(DeclarativeDiscovery._extract_actions_from_ld(item))

        return actions

    @staticmethod
    async def discover_from_forms(page) -> List[Dict[str, Any]]:
        """
        Discover tools from annotated HTML forms.

        Looks for forms with data attributes:
        - data-tool-name: tool name
        - data-tool-description: tool description
        - data-tool-destructive: if present, marks tool as destructive

        Args:
            page: Playwright page instance

        Returns:
            List of discovered tools
        """
        tools = []

        try:
            # Find all annotated forms
            forms_data = await page.evaluate(
                """() => {
                    const forms = document.querySelectorAll('form[data-tool-name]');
                    return Array.from(forms).map(form => {
                        const inputs = form.querySelectorAll('input, select, textarea');
                        const properties = {};
                        const required = [];

                        inputs.forEach(input => {
                            if (input.name) {
                                properties[input.name] = {
                                    type: input.type === 'number' ? 'number' : 'string',
                                    description: input.placeholder || input.name,
                                    required: input.required || false,
                                };
                                if (input.required) {
                                    required.push(input.name);
                                }
                            }
                        });

                        return {
                            name: form.dataset.toolName,
                            description: form.dataset.toolDescription || '',
                            destructive: form.dataset.toolDestructive !== undefined,
                            properties: properties,
                            required: required,
                        };
                    });
                }""",
            )

            for form_data in forms_data:
                tool = {
                    "name": form_data["name"],
                    "description": form_data["description"],
                    "input_schema": {
                        "type": "object",
                        "properties": form_data["properties"],
                        "required": form_data.get("required", []),
                    },
                    "destructive": form_data.get("destructive", False),
                    "invocation": {
                        "type": "form",
                        "selector": f'form[data-tool-name="{form_data["name"]}"]',
                    },
                }
                tools.append(tool)

        except Exception as e:
            logger.warning(f"Could not extract forms: {e}")

        return tools

    @staticmethod
    async def discover_from_llms_txt(page, origin: str) -> List[Dict[str, Any]]:
        """
        Discover tools from /llms.txt convention.

        The llms.txt file can contain action definitions in YAML or Markdown.

        Args:
            page: Playwright page instance (to navigate to /llms.txt)
            origin: Full page URL discovery was run on - only the scheme
                and host are used, since llms.txt is a site-root convention

        Returns:
            List of discovered tools, or empty if file not found
        """
        tools = []

        from urllib.parse import urlparse

        parsed = urlparse(origin)
        if parsed.scheme not in ("http", "https"):
            # llms.txt is an HTTP(S) site-root convention; skip cleanly for
            # file:// and other schemes rather than attempting an invalid
            # navigation (e.g. appending "/llms.txt" onto a file path).
            logger.debug(f"Skipping llms.txt discovery for non-HTTP origin: {origin}")
            return tools

        try:
            # Navigate to /llms.txt at the site root, not wherever `origin`'s
            # own path happens to point
            llms_url = f"{parsed.scheme}://{parsed.netloc}/llms.txt"
            response = await page.goto(llms_url, wait_until="networkidle")

            if response.status != 200:
                logger.debug(f"llms.txt not found at {llms_url}")
                return tools

            # Extract text content
            content = await page.text_content("body")

            if not content:
                return tools

            # Parse as simple key=value or YAML-ish format
            lines = content.split("\n")
            current_tool = None

            for line in lines:
                line = line.strip()

                if not line or line.startswith("#"):
                    continue

                # Very basic parsing
                if line.startswith("- name:"):
                    if current_tool:
                        tools.append(current_tool)
                    current_tool = {
                        "name": line.split(":", 1)[1].strip(),
                        "description": "",
                        "input_schema": {"type": "object", "properties": {}, "required": []},
                        "invocation": {
                            "type": "unsupported",
                            "reason": "llms.txt tools are informational only; no callable endpoint",
                        },
                    }
                elif current_tool and line.startswith("description:"):
                    current_tool["description"] = line.split(":", 1)[1].strip()

            # Add last tool
            if current_tool:
                tools.append(current_tool)

        except Exception as e:
            logger.debug(f"Could not read llms.txt: {e}")

        return tools

    @staticmethod
    async def discover_all(
        page,
        origin: str,
        include_json_ld: bool = True,
        include_forms: bool = True,
        include_llms_txt: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Discover tools using all declarative methods.

        Args:
            page: Playwright page instance
            origin: Origin URL
            include_json_ld: Enable JSON-LD discovery
            include_forms: Enable form discovery
            include_llms_txt: Enable /llms.txt discovery

        Returns:
            Combined list of discovered tools (deduplicated by name)
        """
        tools = []
        seen_names = set()

        # Try JSON-LD
        if include_json_ld:
            try:
                ld_tools = await DeclarativeDiscovery.discover_from_json_ld(page)
                for tool in ld_tools:
                    name = tool.get("name")
                    if name and name not in seen_names:
                        tools.append(tool)
                        seen_names.add(name)
                logger.info(f"Discovered {len(ld_tools)} tools from JSON-LD")
            except Exception as e:
                logger.warning(f"JSON-LD discovery failed: {e}")

        # Try forms
        if include_forms:
            try:
                form_tools = await DeclarativeDiscovery.discover_from_forms(page)
                for tool in form_tools:
                    name = tool.get("name")
                    if name and name not in seen_names:
                        tools.append(tool)
                        seen_names.add(name)
                logger.info(f"Discovered {len(form_tools)} tools from forms")
            except Exception as e:
                logger.warning(f"Form discovery failed: {e}")

        # Try /llms.txt
        if include_llms_txt:
            try:
                llms_tools = await DeclarativeDiscovery.discover_from_llms_txt(
                    page, origin
                )
                for tool in llms_tools:
                    name = tool.get("name")
                    if name and name not in seen_names:
                        tools.append(tool)
                        seen_names.add(name)
                logger.info(f"Discovered {len(llms_tools)} tools from llms.txt")
            except Exception as e:
                logger.warning(f"llms.txt discovery failed: {e}")

        return tools
