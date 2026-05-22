"""Test fixtures and mock patterns for MCPFlow."""

import pytest
from mcpflow import MCPFixture, mock_tool, MockToolExpectation


class TestMockingPatterns:
    """Demonstrate MCPFlow testing and mocking capabilities."""
    
    def test_mock_tool_basic(self):
        """Test basic tool mocking."""
        # Create a mock tool
        get_user = mock_tool("get_user", returns={"id": 123, "name": "Alice"})
        
        # Call the mock
        result = get_user(user_id=1)
        
        assert result == {"id": 123, "name": "Alice"}
    
    def test_mock_tool_with_exception(self):
        """Test mock tool that raises exception."""
        # Create a mock that raises
        delete_user = mock_tool("delete_user", raises=ValueError("User not found"))
        
        with pytest.raises(ValueError, match="User not found"):
            delete_user(user_id=999)
    
    def test_mock_tool_call_tracking(self):
        """Test tracking mock tool calls."""
        fixture = MCPFixture()
        
        # Setup expectation
        fixture.expect_tool("calculate_sum").returns({"sum": 15})
        
        # Call tool
        result = fixture.call_tool("calculate_sum", {"a": 7, "b": 8})
        
        # Verify
        assert result == {"sum": 15}
        assert fixture.called("calculate_sum")
        assert fixture.call_count("calculate_sum") == 1
    
    def test_mock_tool_multiple_calls(self):
        """Test tracking multiple calls to same tool."""
        fixture = MCPFixture()
        fixture.expect_tool("increment").returns({"result": 1})
        
        # Make multiple calls
        fixture.call_tool("increment", {"value": 0})
        fixture.call_tool("increment", {"value": 1})
        fixture.call_tool("increment", {"value": 2})
        
        # Verify call count
        assert fixture.call_count("increment") == 3
        
        # Get all calls
        calls = fixture.get_calls("increment")
        assert len(calls) == 3
    
    def test_mock_fixture_reset(self):
        """Test resetting mock fixture."""
        fixture = MCPFixture()
        fixture.expect_tool("fetch_data").returns({"data": "test"})
        
        # Make calls
        fixture.call_tool("fetch_data", {})
        assert fixture.call_count("fetch_data") == 1
        
        # Reset
        fixture.reset()
        assert fixture.call_count("fetch_data") == 0
    
    def test_chainable_mock_api(self):
        """Test fluent mock API."""
        fixture = MCPFixture()
        
        # Chainable setup
        fixture.expect_tool("api_call")\
            .returns({"status": "success", "data": [1, 2, 3]})
        
        result = fixture.call_tool("api_call", {})
        assert result["status"] == "success"
        assert len(result["data"]) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
