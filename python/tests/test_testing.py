"""Tests for testing utilities."""

import pytest

from mcpflow import MCPFixture, MockToolExpectation, mock_tool, MockServer


class TestMockToolExpectation:
    """Tests for MockToolExpectation class."""

    def test_init(self):
        """Test initializing a mock tool expectation."""
        expectation = MockToolExpectation("test_tool")
        assert expectation.tool_name == "test_tool"
        assert expectation._return_value is None
        assert expectation._exception is None

    def test_returns(self):
        """Test setting return value."""
        expectation = MockToolExpectation("tool")
        result = expectation.returns({"status": "ok"})

        assert result is expectation  # Test chaining
        assert expectation._return_value == {"status": "ok"}

    def test_raises(self):
        """Test setting exception."""
        expectation = MockToolExpectation("tool")
        exc = ValueError("test error")
        result = expectation.raises(exc)

        assert result is expectation  # Test chaining
        assert expectation._exception is exc

    def test_returns_and_raises_chaining(self):
        """Test chaining returns and raises."""
        exc = RuntimeError("error")
        expectation = (
            MockToolExpectation("tool").returns({"data": "value"}).raises(exc)
        )

        assert expectation._return_value == {"data": "value"}
        assert expectation._exception is exc


class TestMCPFixture:
    """Tests for MCPFixture class."""

    def test_init(self):
        """Test initializing MCPFixture."""
        fixture = MCPFixture()
        assert fixture._expectations == {}
        assert fixture._call_history == {}
        assert fixture._tools == {}

    def test_expect_tool(self):
        """Test expecting a tool."""
        fixture = MCPFixture()
        expectation = fixture.expect_tool("my_tool")

        assert isinstance(expectation, MockToolExpectation)
        assert expectation.tool_name == "my_tool"
        assert fixture._expectations["my_tool"] is expectation

    @pytest.mark.asyncio
    async def test_call_tool_with_expectation(self):
        """Test calling a tool with expectation."""
        fixture = MCPFixture()
        fixture.expect_tool("test_tool").returns({"result": "success"})

        result = await fixture.call_tool("test_tool", {"input": "data"})
        assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_call_tool_not_expected_raises(self):
        """Test calling non-expected tool raises error."""
        fixture = MCPFixture()

        with pytest.raises(ValueError, match="not expected"):
            await fixture.call_tool("unexpected_tool", {})

    @pytest.mark.asyncio
    async def test_call_tool_with_exception(self):
        """Test tool call that raises exception."""
        fixture = MCPFixture()
        fixture.expect_tool("bad_tool").raises(ValueError("Tool error"))

        with pytest.raises(ValueError, match="Tool error"):
            await fixture.call_tool("bad_tool", {})

    @pytest.mark.asyncio
    async def test_call_tool_default_return(self):
        """Test tool call with default return value."""
        fixture = MCPFixture()
        fixture.expect_tool("tool")

        result = await fixture.call_tool("tool", {})
        assert result["status"] == "success"
        assert result["tool"] == "tool"

    @pytest.mark.asyncio
    async def test_call_history(self):
        """Test tracking tool call history."""
        fixture = MCPFixture()
        fixture.expect_tool("tool")

        await fixture.call_tool("tool", {"arg1": "val1"})
        await fixture.call_tool("tool", {"arg1": "val2"})

        assert fixture.call_count("tool") == 2
        assert fixture.called("tool") is True

    @pytest.mark.asyncio
    async def test_called_returns_false_for_uncalled_tool(self):
        """Test called() returns false for tool that wasn't called."""
        fixture = MCPFixture()
        fixture.expect_tool("tool")

        assert fixture.called("tool") is False
        assert fixture.call_count("tool") == 0

    @pytest.mark.asyncio
    async def test_get_calls(self):
        """Test getting all calls to a tool."""
        fixture = MCPFixture()
        fixture.expect_tool("search")

        inputs1 = {"query": "python"}
        inputs2 = {"query": "rust"}

        await fixture.call_tool("search", inputs1)
        await fixture.call_tool("search", inputs2)

        calls = fixture.get_calls("search")
        assert len(calls) == 2
        assert calls[0] == inputs1
        assert calls[1] == inputs2

    @pytest.mark.asyncio
    async def test_multiple_tools(self):
        """Test tracking multiple different tools."""
        fixture = MCPFixture()
        fixture.expect_tool("tool_a").returns({"a": 1})
        fixture.expect_tool("tool_b").returns({"b": 2})

        result_a = await fixture.call_tool("tool_a", {})
        result_b = await fixture.call_tool("tool_b", {})

        assert result_a == {"a": 1}
        assert result_b == {"b": 2}
        assert fixture.call_count("tool_a") == 1
        assert fixture.call_count("tool_b") == 1

    def test_reset(self):
        """Test resetting fixture."""
        fixture = MCPFixture()
        fixture.expect_tool("tool")

        # Simulate call
        fixture._call_history["tool"] = [{"arg": "val"}]

        fixture.reset()
        assert fixture._expectations == {}
        assert fixture._call_history == {}
        assert fixture._tools == {}


class TestMockToolHelper:
    """Tests for mock_tool helper function."""

    def test_mock_tool_basic(self):
        """Test creating a basic mock tool."""
        expectation = mock_tool("my_tool")
        assert expectation.tool_name == "my_tool"

    def test_mock_tool_with_return_value(self):
        """Test mock_tool with return value."""
        expectation = mock_tool("tool", return_value={"status": "ok"})
        assert expectation._return_value == {"status": "ok"}

    def test_mock_tool_with_exception(self):
        """Test mock_tool with exception."""
        exc = RuntimeError("error")
        expectation = mock_tool("tool", side_effect=exc)
        assert expectation._exception is exc

    def test_mock_tool_with_both(self):
        """Test mock_tool with both return value and exception."""
        exc = ValueError("error")
        expectation = mock_tool("tool", return_value={"data": "x"}, side_effect=exc)
        assert expectation._return_value == {"data": "x"}
        assert expectation._exception is exc

    def test_mock_tool_with_kwargs(self):
        """Test mock_tool ignores extra kwargs."""
        expectation = mock_tool(
            "tool",
            return_value={"ok": True},
            custom_kwarg="ignored",
            another="also_ignored",
        )
        assert expectation.tool_name == "tool"
        assert expectation._return_value == {"ok": True}


class TestMockServer:
    """Tests for MockServer class."""

    def test_mock_server_init(self):
        """Test initializing MockServer."""
        server = MockServer()
        assert server.call_history == []
        assert server._mock_tools == {}

    @pytest.mark.asyncio
    async def test_mock_server_call_tool_records_call(self):
        """Test that MockServer records tool calls."""
        server = MockServer()
        server.set_tool_result("test_tool", {"result": "success"})

        await server.call_tool("test_tool", {"input": "data"})

        assert len(server.call_history) == 1
        assert server.call_history[0]["tool"] == "test_tool"
        assert server.call_history[0]["params"] == {"input": "data"}

    def test_mock_server_set_tool_result(self):
        """Test setting tool result."""
        server = MockServer()
        server.set_tool_result("tool", {"data": "value"})

        assert "tool" in server._mock_tools
        assert server._mock_tools["tool"] == {"data": "value"}

    def test_mock_server_get_call_history(self):
        """Test getting call history."""
        server = MockServer()
        server.call_history.append({"tool": "test", "params": {}})

        history = server.get_call_history()
        assert len(history) == 1

    def test_mock_server_reset_call_history(self):
        """Test resetting call history."""
        server = MockServer()
        server.call_history.append({"tool": "test", "params": {}})
        assert len(server.call_history) == 1

        server.reset_call_history()
        assert len(server.call_history) == 0

    def test_mock_server_clear_mock_tools(self):
        """Test clearing mock tools."""
        server = MockServer()
        server.set_tool_result("tool1", {"data": 1})
        server.set_tool_result("tool2", {"data": 2})
        assert len(server._mock_tools) == 2

        server.clear_mock_tools()
        assert len(server._mock_tools) == 0

    @pytest.mark.asyncio
    async def test_mock_server_multiple_calls(self):
        """Test multiple tool calls."""
        server = MockServer()
        server.set_tool_result("add", {"sum": 3})
        server.set_tool_result("multiply", {"product": 6})

        await server.call_tool("add", {"a": 1, "b": 2})
        await server.call_tool("multiply", {"a": 2, "b": 3})

        assert len(server.call_history) == 2
        assert server.call_history[0]["tool"] == "add"
        assert server.call_history[1]["tool"] == "multiply"


class TestFixtureIntegration:
    """Integration tests for MCPFixture."""

    @pytest.mark.asyncio
    async def test_fixture_workflow(self):
        """Test typical fixture workflow."""
        fixture = MCPFixture()

        # Setup expectations
        fixture.expect_tool("search").returns({"results": ["a", "b"]})
        fixture.expect_tool("parse").returns({"parsed": True})

        # Call tools
        search_result = await fixture.call_tool("search", {"query": "test"})
        parse_result = await fixture.call_tool("parse", {"data": "test"})

        # Verify calls
        assert fixture.called("search")
        assert fixture.called("parse")
        assert fixture.call_count("search") == 1
        assert fixture.call_count("parse") == 1

        # Verify results
        assert search_result["results"] == ["a", "b"]
        assert parse_result["parsed"] is True

    @pytest.mark.asyncio
    async def test_fixture_with_repeated_calls(self):
        """Test fixture with repeated calls to same tool."""
        fixture = MCPFixture()
        fixture.expect_tool("counter").returns({"count": 1})

        # Call multiple times
        for _ in range(5):
            await fixture.call_tool("counter", {})

        # All calls should be recorded
        assert fixture.call_count("counter") == 5
        calls = fixture.get_calls("counter")
        assert len(calls) == 5
