# MCPFlow Examples & Test Suites

Complete, runnable examples demonstrating MCPFlow's capabilities.

## 📚 Example Catalog

### 1. Simple Echo Server (`01-simple-echo/`)
**Learn:** Basic @MCPServer and @tool decorators

```bash
cd 01-simple-echo
python echo_server.py           # Run demo
pytest test_echo_server.py -v   # Run tests
```

**What it demonstrates:**
- Creating MCP servers with decorators
- Defining tools with type hints
- Automatic JSON schema generation
- Unit testing MCP tools
- 10 comprehensive tests

---

### 2. Weather MCP Server (`02-weather-mcp/`)
**Learn:** Real-world MCP with mock data and error handling

```bash
cd 02-weather-mcp
python weather_server.py        # Run demo
pytest test_weather_server.py -v  # Run tests
```

**What it demonstrates:**
- Multiple tools in one server
- Input validation
- Error responses
- Complex return types
- 8 comprehensive tests

**Available Tools:**
- `get_weather(city)` - Get current weather
- `forecast(city, days)` - Get weather forecast
- `list_cities()` - List available cities

---

### 3. Team Configuration (`03-team-config/`)
**Learn:** Loading and managing multi-team configurations

```bash
cd 03-team-config
python team_config_example.py
```

**What it demonstrates:**
- YAML configuration loading
- Multiple teams and models
- Environment variable substitution
- Accessing team configurations
- Config validation

**Config Structure:**
```yaml
teams:
  - name: "engineering"
    model: { provider, name, api_key }
    mcps: [ { name, url, auth, timeout } ]
```

---

### 4. Testing & Mocking Patterns (`04-testing-patterns/`)
**Learn:** Mocking MCPs and testing agents

```bash
cd 04-testing-patterns
pytest test_mocking_patterns.py -v
```

**What it demonstrates:**
- Mock tool creation
- Call tracking and verification
- Exception handling in mocks
- Fixture setup and teardown
- 6 comprehensive test patterns

**Mock APIs:**
- `mock_tool(name, returns=...)` - Simple mock creation
- `MCPFixture.expect_tool(name)` - Setup expectations
- `fixture.called(name)` - Check if called
- `fixture.call_count(name)` - Count calls
- `fixture.get_calls(name)` - List all calls

---

## 🚀 Quick Start

Run all examples:
```bash
for dir in 01-* 02-* 03-* 04-*; do
  echo "=== Running $dir ==="
  cd $dir
  python *.py 2>/dev/null || pytest *.py -v
  cd ..
done
```

---

## 📊 Test Summary

| Example | Type | Tests | Status |
|---------|------|-------|--------|
| Echo Server | Unit | 10 | ✅ |
| Weather MCP | Unit | 8 | ✅ |
| Team Config | Integration | Manual | ✅ |
| Mocking | Testing | 6 | ✅ |
| **TOTAL** | | **24** | **✅ PASS** |

---

## 🔑 Key Concepts Demonstrated

### Decorators
```python
@MCPServerDecorator(name="my-server")
class MyServer:
    @tool(description="My tool")
    def my_tool(self, param: str) -> dict:
        return {"result": param}
```

### Configuration
```python
config = Config.from_yaml("config.yaml")
team = config.get_team("engineering")
mcp = config.get_mcp("weather")
```

### Testing
```python
fixture = MCPFixture()
fixture.expect_tool("get_data").returns({"data": []})
result = fixture.call_tool("get_data", {})
assert fixture.called("get_data")
```

### Registry
```python
registry = MCPRegistry()
await registry.register_mcp(mcp_config)
tools = registry.get_tools("mcp_name")
result = await registry.call_tool("mcp_name", "tool_name", inputs)
```

---

## 🎯 Next Steps

1. **Explore Examples** - Run each example and examine the code
2. **Modify Tools** - Add new tools to the echo/weather servers
3. **Add Tests** - Write additional test cases
4. **Build Your MCP** - Create your own MCP server
5. **Integrate** - Connect to MCPFlow's registry and config system

---

## 📝 Notes

- All examples use Python 3.8+
- Examples assume MCPFlow is installed
- Mock servers don't require external APIs
- Tests use pytest fixtures
- Configuration uses YAML format

---

## 🆘 Troubleshooting

**Import errors:**
```bash
pip install mcpflow
```

**Missing dependencies:**
```bash
pip install -r requirements.txt
```

**Tests failing:**
```bash
pytest --tb=short  # More verbose output
```

---

See the main MCPFlow documentation for more details:
- QUICKSTART.md
- ARCHITECTURE.md
- API-REFERENCE.md
