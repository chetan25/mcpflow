"""Weather MCP Server - demonstrates real-world MCP with mock data."""

from mcpflow import MCPServerDecorator, tool
from datetime import datetime, timedelta
from typing import List, Dict


@MCPServerDecorator(name="weather-server", version="0.1.0", description="Weather data provider")
class WeatherServer:
    """MCP server that provides weather information."""
    
    # Mock weather data
    MOCK_WEATHER = {
        "New York": {"temp": 72, "condition": "Sunny", "humidity": 45},
        "San Francisco": {"temp": 65, "condition": "Cloudy", "humidity": 60},
        "London": {"temp": 55, "condition": "Rainy", "humidity": 80},
        "Tokyo": {"temp": 68, "condition": "Clear", "humidity": 50},
    }
    
    @tool(description="Get current weather for a city")
    def get_weather(self, city: str) -> dict:
        """Get current weather conditions for a city."""
        if city not in self.MOCK_WEATHER:
            return {"error": f"City '{city}' not found", "available_cities": list(self.MOCK_WEATHER.keys())}
        
        weather = self.MOCK_WEATHER[city]
        return {
            "city": city,
            "temperature": weather["temp"],
            "condition": weather["condition"],
            "humidity": weather["humidity"],
            "timestamp": datetime.now().isoformat()
        }
    
    @tool(description="Get weather forecast for N days")
    def forecast(self, city: str, days: int = 3) -> dict:
        """Get weather forecast for specified number of days."""
        if city not in self.MOCK_WEATHER:
            return {"error": f"City '{city}' not found"}
        
        if days < 1 or days > 14:
            return {"error": "Days must be between 1 and 14"}
        
        base_weather = self.MOCK_WEATHER[city]
        forecast_data = []
        
        for i in range(days):
            date = (datetime.now() + timedelta(days=i)).date()
            forecast_data.append({
                "date": str(date),
                "temp_high": base_weather["temp"] + i,
                "temp_low": base_weather["temp"] - 5 - i,
                "condition": base_weather["condition"],
                "precipitation_chance": 20 + (i * 5)
            })
        
        return {
            "city": city,
            "forecast": forecast_data,
            "generated_at": datetime.now().isoformat()
        }
    
    @tool(description="List all available cities")
    def list_cities(self) -> dict:
        """List all cities with available weather data."""
        return {
            "cities": list(self.MOCK_WEATHER.keys()),
            "count": len(self.MOCK_WEATHER)
        }


if __name__ == "__main__":
    server = WeatherServer()
    
    print("=== Weather Server Demo ===\n")
    
    # Get current weather
    result1 = server.get_weather("New York")
    print(f"get_weather('New York'):")
    print(f"  {result1}\n")
    
    # Get forecast
    result2 = server.forecast("San Francisco", days=3)
    print(f"forecast('San Francisco', days=3):")
    print(f"  {result2}\n")
    
    # List cities
    result3 = server.list_cities()
    print(f"list_cities():")
    print(f"  {result3}\n")
    
    # Show server info
    print(f"Server: {server.__class__._server_def.name}")
    print(f"Tools: {list(server.__class__._tools.keys())}")
