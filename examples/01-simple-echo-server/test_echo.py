"""Tests for the Echo Server example."""

import pytest
from echo_server import EchoServer


@pytest.fixture
def echo_server():
    """Create an echo server instance for testing."""
    return EchoServer()


class TestEchoTool:
    """Tests for the echo tool."""

    def test_echo_returns_input(self, echo_server):
        """Test that echo returns the input text."""
        result = echo_server.echo("Hello, World!")
        assert result == "Hello, World!"

    def test_echo_with_empty_string(self, echo_server):
        """Test echo with empty string."""
        result = echo_server.echo("")
        assert result == ""

    def test_echo_with_special_characters(self, echo_server):
        """Test echo with special characters."""
        result = echo_server.echo("!@#$%^&*()")
        assert result == "!@#$%^&*()"


class TestReverseTool:
    """Tests for the reverse tool."""

    def test_reverse_simple_string(self, echo_server):
        """Test reversing a simple string."""
        result = echo_server.reverse("hello")
        assert result == "olleh"

    def test_reverse_palindrome(self, echo_server):
        """Test reversing a palindrome."""
        result = echo_server.reverse("racecar")
        assert result == "racecar"

    def test_reverse_with_spaces(self, echo_server):
        """Test reversing text with spaces."""
        result = echo_server.reverse("hello world")
        assert result == "dlrow olleh"


class TestUppercaseTool:
    """Tests for the uppercase tool."""

    def test_uppercase_lowercase(self, echo_server):
        """Test converting lowercase to uppercase."""
        result = echo_server.uppercase("hello")
        assert result == "HELLO"

    def test_uppercase_mixed_case(self, echo_server):
        """Test converting mixed case to uppercase."""
        result = echo_server.uppercase("HeLLo WoRLd")
        assert result == "HELLO WORLD"

    def test_uppercase_already_uppercase(self, echo_server):
        """Test uppercase on already uppercase text."""
        result = echo_server.uppercase("HELLO")
        assert result == "HELLO"


class TestLowercaseTool:
    """Tests for the lowercase tool."""

    def test_lowercase_uppercase(self, echo_server):
        """Test converting uppercase to lowercase."""
        result = echo_server.lowercase("HELLO")
        assert result == "hello"

    def test_lowercase_mixed_case(self, echo_server):
        """Test converting mixed case to lowercase."""
        result = echo_server.lowercase("HeLLo WoRLd")
        assert result == "hello world"


class TestCharCountTool:
    """Tests for the char_count tool."""

    def test_char_count_simple(self, echo_server):
        """Test counting characters in simple string."""
        result = echo_server.char_count("hello")
        assert result == 5

    def test_char_count_with_spaces(self, echo_server):
        """Test counting characters including spaces."""
        result = echo_server.char_count("hello world")
        assert result == 11

    def test_char_count_empty_string(self, echo_server):
        """Test counting characters in empty string."""
        result = echo_server.char_count("")
        assert result == 0


class TestWordCountTool:
    """Tests for the word_count tool."""

    def test_word_count_simple(self, echo_server):
        """Test counting words."""
        result = echo_server.word_count("hello world")
        assert result == 2

    def test_word_count_single_word(self, echo_server):
        """Test word count with single word."""
        result = echo_server.word_count("hello")
        assert result == 1

    def test_word_count_multiple_spaces(self, echo_server):
        """Test word count with multiple spaces."""
        result = echo_server.word_count("hello  world  test")
        assert result == 3


class TestServerTools:
    """Tests for server tools registration."""

    def test_server_has_tools(self):
        """Test that server has registered tools."""
        assert len(EchoServer._tools) > 0

    def test_server_tool_names(self):
        """Test that server has expected tool names."""
        tool_names = {tool['name'] for tool in EchoServer._tools.values()}
        expected = {"echo", "reverse", "uppercase", "lowercase", "char_count", "word_count"}
        assert tool_names == expected

    def test_server_tool_has_schema(self):
        """Test that each tool has a schema."""
        for tool_name, tool_def in EchoServer._tools.items():
            assert tool_def is not None
            assert "input_schema" in tool_def
            assert "type" in tool_def["input_schema"]
            assert "properties" in tool_def["input_schema"]
