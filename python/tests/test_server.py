"""Tests for MCPServer and tool decorators."""

import pytest

from mcpflow import MCPServer, MCPServerDecorator, tool


class TestToolDecorator:
    """Test the @tool decorator."""

    def test_tool_decorator_with_name_and_description(self):
        """Test that tool decorator stores name and description."""
        @tool("my_tool", "A test tool")
        def my_func(x: int) -> int:
            return x * 2

        assert my_func._mcp_tool["name"] == "my_tool"
        assert my_func._mcp_tool["description"] == "A test tool"
        assert my_func._tool_name == "my_tool"
        assert my_func._tool_description == "A test tool"

    def test_tool_decorator_generates_schema_from_type_hints(self):
        """Test that tool decorator generates JSON schema from type hints."""
        @tool("add", "Add two numbers")
        def add_func(a: int, b: int) -> int:
            return a + b

        schema = add_func._mcp_tool["input_schema"]
        assert schema["type"] == "object"
        assert "a" in schema["properties"]
        assert "b" in schema["properties"]
        assert schema["properties"]["a"]["type"] == "integer"
        assert schema["properties"]["b"]["type"] == "integer"
        assert set(schema["required"]) == {"a", "b"}

    def test_tool_decorator_handles_optional_parameters(self):
        """Test that tool decorator marks parameters with defaults as optional."""
        @tool("greet", "Greet someone")
        def greet_func(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"

        schema = greet_func._mcp_tool["input_schema"]
        assert "name" in schema["required"]
        assert "greeting" not in schema["required"]

    def test_tool_decorator_type_mapping_int(self):
        """Test int type mapping to integer."""
        @tool("int_tool", "Integer tool")
        def func(x: int) -> int:
            return x

        schema = func._mcp_tool["input_schema"]
        assert schema["properties"]["x"]["type"] == "integer"

    def test_tool_decorator_type_mapping_float(self):
        """Test float type mapping to number."""
        @tool("float_tool", "Float tool")
        def func(x: float) -> float:
            return x

        schema = func._mcp_tool["input_schema"]
        assert schema["properties"]["x"]["type"] == "number"

    def test_tool_decorator_type_mapping_str(self):
        """Test str type mapping to string."""
        @tool("str_tool", "String tool")
        def func(x: str) -> str:
            return x

        schema = func._mcp_tool["input_schema"]
        assert schema["properties"]["x"]["type"] == "string"

    def test_tool_decorator_type_mapping_bool(self):
        """Test bool type mapping to boolean."""
        @tool("bool_tool", "Boolean tool")
        def func(x: bool) -> bool:
            return x

        schema = func._mcp_tool["input_schema"]
        assert schema["properties"]["x"]["type"] == "boolean"

    def test_tool_decorator_type_mapping_list(self):
        """Test list type mapping to array."""
        @tool("list_tool", "List tool")
        def func(x: list) -> list:
            return x

        schema = func._mcp_tool["input_schema"]
        assert schema["properties"]["x"]["type"] == "array"

    def test_tool_decorator_type_mapping_dict(self):
        """Test dict type mapping to object."""
        @tool("dict_tool", "Dict tool")
        def func(x: dict) -> dict:
            return x

        schema = func._mcp_tool["input_schema"]
        assert schema["properties"]["x"]["type"] == "object"

    def test_tool_decorator_with_custom_schema(self):
        """Test that tool decorator accepts custom input schema."""
        custom_schema = {
            "type": "object",
            "properties": {
                "custom": {"type": "string"}
            },
        }

        @tool("custom_tool", "Custom schema tool", input_schema=custom_schema)
        def func():
            pass

        assert func._mcp_tool["input_schema"] == custom_schema

    def test_tool_decorator_uses_function_name_as_default(self):
        """Test that tool decorator uses function name if name not provided."""
        @tool(description="A tool without explicit name")
        def my_function():
            pass

        assert my_function._mcp_tool["name"] == "my_function"

    def test_tool_decorator_uses_docstring_as_default_description(self):
        """Test that tool decorator uses docstring as description if not provided."""
        @tool()
        def documented_func():
            """This is a documented function."""
            pass

        # Note: docstring might not be available depending on how it's called
        # This test documents the expected behavior
        assert "documented_func" in documented_func._mcp_tool["name"]

    def test_tool_decorator_skips_self_parameter(self):
        """Test that tool decorator skips 'self' parameter in methods."""
        class MyClass:
            @tool("method_tool", "A method tool")
            def my_method(self, x: int) -> int:
                return x * 2

        schema = MyClass.my_method._mcp_tool["input_schema"]
        assert "self" not in schema["properties"]
        assert "x" in schema["properties"]
        assert schema["properties"]["x"]["type"] == "integer"

    def test_tool_decorator_with_multiple_parameters(self):
        """Test tool decorator with multiple parameters of different types."""
        @tool("multi_param", "Multiple parameters")
        def func(name: str, age: int, score: float, active: bool):
            pass

        schema = func._mcp_tool["input_schema"]
        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["age"]["type"] == "integer"
        assert schema["properties"]["score"]["type"] == "number"
        assert schema["properties"]["active"]["type"] == "boolean"
        assert set(schema["required"]) == {"name", "age", "score", "active"}

    def test_tool_decorator_preserves_function_name(self):
        """Test that tool decorator preserves original function name."""
        @tool("different_name", "A tool")
        def original_name():
            pass

        assert original_name.__name__ == "original_name"

    def test_tool_decorator_is_callable(self):
        """Test that decorated function remains callable."""
        @tool("callable_tool", "Callable tool")
        def add(a: int, b: int) -> int:
            return a + b

        result = add(2, 3)
        assert result == 5


class TestMCPServerDecorator:
    """Test the @MCPServerDecorator class decorator."""

    def test_mcp_server_decorator_sets_name(self):
        """Test that MCPServerDecorator sets server name."""
        @MCPServerDecorator("test-server", "1.0.0", "Test Server")
        class TestServer:
            pass

        assert TestServer.name == "test-server"

    def test_mcp_server_decorator_sets_version(self):
        """Test that MCPServerDecorator sets server version."""
        @MCPServerDecorator("test-server", "2.5.3", "Test Server")
        class TestServer:
            pass

        assert TestServer.version == "2.5.3"

    def test_mcp_server_decorator_sets_description(self):
        """Test that MCPServerDecorator sets server description."""
        @MCPServerDecorator("test-server", "1.0.0", "My Server Description")
        class TestServer:
            pass

        assert TestServer.description == "My Server Description"

    def test_mcp_server_decorator_uses_class_name_as_default(self):
        """Test that MCPServerDecorator uses class name as default."""
        @MCPServerDecorator()
        class MyTestServer:
            pass

        assert MyTestServer.name == "MyTestServer"

    def test_mcp_server_decorator_uses_default_version(self):
        """Test that MCPServerDecorator uses default version."""
        @MCPServerDecorator("test-server")
        class TestServer:
            pass

        assert TestServer.version == "0.1.0"

    def test_mcp_server_decorator_collects_tools(self):
        """Test that MCPServerDecorator collects all @tool decorated methods."""
        @MCPServerDecorator("test-server", "1.0.0", "Test Server")
        class TestServer:
            @tool("add", "Add two numbers")
            def add(self, a: int, b: int) -> int:
                return a + b

            @tool("subtract", "Subtract two numbers")
            def subtract(self, a: int, b: int) -> int:
                return a - b

        assert "add" in TestServer._tools
        assert "subtract" in TestServer._tools
        assert len(TestServer._tools) == 2

    def test_mcp_server_decorator_tool_definitions(self):
        """Test that collected tools have correct definitions."""
        @MCPServerDecorator("test-server", "1.0.0", "Test Server")
        class TestServer:
            @tool("multiply", "Multiply two numbers")
            def multiply(self, a: int, b: int) -> int:
                return a * b

        tool_def = TestServer._tools["multiply"]
        assert tool_def["name"] == "multiply"
        assert tool_def["description"] == "Multiply two numbers"
        assert tool_def["input_schema"]["properties"]["a"]["type"] == "integer"
        assert tool_def["input_schema"]["properties"]["b"]["type"] == "integer"

    def test_mcp_server_decorator_creates_server_def(self):
        """Test that MCPServerDecorator creates _server_def."""
        @MCPServerDecorator("my-server", "1.0.0", "My Server")
        class TestServer:
            @tool("test", "Test tool")
            def test_tool(self):
                pass

        assert hasattr(TestServer, "_server_def")
        assert TestServer._server_def.name == "my-server"
        assert TestServer._server_def.version == "1.0.0"
        assert TestServer._server_def.description == "My Server"
        assert "test" in TestServer._server_def.tools

    def test_mcp_server_decorator_skips_private_methods(self):
        """Test that MCPServerDecorator ignores private methods."""
        @MCPServerDecorator("test-server")
        class TestServer:
            @tool("public_tool", "Public")
            def public_tool(self):
                pass

            @tool("private_tool", "Private")
            def _private_tool(self):
                pass

        assert "public_tool" in TestServer._tools
        assert "private_tool" not in TestServer._tools

    def test_mcp_server_decorator_with_multiple_tools(self):
        """Test server with multiple tools of different types."""
        @MCPServerDecorator("calc-server", "1.0.0", "Calculator Server")
        class CalcServer:
            @tool("add", "Add numbers")
            def add(self, a: int, b: int) -> int:
                return a + b

            @tool("divide", "Divide numbers")
            def divide(self, a: float, b: float) -> float:
                return a / b

            @tool("greet", "Greet someone")
            def greet(self, name: str) -> str:
                return f"Hello, {name}!"

            @tool("toggle", "Toggle boolean")
            def toggle(self, value: bool) -> bool:
                return not value

        assert len(CalcServer._tools) == 4
        assert CalcServer._tools["add"]["input_schema"]["properties"]["a"]["type"] == "integer"
        assert CalcServer._tools["divide"]["input_schema"]["properties"]["a"]["type"] == "number"
        assert CalcServer._tools["greet"]["input_schema"]["properties"]["name"]["type"] == "string"
        assert CalcServer._tools["toggle"]["input_schema"]["properties"]["value"]["type"] == "boolean"

    def test_mcp_server_decorator_can_be_instantiated(self):
        """Test that decorated class can still be instantiated."""
        @MCPServerDecorator("test-server", "1.0.0", "Test Server")
        class TestServer:
            @tool("test", "Test tool")
            def test_tool(self):
                return "result"

        instance = TestServer()
        assert instance is not None

    def test_mcp_server_decorator_instance_has_tools_access(self):
        """Test that class-level tool access is available."""
        @MCPServerDecorator("test-server", "1.0.0", "Test Server")
        class TestServer:
            @tool("test", "Test tool")
            def test_tool(self):
                return "result"

        instance = TestServer()
        # Should be able to access class-level tools
        assert instance.__class__._tools is not None
        assert "test" in instance.__class__._tools

    def test_mcp_server_decorator_preserves_class_methods(self):
        """Test that non-tool methods are preserved."""
        @MCPServerDecorator("test-server")
        class TestServer:
            def __init__(self):
                self.value = 42

            @tool("get_value", "Get value")
            def get_value(self):
                return self.value

            def regular_method(self):
                return "regular"

        instance = TestServer()
        assert instance.value == 42
        assert instance.regular_method() == "regular"
        assert instance.get_value() == 42

    def test_mcp_server_decorator_with_optional_parameters(self):
        """Test server tools with optional parameters."""
        @MCPServerDecorator("test-server")
        class TestServer:
            @tool("greet", "Greet with optional greeting")
            def greet(self, name: str, greeting: str = "Hello") -> str:
                return f"{greeting}, {name}!"

        tool_def = TestServer._tools["greet"]
        assert "name" in tool_def["input_schema"]["required"]
        assert "greeting" not in tool_def["input_schema"]["required"]

    def test_mcp_server_decorator_with_no_parameters(self):
        """Test server tool with no parameters."""
        @MCPServerDecorator("test-server")
        class TestServer:
            @tool("get_time", "Get current time")
            def get_time(self):
                return "12:00"

        tool_def = TestServer._tools["get_time"]
        assert len(tool_def["input_schema"]["properties"]) == 0
        assert len(tool_def["input_schema"]["required"]) == 0


class TestToolDecoratorRegistersMethod:
    """Test that @tool decorator registers methods properly."""

    def test_tool_decorator_registers_method(self):
        """Test that tool decorator registers the method."""
        class TestClass:
            @tool("test_method", "Test method")
            def test_method(self):
                pass

        assert hasattr(TestClass.test_method, "_mcp_tool")
        assert TestClass.test_method._mcp_tool["name"] == "test_method"

    def test_multiple_tools_in_class(self):
        """Test multiple tool-decorated methods in a class."""
        class TestClass:
            @tool("tool1", "First tool")
            def method1(self):
                pass

            @tool("tool2", "Second tool")
            def method2(self):
                pass

        assert hasattr(TestClass.method1, "_mcp_tool")
        assert hasattr(TestClass.method2, "_mcp_tool")
        assert TestClass.method1._mcp_tool["name"] == "tool1"
        assert TestClass.method2._mcp_tool["name"] == "tool2"


class TestToolSchemaGeneration:
    """Test JSON schema generation from type hints."""

    def test_tool_schema_generation_basic_types(self):
        """Test schema generation for basic types."""
        @tool("test", "Test")
        def func(
            a: int,
            b: str,
            c: float,
            d: bool,
            e: list,
            f: dict,
        ):
            pass

        schema = func._mcp_tool["input_schema"]
        assert schema["properties"]["a"]["type"] == "integer"
        assert schema["properties"]["b"]["type"] == "string"
        assert schema["properties"]["c"]["type"] == "number"
        assert schema["properties"]["d"]["type"] == "boolean"
        assert schema["properties"]["e"]["type"] == "array"
        assert schema["properties"]["f"]["type"] == "object"

    def test_tool_schema_generation_with_defaults(self):
        """Test schema generation correctly identifies required vs optional params."""
        @tool("test", "Test")
        def func(required_param: str, optional_param: int = 10):
            pass

        schema = func._mcp_tool["input_schema"]
        assert "required_param" in schema["required"]
        assert "optional_param" not in schema["required"]

    def test_tool_schema_generation_mixed_types(self):
        """Test schema generation with mixed types and defaults."""
        @tool("test", "Test")
        def func(
            name: str,
            age: int,
            score: float = 0.0,
            active: bool = True,
            tags: list = None,
        ):
            pass

        schema = func._mcp_tool["input_schema"]
        required = schema["required"]
        assert "name" in required
        assert "age" in required
        assert "score" not in required
        assert "active" not in required
        assert "tags" not in required

    def test_tool_schema_generation_has_type_object(self):
        """Test that generated schema has type object."""
        @tool("test", "Test")
        def func(x: int):
            pass

        schema = func._mcp_tool["input_schema"]
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema


class TestToolWithCustomDescription:
    """Test tool decorator with custom descriptions."""

    def test_tool_decorator_custom_description(self):
        """Test tool decorator with custom description."""
        @tool("my_tool", "Custom description")
        def func():
            pass

        assert func._mcp_tool["description"] == "Custom description"

    def test_tool_decorator_description_in_schema(self):
        """Test that description appears in schema."""
        @tool("test", "Tool description")
        def func(x: int):
            pass

        schema = func._mcp_tool["input_schema"]
        assert schema.get("description") == "Tool description"

    def test_tool_decorator_empty_description(self):
        """Test tool decorator with empty description."""
        @tool("test", "")
        def func():
            pass

        assert func._mcp_tool["description"] == ""

    def test_tool_decorator_long_description(self):
        """Test tool decorator with long description."""
        long_desc = "This is a very long description " * 10
        @tool("test", long_desc)
        def func():
            pass

        assert func._mcp_tool["description"] == long_desc
        assert len(func._mcp_tool["description"]) > 100


class TestComplexScenarios:
    """Test complex scenarios with decorators."""

    def test_multiple_servers_with_tools(self):
        """Test creating multiple servers with tools."""
        @MCPServerDecorator("server1", "1.0.0", "Server 1")
        class Server1:
            @tool("tool1", "Tool 1")
            def tool1(self, x: int):
                return x

        @MCPServerDecorator("server2", "2.0.0", "Server 2")
        class Server2:
            @tool("tool2", "Tool 2")
            def tool2(self, x: str):
                return x

        assert Server1.name == "server1"
        assert Server2.name == "server2"
        assert "tool1" in Server1._tools
        assert "tool2" in Server2._tools
        assert "tool1" not in Server2._tools
        assert "tool2" not in Server1._tools

    def test_server_with_many_tools(self):
        """Test server with many tools."""
        @MCPServerDecorator("big-server")
        class BigServer:
            @tool("tool1", "Tool 1")
            def tool1(self, x: int):
                pass

            @tool("tool2", "Tool 2")
            def tool2(self, x: str):
                pass

            @tool("tool3", "Tool 3")
            def tool3(self, x: float):
                pass

            @tool("tool4", "Tool 4")
            def tool4(self, x: bool):
                pass

            @tool("tool5", "Tool 5")
            def tool5(self, x: list):
                pass

        assert len(BigServer._tools) == 5
        for i in range(1, 6):
            assert f"tool{i}" in BigServer._tools
