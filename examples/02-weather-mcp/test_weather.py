"""Tests for the Weather Server example."""

import pytest
from weather_server import WeatherServer, WeatherData


@pytest.fixture
def weather_server():
    """Create a weather server instance for testing."""
    return WeatherServer(name="test-weather", description="Test weather server")


class TestGetWeatherTool:
    """Tests for the get_weather tool."""

    def test_get_weather_new_york(self, weather_server):
        """Test getting weather for New York."""
        result = weather_server.get_weather("New York")
        assert result["city"] == "new_york"
        assert "temp" in result
        assert "condition" in result
        assert "humidity" in result

    def test_get_weather_case_insensitive(self, weather_server):
        """Test that city names are case insensitive."""
        result = weather_server.get_weather("LONDON")
        assert result["city"] == "london"
        assert "temp" in result

    def test_get_weather_invalid_city(self, weather_server):
        """Test getting weather for non-existent city."""
        result = weather_server.get_weather("Atlantis")
        assert "error" in result
        assert "available_cities" in result

    def test_get_weather_all_cities(self, weather_server):
        """Test getting weather for all known cities."""
        for city in WeatherData.WEATHER_DB.keys():
            result = weather_server.get_weather(city)
            assert "error" not in result
            assert result["city"] == city


class TestGetForecastTool:
    """Tests for the get_forecast tool."""

    def test_get_forecast_default_days(self, weather_server):
        """Test getting forecast with default days (5)."""
        result = weather_server.get_forecast("Tokyo")
        assert result["city"] == "tokyo"
        assert result["days"] == 5
        assert len(result["forecast"]) == 5

    def test_get_forecast_custom_days(self, weather_server):
        """Test getting forecast with custom number of days."""
        result = weather_server.get_forecast("Paris", days=3)
        assert result["days"] == 3
        assert len(result["forecast"]) == 3

    def test_get_forecast_max_days_capped(self, weather_server):
        """Test that forecast days are capped at 10."""
        result = weather_server.get_forecast("Sydney", days=20)
        assert result["days"] == 10
        assert len(result["forecast"]) <= 10

    def test_get_forecast_min_days(self, weather_server):
        """Test that forecast requires at least 1 day."""
        result = weather_server.get_forecast("London", days=0)
        assert result["days"] >= 1

    def test_get_forecast_invalid_city(self, weather_server):
        """Test forecast for non-existent city."""
        result = weather_server.get_forecast("Unknown")
        assert "error" in result

    def test_forecast_contains_required_fields(self, weather_server):
        """Test that forecast contains required fields."""
        result = weather_server.get_forecast("New York", days=1)
        forecast_day = result["forecast"][0]
        assert "day" in forecast_day
        assert "temperature" in forecast_day
        assert "condition" in forecast_day
        assert "chance_of_rain" in forecast_day


class TestListCitiesTool:
    """Tests for the list_available_cities tool."""

    def test_list_available_cities(self, weather_server):
        """Test listing available cities."""
        result = weather_server.list_available_cities()
        assert "cities" in result
        assert "total" in result
        assert result["total"] == len(result["cities"])
        assert len(result["cities"]) > 0

    def test_list_contains_known_cities(self, weather_server):
        """Test that list contains known cities."""
        result = weather_server.list_available_cities()
        assert "new_york" in result["cities"]
        assert "london" in result["cities"]
        assert "tokyo" in result["cities"]


class TestCompareWeatherTool:
    """Tests for the compare_weather tool."""

    def test_compare_two_valid_cities(self, weather_server):
        """Test comparing weather between two valid cities."""
        result = weather_server.compare_weather("New York", "Tokyo")
        assert "city1" in result
        assert "city2" in result
        assert "temp_diff" in result
        assert "warmer_city" in result
        assert result["city1"]["name"] == "new_york"
        assert result["city2"]["name"] == "tokyo"

    def test_compare_identifies_warmer_city(self, weather_server):
        """Test that comparison identifies the warmer city."""
        result = weather_server.compare_weather("Tokyo", "London")
        # Tokyo should be warmer than London
        assert result["warmer_city"] == "tokyo"

    def test_compare_with_invalid_city(self, weather_server):
        """Test comparison with non-existent city."""
        result = weather_server.compare_weather("New York", "Unknown")
        assert "error" in result

    def test_temp_diff_accuracy(self, weather_server):
        """Test that temperature difference is calculated correctly."""
        result = weather_server.compare_weather("New York", "Sydney")
        temp1 = WeatherData.WEATHER_DB["new_york"]["temp"]
        temp2 = WeatherData.WEATHER_DB["sydney"]["temp"]
        expected_diff = abs(temp1 - temp2)
        assert result["temp_diff"] == expected_diff


class TestServerTools:
    """Tests for server tools registration."""

    def test_server_has_tools(self, weather_server):
        """Test that server has registered tools."""
        assert len(weather_server.tools) > 0

    def test_server_tool_names(self, weather_server):
        """Test that server has expected tool names."""
        tool_names = {tool.name for tool in weather_server.tools}
        expected = {
            "get_weather",
            "get_forecast",
            "list_available_cities",
            "compare_weather",
        }
        assert tool_names == expected

    def test_all_tools_have_descriptions(self, weather_server):
        """Test that all tools have descriptions."""
        for tool in weather_server.tools:
            assert tool.description is not None
            assert len(tool.description) > 0

    def test_all_tools_have_schema(self, weather_server):
        """Test that all tools have input schemas."""
        for tool in weather_server.tools:
            assert tool.input_schema is not None
            assert "type" in tool.input_schema
            assert "properties" in tool.input_schema
