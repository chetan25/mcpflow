"""Tests for the Multi-MCP Agent example."""

import pytest
from agent import MultiMCPAgent


@pytest.fixture
def agent():
    """Create a multi-MCP agent instance for testing."""
    return MultiMCPAgent(model="gpt-4")


class TestAgentInitialization:
    """Tests for agent initialization."""

    def test_agent_creates_successfully(self, agent):
        """Test that agent initializes successfully."""
        assert agent is not None
        assert agent.model == "gpt-4"

    def test_agent_has_registries(self, agent):
        """Test that agent has required registries."""
        assert agent.registry is not None
        assert agent.tool_registry is not None
        assert agent.chat_manager is not None

    def test_agent_has_tools(self, agent):
        """Test that agent has registered tools."""
        tools = agent.get_available_tools()
        assert len(tools) > 0

    def test_agent_has_both_mcps(self, agent):
        """Test that agent has both MCP types."""
        echo_tools = agent.get_tools_by_mcp("echo")
        weather_tools = agent.get_tools_by_mcp("weather")
        assert len(echo_tools) > 0
        assert len(weather_tools) > 0


class TestToolDiscovery:
    """Tests for tool discovery."""

    def test_get_available_tools(self, agent):
        """Test getting all available tools."""
        tools = agent.get_available_tools()
        assert isinstance(tools, list)
        assert all(isinstance(t, dict) for t in tools)

    def test_get_tools_by_mcp_echo(self, agent):
        """Test getting echo MCP tools."""
        tools = agent.get_tools_by_mcp("echo")
        tool_names = {t["name"] for t in tools}
        expected = {"echo", "reverse", "uppercase"}
        assert tool_names == expected

    def test_get_tools_by_mcp_weather(self, agent):
        """Test getting weather MCP tools."""
        tools = agent.get_tools_by_mcp("weather")
        tool_names = {t["name"] for t in tools}
        expected = {"get_weather", "get_forecast", "list_available_cities"}
        assert tool_names == expected

    def test_get_tools_by_category(self, agent):
        """Test getting tools by category."""
        echo_tools = agent.get_tools_by_category("echo")
        weather_tools = agent.get_tools_by_category("weather")
        assert len(echo_tools) > 0
        assert len(weather_tools) > 0

    def test_all_tools_have_required_fields(self, agent):
        """Test that all tools have required fields."""
        tools = agent.get_available_tools()
        required_fields = {"name", "mcp", "description", "input_schema"}
        for tool in tools:
            assert required_fields.issubset(set(tool.keys()))


class TestEchoToolSimulation:
    """Tests for echo tool simulation."""

    def test_echo_tool_call(self, agent):
        """Test simulating echo tool call."""
        result = agent.simulate_tool_call("echo", "echo", {"text": "hello"})
        assert result["result"] == "hello"
        assert result["mcp"] == "echo"
        assert result["tool"] == "echo"

    def test_reverse_tool_call(self, agent):
        """Test simulating reverse tool call."""
        result = agent.simulate_tool_call("reverse", "echo", {"text": "hello"})
        assert result["result"] == "olleh"
        assert result["mcp"] == "echo"

    def test_uppercase_tool_call(self, agent):
        """Test simulating uppercase tool call."""
        result = agent.simulate_tool_call("uppercase", "echo", {"text": "hello"})
        assert result["result"] == "HELLO"
        assert result["mcp"] == "echo"

    def test_unknown_echo_tool(self, agent):
        """Test unknown echo tool error handling."""
        result = agent.simulate_tool_call("unknown", "echo", {})
        assert "error" in result


class TestWeatherToolSimulation:
    """Tests for weather tool simulation."""

    def test_list_cities_tool_call(self, agent):
        """Test listing available cities."""
        result = agent.simulate_tool_call(
            "list_available_cities", "weather", {}
        )
        assert "cities" in result
        assert len(result["cities"]) > 0
        assert result["mcp"] == "weather"

    def test_get_weather_tool_call(self, agent):
        """Test getting weather for a city."""
        result = agent.simulate_tool_call(
            "get_weather", "weather", {"city": "New York"}
        )
        assert result["city"] == "New York"
        assert "temperature" in result
        assert "condition" in result
        assert "humidity" in result
        assert result["mcp"] == "weather"

    def test_get_forecast_tool_call(self, agent):
        """Test getting forecast."""
        result = agent.simulate_tool_call(
            "get_forecast", "weather", {"city": "London", "days": 3}
        )
        assert result["city"] == "London"
        assert result["days"] == 3
        assert len(result["forecast"]) == 3
        assert result["mcp"] == "weather"

    def test_get_forecast_default_days(self, agent):
        """Test forecast with default days."""
        result = agent.simulate_tool_call(
            "get_forecast", "weather", {"city": "Paris"}
        )
        assert result["days"] == 5

    def test_unknown_weather_tool(self, agent):
        """Test unknown weather tool error handling."""
        result = agent.simulate_tool_call("unknown", "weather", {})
        assert "error" in result


class TestMultiMCPIntegration:
    """Tests for multi-MCP integration."""

    def test_process_request(self, agent):
        """Test processing a user request."""
        result = agent.process_request("What is the weather in London?")
        assert "request" in result
        assert "available_tools" in result
        assert "mcps" in result
        assert "status" in result

    def test_mixed_mcp_operations(self, agent):
        """Test operations across multiple MCPs."""
        # Call echo MCP
        echo_result = agent.simulate_tool_call("echo", "echo", {"text": "weather"})
        assert echo_result["result"] == "weather"

        # Call weather MCP
        weather_result = agent.simulate_tool_call(
            "get_weather", "weather", {"city": "Tokyo"}
        )
        assert weather_result["city"] == "Tokyo"

        # Both should succeed
        assert "error" not in echo_result
        assert "error" not in weather_result

    def test_tool_routing(self, agent):
        """Test that tools are properly routed to their MCPs."""
        # Echo tools should only be available in echo MCP
        echo_tools = agent.get_tools_by_mcp("echo")
        echo_names = {t["name"] for t in echo_tools}
        assert "echo" in echo_names
        assert "get_weather" not in echo_names

        # Weather tools should only be in weather MCP
        weather_tools = agent.get_tools_by_mcp("weather")
        weather_names = {t["name"] for t in weather_tools}
        assert "get_weather" in weather_names
        assert "echo" not in weather_names


class TestErrorHandling:
    """Tests for error handling."""

    def test_unknown_mcp_error(self, agent):
        """Test error handling for unknown MCP."""
        result = agent.simulate_tool_call("tool", "unknown_mcp", {})
        assert "error" in result

    def test_missing_parameters_handled(self, agent):
        """Test that missing parameters are handled."""
        # Tool should handle empty inputs gracefully
        result = agent.simulate_tool_call("get_weather", "weather", {})
        # Result should have a city field (might be "Unknown")
        assert "city" in result or "error" in result

    def test_multiple_sequential_calls(self, agent):
        """Test multiple sequential tool calls."""
        results = []
        for i in range(3):
            result = agent.simulate_tool_call(
                "echo", "echo", {"text": f"message_{i}"}
            )
            results.append(result)

        assert len(results) == 3
        assert all("result" in r for r in results)
