"""Unit tests for Echo MCP Server."""

import pytest
from echo_server import EchoServer


class TestEchoServer:
    """Test suite for EchoServer."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.server = EchoServer()
    
    def test_echo_basic(self):
        """Test basic echo functionality."""
        result = self.server.echo("Hello")
        assert result["result"] == "Hello"
        assert result["length"] == 5
    
    def test_echo_empty_string(self):
        """Test echo with empty string."""
        result = self.server.echo("")
        assert result["result"] == ""
        assert result["length"] == 0
    
    def test_reverse_basic(self):
        """Test basic reverse functionality."""
        result = self.server.reverse("Hello")
        assert result["result"] == "olleH"
        assert result["original"] == "Hello"
    
    def test_reverse_palindrome(self):
        """Test reverse with palindrome."""
        result = self.server.reverse("racecar")
        assert result["result"] == "racecar"
    
    def test_word_count_single(self):
        """Test word count with single word."""
        result = self.server.word_count("Hello")
        assert result["words"] == 1
        assert result["characters"] == 5
    
    def test_word_count_multiple(self):
        """Test word count with multiple words."""
        result = self.server.word_count("Hello MCPFlow World")
        assert result["words"] == 3
        assert result["characters"] == 19
    
    def test_word_count_with_spaces(self):
        """Test word count handles extra spaces."""
        result = self.server.word_count("Hello  MCPFlow")
        assert result["words"] == 2
    
    def test_server_metadata(self):
        """Test server metadata is set correctly."""
        assert self.server.__class__._server_def.name == "echo-server"
        assert self.server.__class__._server_def.version == "0.1.0"
        assert "echo" in self.server.__class__._tools
        assert "reverse" in self.server.__class__._tools
        assert "word_count" in self.server.__class__._tools
    
    def test_tools_are_callable(self):
        """Test that tools are registered and callable."""
        tools = self.server.__class__._tools
        assert len(tools) == 3
        for tool_name in ["echo", "reverse", "word_count"]:
            assert tool_name in tools
            tool_func = tools[tool_name]
            assert callable(tool_func)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
