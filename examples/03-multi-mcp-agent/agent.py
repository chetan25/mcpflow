"""
Multi-MCP Agent Example

This example demonstrates:
- Using ChatManager with multiple MCP servers
- Tool routing across different MCPs
- Orchestrating multiple services in a single agent
- Configuration of multiple MCP servers
"""

from typing import Dict, List, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from mcpflow import MCPRegistry, ChatManager, ToolRegistry


class MultiMCPAgent:
    """Agent that coordinates multiple MCP servers."""

    def __init__(self, model: str = "gpt-4"):
        """
        Initialize the multi-MCP agent.

        Args:
            model: LLM model to use
        """
        self.model = model
        self.registry = MCPRegistry()
        self.tool_registry = ToolRegistry()
        self.chat_manager = ChatManager(model=model, registry=self.registry)

        # Initialize tool registry with example tools
        self._setup_tools()

    def _setup_tools(self):
        """Set up example tools from different MCPs."""
        # Echo server tools
        self.tool_registry.register_tool(
            name="echo",
            mcp="echo",
            description="Echo text",
            input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        )

        self.tool_registry.register_tool(
            name="reverse",
            mcp="echo",
            description="Reverse text",
            input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        )

        self.tool_registry.register_tool(
            name="uppercase",
            mcp="echo",
            description="Convert text to uppercase",
            input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        )

        # Weather server tools
        self.tool_registry.register_tool(
            name="get_weather",
            mcp="weather",
            description="Get current weather for a city",
            input_schema={
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        )

        self.tool_registry.register_tool(
            name="get_forecast",
            mcp="weather",
            description="Get weather forecast",
            input_schema={
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "days": {"type": "integer", "default": 5},
                },
                "required": ["city"],
            },
        )

        self.tool_registry.register_tool(
            name="list_available_cities",
            mcp="weather",
            description="List available cities",
            input_schema={"type": "object", "properties": {}, "required": []},
        )

    def get_available_tools(self) -> List[Dict]:
        """
        Get list of available tools from all MCPs.

        Returns:
            List of tool definitions
        """
        return [tool.to_dict() for tool in self.tool_registry.list_tools()]

    def get_tools_by_mcp(self, mcp_name: str) -> List[Dict]:
        """
        Get tools from a specific MCP.

        Args:
            mcp_name: Name of the MCP

        Returns:
            List of tool definitions from that MCP
        """
        return [
            tool.to_dict()
            for tool in self.tool_registry.list_tools()
            if tool.mcp == mcp_name
        ]

    def get_tools_by_category(self, category: str) -> List[Dict]:
        """
        Get tools by category (echo or weather).

        Args:
            category: Tool category

        Returns:
            List of tools in that category
        """
        return self.get_tools_by_mcp(category)

    def simulate_tool_call(self, tool_name: str, mcp_name: str, inputs: Dict) -> Dict:
        """
        Simulate calling a tool.

        This is for demonstration. In production, this would route to the actual MCP.

        Args:
            tool_name: Name of the tool
            mcp_name: Name of the MCP server
            inputs: Input parameters

        Returns:
            Simulated tool result
        """
        if mcp_name == "echo":
            return self._simulate_echo_tool(tool_name, inputs)
        elif mcp_name == "weather":
            return self._simulate_weather_tool(tool_name, inputs)
        else:
            return {"error": f"Unknown MCP: {mcp_name}"}

    def _simulate_echo_tool(self, tool_name: str, inputs: Dict) -> Dict:
        """Simulate echo server tools."""
        text = inputs.get("text", "")

        if tool_name == "echo":
            return {"result": text, "mcp": "echo", "tool": tool_name}
        elif tool_name == "reverse":
            return {"result": text[::-1], "mcp": "echo", "tool": tool_name}
        elif tool_name == "uppercase":
            return {"result": text.upper(), "mcp": "echo", "tool": tool_name}
        else:
            return {"error": f"Unknown echo tool: {tool_name}"}

    def _simulate_weather_tool(self, tool_name: str, inputs: Dict) -> Dict:
        """Simulate weather server tools."""
        if tool_name == "list_available_cities":
            return {
                "cities": ["New York", "London", "Tokyo", "Sydney", "Paris"],
                "mcp": "weather",
                "tool": tool_name,
            }
        elif tool_name == "get_weather":
            city = inputs.get("city", "Unknown")
            return {
                "city": city,
                "temperature": 72,
                "condition": "Sunny",
                "humidity": 65,
                "mcp": "weather",
                "tool": tool_name,
            }
        elif tool_name == "get_forecast":
            city = inputs.get("city", "Unknown")
            days = inputs.get("days", 5)
            return {
                "city": city,
                "days": days,
                "forecast": [
                    {"day": i + 1, "temp": 70 + i, "condition": "Sunny"}
                    for i in range(days)
                ],
                "mcp": "weather",
                "tool": tool_name,
            }
        else:
            return {"error": f"Unknown weather tool: {tool_name}"}

    def process_request(self, request: str) -> Dict:
        """
        Process a user request that may require multiple MCP calls.

        Args:
            request: User request

        Returns:
            Response with tool calls and results
        """
        return {
            "request": request,
            "available_tools": len(self.get_available_tools()),
            "mcps": ["echo", "weather"],
            "status": "ready",
            "message": f"Ready to process: {request}",
        }


def main():
    """Run the multi-MCP agent example."""
    print("Multi-MCP Agent Example")
    print("=" * 50)

    agent = MultiMCPAgent(model="gpt-4")

    print("\nAvailable MCPs:")
    for mcp_name in ["echo", "weather"]:
        tools = agent.get_tools_by_mcp(mcp_name)
        print(f"\n{mcp_name.upper()} MCP ({len(tools)} tools):")
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")

    print("\n" + "=" * 50)
    print("Example Operations:")
    print("=" * 50)

    # Example 1: Echo tool simulation
    print("\n1. Echo 'hello' using echo MCP:")
    result = agent.simulate_tool_call("echo", "echo", {"text": "hello"})
    print(f"   Result: {result}")

    # Example 2: Reverse tool
    print("\n2. Reverse 'hello' using echo MCP:")
    result = agent.simulate_tool_call("reverse", "echo", {"text": "hello"})
    print(f"   Result: {result}")

    # Example 3: Get weather
    print("\n3. Get weather for New York using weather MCP:")
    result = agent.simulate_tool_call("get_weather", "weather", {"city": "New York"})
    print(f"   Result: {result}")

    # Example 4: Get forecast
    print("\n4. Get 3-day forecast for London:")
    result = agent.simulate_tool_call(
        "get_forecast", "weather", {"city": "London", "days": 3}
    )
    print(f"   Result: {result}")

    # Example 5: List cities
    print("\n5. List available cities:")
    result = agent.simulate_tool_call("list_available_cities", "weather", {})
    print(f"   Result: {result}")

    print("\n" + "=" * 50)
    print("Agent initialized successfully!")


if __name__ == "__main__":
    main()
