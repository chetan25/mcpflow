# Weather MCP Server

This example demonstrates a more complex MCP server with:

- **Multiple parameters** including optional ones
- **Complex return types** (dictionaries, lists)
- **Tool composition** with helper functions
- **Error handling** and validation
- **Integration testing**

## Features

This example implements a weather service with 4 tools:

1. **get_weather** - Get current weather for a city
   - Required: `city` (string)
   - Returns: Current conditions, temperature, humidity, wind

2. **get_forecast** - Get weather forecast
   - Required: `city` (string)
   - Optional: `days` (integer, default: 5, max: 10)
   - Returns: 5-day forecast with daily data

3. **list_available_cities** - List all available cities
   - No parameters
   - Returns: List of supported cities

4. **compare_weather** - Compare weather between two cities
   - Required: `city1`, `city2` (strings)
   - Returns: Side-by-side comparison with temperature difference

## Running

### Installation and Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest test_weather.py -v

# Run specific test class
pytest test_weather.py::TestGetWeatherTool -v

# Run with coverage
pytest test_weather.py --cov=weather_server
```

### Expected Output

```
test session starts ...
collected 22 items

test_weather.py::TestGetWeatherTool::test_get_weather_new_york PASSED  [ 4%]
test_weather.py::TestGetWeatherTool::test_get_weather_case_insensitive PASSED [ 9%]
...
======================== 22 passed in 0.18s ========================
```

### Direct Usage

```python
from weather_server import WeatherServer

# Create server
server = WeatherServer(name="weather", description="Weather API")

# Get weather
weather = server.get_weather("London")
print(weather)
# Output: {'city': 'london', 'temp': 59, 'condition': 'Rainy', 'humidity': 80, 'wind': 18}

# Get forecast
forecast = server.get_forecast("Tokyo", days=3)
print(forecast)
# Output: {'city': 'tokyo', 'days': 3, 'forecast': [...]}

# Compare cities
comparison = server.compare_weather("New York", "Sydney")
print(comparison)
# Output: {'city1': {...}, 'city2': {...}, 'temp_diff': 3, 'warmer_city': 'sydney'}
```

## Key Concepts

### 1. Optional Parameters

The `get_forecast` tool uses an optional `days` parameter:

```python
def get_forecast(self, city: str, days: int = 5) -> Dict:
```

The schema automatically marks parameters with defaults as optional.

### 2. Complex Return Types

Tools return dictionaries with structured data:

```python
return {
    "city": city,
    "forecast": [
        {
            "day": 1,
            "temperature": 72,
            "condition": "Sunny",
            "chance_of_rain": 20,
        },
        ...
    ]
}
```

### 3. Error Handling

Tools validate inputs and return error responses:

```python
if not weather:
    return {
        "error": f"Weather data not found for city: {city}",
        "available_cities": list(WeatherData.WEATHER_DB.keys()),
    }
```

### 4. Helper Classes

`WeatherData` provides:
- Static data store (simulating API)
- Helper methods for data retrieval
- Mock forecast generation

This pattern is useful for:
- Separating concerns
- Testing data logic independently
- Mocking external services

## Configuration

Create a `config.yaml` for deployment:

```yaml
mcps:
  - name: weather
    url: http://localhost:8000
    auth:
      type: bearer
      token: ${WEATHER_API_TOKEN}
    timeout: 30.0
```

Use environment variables:
- `WEATHER_API_TOKEN` - API authentication token
- `WEATHER_SERVICE_URL` - Custom service URL (optional)

## Testing Patterns

### Unit Tests

Test individual tools directly:

```python
def test_get_weather_new_york(self, weather_server):
    result = weather_server.get_weather("New York")
    assert result["city"] == "new_york"
```

### Integration Tests

Test tool interaction:

```python
def test_get_forecast_integrates_with_get_weather(self):
    weather = server.get_weather("London")
    forecast = server.get_forecast("London")
    # Both should work with same city name format
```

### Error Cases

Test error handling:

```python
def test_get_weather_invalid_city(self, weather_server):
    result = weather_server.get_weather("Unknown")
    assert "error" in result
```

## Next Steps

- See `03-multi-mcp-agent` for using multiple MCPs together
- See `04-team-config` for production configuration setup
