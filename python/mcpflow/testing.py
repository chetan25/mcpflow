"""Testing utilities for MCPFlow."""

from typing import Any, Callable, Dict, List, Optional
from unittest.mock import MagicMock, AsyncMock

from .server import MCPServer
from .config import Config


class MockToolExpectation:
    """Expectation for a mock tool call."""

    def __init__(self, tool_name: str):
        """Initialize mock tool expectation.
        
        Args:
            tool_name: Name of the tool
        """
        self.tool_name = tool_name
        self._return_value: Optional[Dict[str, Any]] = None
        self._exception: Optional[Exception] = None

    def returns(self, value: Dict[str, Any]) -> "MockToolExpectation":
        """Set the return value for this tool.
        
        Args:
            value: Return value dictionary
            
        Returns:
            Self for chaining
        """
        self._return_value = value
        return self

    def raises(self, exception: Exception) -> "MockToolExpectation":
        """Set an exception to be raised by this tool.
        
        Args:
            exception: Exception to raise
            
        Returns:
            Self for chaining
        """
        self._exception = exception
        return self


class MCPFixture:
    """Fixture for testing with mock MCP tools."""

    def __init__(self):
        """Initialize MCPFixture."""
        self._expectations: Dict[str, MockToolExpectation] = {}
        self._call_history: Dict[str, List[Dict[str, Any]]] = {}
        self._tools: Dict[str, MagicMock] = {}

    def expect_tool(self, tool_name: str) -> MockToolExpectation:
        """Create an expectation for a tool call.
        
        Args:
            tool_name: Name of the tool to expect
            
        Returns:
            MockToolExpectation for setting up behavior
        """
        expectation = MockToolExpectation(tool_name)
        self._expectations[tool_name] = expectation
        return expectation

    async def call_tool(
        self, tool_name: str, inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a mocked tool.
        
        Args:
            tool_name: Name of the tool to call
            inputs: Tool inputs
            
        Returns:
            Tool result
            
        Raises:
            ValueError: If tool not found
            Exception: If exception was set for the tool
        """
        if tool_name not in self._expectations:
            raise ValueError(f"Tool '{tool_name}' not expected. Call expect_tool first.")

        # Record call
        if tool_name not in self._call_history:
            self._call_history[tool_name] = []
        self._call_history[tool_name].append(inputs)

        expectation = self._expectations[tool_name]

        # Raise exception if set
        if expectation._exception:
            raise expectation._exception

        # Return expected value
        if expectation._return_value is not None:
            return expectation._return_value

        # Default return
        return {"status": "success", "tool": tool_name}

    def called(self, tool_name: str) -> bool:
        """Check if a tool was called.
        
        Args:
            tool_name: Name of the tool to check
            
        Returns:
            True if the tool was called, False otherwise
        """
        return self.call_count(tool_name) > 0

    def call_count(self, tool_name: str) -> int:
        """Get the number of times a tool was called.
        
        Args:
            tool_name: Name of the tool to check
            
        Returns:
            Number of times the tool was called
        """
        return len(self._call_history.get(tool_name, []))

    def get_calls(self, tool_name: str) -> List[Dict[str, Any]]:
        """Get all calls to a tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            List of call arguments
        """
        return self._call_history.get(tool_name, [])

    def reset(self) -> None:
        """Reset all expectations and call history."""
        self._expectations.clear()
        self._call_history.clear()
        self._tools.clear()


def mock_tool(
    name: str,
    return_value: Optional[Dict[str, Any]] = None,
    side_effect: Optional[Exception] = None,
    **kwargs: Any,
) -> MockToolExpectation:
    """Create a mock tool expectation.
    
    Args:
        name: Name of the tool
        return_value: Return value for the tool
        side_effect: Exception to raise
        **kwargs: Additional keyword arguments
        
    Returns:
        MockToolExpectation for the tool
    """
    expectation = MockToolExpectation(name)
    
    if return_value is not None:
        expectation.returns(return_value)
    
    if side_effect is not None:
        expectation.raises(side_effect)
    
    return expectation


class MockServer(MCPServer):
    """Mock MCP server for testing."""

    def __init__(self, config: Optional[Config] = None):
        """Initialize mock server.
        
        Args:
            config: Server configuration
        """
        if config is None:
            config = Config.from_dict({"teams": []})
        super().__init__(config)
        self.call_history: List[Dict[str, Any]] = []
        self._mock_tools: Dict[str, Dict[str, Any]] = {}

    async def call_tool(self, name: str, params: Dict[str, Any]) -> Any:
        """Call a tool and record the call.
        
        Args:
            name: Tool name
            params: Tool parameters
            
        Returns:
            Tool result
        """
        self.call_history.append({"tool": name, "params": params})
        
        # Return mocked result if set
        if name in self._mock_tools:
            return self._mock_tools[name]
        
        return await super().call_tool(name, params)

    def get_call_history(self) -> List[Dict[str, Any]]:
        """Get the history of tool calls.
        
        Returns:
            List of call records
        """
        return self.call_history

    def reset_call_history(self) -> None:
        """Reset the call history."""
        self.call_history.clear()

    def set_tool_result(self, tool_name: str, result: Dict[str, Any]) -> None:
        """Set the result for a mocked tool.
        
        Args:
            tool_name: Name of the tool
            result: Result to return when tool is called
        """
        self._mock_tools[tool_name] = result

    def clear_mock_tools(self) -> None:
        """Clear all mocked tool results."""
        self._mock_tools.clear()


def create_test_server(debug: bool = True) -> MCPServer:
    """Create a test server instance.
    
    Args:
        debug: Enable debug logging
        
    Returns:
        MCPServer instance
    """
    config = Config.from_dict({"teams": [], "debug": debug, "log_level": "DEBUG"})
    return MCPServer(config)
