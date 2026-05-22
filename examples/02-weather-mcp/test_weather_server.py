"""Tests for Weather MCP Server."""

import pytest
from weather_server import WeatherServer


class TestWeatherServer:
    """Test suite for WeatherServer."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.server = WeatherServer()
    
    def test_get_weather_valid_city(self):
        """Test getting weather for valid city."""
        result = self.server.get_weather("New York")
        assert result["city"] == "New York"
        assert result["temperature"] == 72
        assert result["condition"] == "Sunny"
        assert result["humidity"] == 45
        assert "timestamp" in result
    
    def test_get_weather_invalid_city(self):
        """Test getting weather for invalid city."""
        result = self.server.get_weather("Atlantis")
        assert "error" in result
        assert "not found" in result["error"]
        assert "available_cities" in result
    
    def test_forecast_default_days(self):
        """Test forecast with default days parameter."""
        result = self.server.forecast("London")
        assert result["city"] == "London"
        assert len(result["forecast"]) == 3  # Default is 3 days
    
    def test_forecast_custom_days(self):
        """Test forecast with custom days."""
        result = self.server.forecast("Tokyo", days=7)
        assert len(result["forecast"]) == 7
        for day in result["forecast"]:
            assert "date" in day
            assert "temp_high" in day
            assert "temp_low" in day
            assert "precipitation_chance" in day
    
    def test_forecast_invalid_days(self):
        """Test forecast with invalid days count."""
        result1 = self.server.forecast("New York", days=0)
        assert "error" in result1
        
        result2 = self.server.forecast("New York", days=20)
        assert "error" in result2
    
    def test_forecast_invalid_city(self):
        """Test forecast for invalid city."""
        result = self.server.forecast("Mars")
        assert "error" in result
    
    def test_list_cities(self):
        """Test listing available cities."""
        result = self.server.list_cities()
        assert "cities" in result
        assert len(result["cities"]) == 4
        assert "New York" in result["cities"]
        assert "San Francisco" in result["cities"]
        assert result["count"] == 4
    
    def test_server_metadata(self):
        """Test server metadata."""
        assert self.server.__class__._server_def.name == "weather-server"
        assert "get_weather" in self.server.__class__._tools
        assert "forecast" in self.server.__class__._tools
        assert "list_cities" in self.server.__class__._tools


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
