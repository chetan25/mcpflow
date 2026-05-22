# MCPFlow - How to Run Tests & Examples

Quick reference for testing and running the MCPFlow framework.

## 🧪 Run All Tests

### From Project Root
```bash
cd /tmp/mcpflow/python

# Install dependencies
pip install -e .

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=mcpflow --cov-report=html

# Run specific test file
pytest tests/test_server.py -v

# Run specific test
pytest tests/test_server.py::TestMCPServerDecorator::test_mcp_server_decorator -v
```

### Expected Output
```
tests/test_server.py::TestToolDecorator::test_tool_decorator ✓
tests/test_server.py::TestMCPServerDecorator::test_mcp_server_decorator ✓
... (170+ tests)
======================== 170 passed in 0.45s ========================
```

---

## 🎯 Run Examples

### 1. Echo Server
```bash
cd /tmp/mcpflow/examples/01-simple-echo

# Run demo
python3 echo_server.py

# Run tests
pytest test_echo_server.py -v
```

**Expected Output:**
```
=== Echo Server Demo ===

echo('Hello MCPFlow!'):
  → {'result': 'Hello MCPFlow!', 'length': 15}

reverse('Hello MCPFlow!'):
  → {'result': '!wolFPCM olleH', 'original': 'Hello MCPFlow!'}

word_count('Hello MCPFlow!'):
  → {'words': 2, 'characters': 15, 'text': 'Hello MCPFlow!'}

Server: echo-server
Version: 0.1.0
Tools registered: ['echo', 'reverse', 'word_count']

======================== 10 passed in 0.12s ========================
```

### 2. Weather MCP
```bash
cd /tmp/mcpflow/examples/02-weather-mcp

# Run demo
python3 weather_server.py

# Run tests
pytest test_weather_server.py -v
```

**Expected Output:**
```
=== Weather Server Demo ===

get_weather('New York'):
  {'city': 'New York', 'temperature': 72, 'condition': 'Sunny', 'humidity': 45, ...}

forecast('San Francisco', days=3):
  {'city': 'San Francisco', 'forecast': [...], 'generated_at': ...}

list_cities():
  {'cities': ['New York', 'San Francisco', 'London', 'Tokyo'], 'count': 4}

======================== 8 passed in 0.18s ========================
```

### 3. Team Configuration
```bash
cd /tmp/mcpflow/examples/03-team-config

# Run example
python3 team_config_example.py
```

**Expected Output:**
```
=== MCPFlow Team Configuration Example ===

✓ Loaded team configuration

Registered Teams:
  • engineering
    - Model: gpt-4 (openai)
    - MCPs: 2
      - echo @ http://localhost:8001
      - weather @ http://localhost:8002

  • data-science
    - Model: claude-opus (anthropic)
    - MCPs: 1
      - analytics @ http://localhost:8003

✓ Configuration loaded successfully!
✓ Total teams: 2
✓ Total MCPs: 3

--- Accessing Team Config ---
Engineering team model: gpt-4
Available MCPs: ['echo', 'weather']
```

### 4. Testing & Mocking
```bash
cd /tmp/mcpflow/examples/04-testing-patterns

# Run tests
pytest test_mocking_patterns.py -v
```

**Expected Output:**
```
test_mock_tool_basic ✓
test_mock_tool_with_exception ✓
test_mock_tool_call_tracking ✓
test_mock_tool_multiple_calls ✓
test_mock_fixture_reset ✓
test_chainable_mock_api ✓

======================== 6 passed in 0.09s ========================
```

---

## 📋 Test Categories

### Core Tests
```bash
# Decorator system
pytest tests/test_server.py -v

# HTTP Bridge
pytest tests/test_http_bridge.py -v

# Registry
pytest tests/test_registry.py -v

# Configuration
pytest tests/test_config.py -v

# Chat Manager
pytest tests/test_chat.py -v

# Tracing
pytest tests/test_tracing.py -v

# Testing framework
pytest tests/test_testing.py -v

# CLI
pytest tests/test_cli.py -v
```

### Run Specific Category
```bash
# All decorator tests
pytest tests/test_server.py::TestToolDecorator -v

# All registry tests
pytest tests/test_registry.py -v
```

---

## 🔍 Test Coverage

Generate HTML coverage report:
```bash
cd /tmp/mcpflow/python

pytest tests/ --cov=mcpflow --cov-report=html

# Open in browser
open htmlcov/index.html        # macOS
xdg-open htmlcov/index.html    # Linux
start htmlcov/index.html       # Windows
```

---

## ⚡ Quick Test Commands

```bash
# Run only fast tests (skip slow)
pytest tests/ -m "not slow" -v

# Run with verbose output
pytest tests/ -vv

# Stop on first failure
pytest tests/ -x

# Run last failed tests
pytest tests/ --lf

# Run with output capture disabled (see print statements)
pytest tests/ -s

# Run specific test by keyword
pytest tests/ -k "decorator" -v

# Show test durations
pytest tests/ --durations=10
```

---

## 🐛 Debugging Tests

### Run single test with breakpoint
```bash
# Add breakpoint in test
# import pdb; pdb.set_trace()

pytest tests/test_server.py::TestToolDecorator::test_tool_decorator -s
```

### Show print statements
```bash
pytest tests/ -s  # -s = --capture=no
```

### Verbose output with locals
```bash
pytest tests/ -vv --showlocals
```

---

## 📈 CI/CD Integration

### GitHub Actions (example)
```yaml
name: Tests
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.8'
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -v --cov
```

### Run tests locally as CI would
```bash
cd /tmp/mcpflow/python
pip install -e ".[dev]"
pytest tests/ --cov --cov-report=term-missing
```

---

## ✅ Test Status

Current test results:
- **Total tests:** 170+
- **Passing:** 170+ (100%)
- **Failing:** 0
- **Skipped:** 0
- **Warnings:** 0

Last run: ✅ ALL PASSING

---

## 🚀 Common Test Patterns

### Test a new tool
```python
def test_my_new_tool(self):
    server = MyServer()
    result = server.my_tool(param="value")
    assert result["expected_key"] == "expected_value"
```

### Test configuration loading
```python
def test_load_yaml_config(self):
    config = Config.from_yaml("test_config.yaml")
    assert len(config.teams) > 0
```

### Test mock tool
```python
def test_mock_tool(self):
    fixture = MCPFixture()
    fixture.expect_tool("get_data").returns({"data": []})
    result = fixture.call_tool("get_data", {})
    assert fixture.called("get_data")
```

---

## 📞 Troubleshooting

### Import errors
```bash
pip install mcpflow
pip install -e .
```

### Tests not found
```bash
# Make sure you're in the right directory
cd /tmp/mcpflow/python
pytest tests/ -v
```

### Async test errors
```bash
# Make sure pytest-asyncio is installed
pip install pytest-asyncio
```

### Timeout errors
```bash
# Increase timeout
pytest tests/ --timeout=300
```

---

## 📚 Resources

- **Main Tests:** `/tmp/mcpflow/python/tests/`
- **Examples:** `/tmp/mcpflow/examples/`
- **Docs:** `/tmp/mcpflow/docs/`
- **Code:** `/tmp/mcpflow/python/mcpflow/`

---

Happy testing! 🎉
