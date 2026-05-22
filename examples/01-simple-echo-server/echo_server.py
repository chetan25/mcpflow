"""
Simple Echo Server Example

This is a basic MCP server demonstrating:
- MCPServerDecorator class decorator
- @tool decorator for registration
- Automatic JSON schema generation from type hints
- Simple tool implementation
"""

from mcpflow import MCPServerDecorator, tool


@MCPServerDecorator("echo-server", "0.1.0", "A simple echo server demonstrating MCPFlow basics")
class EchoServer:
    """A simple MCP server with echo and reverse tools."""

    @tool("echo", "Echo back the input text")
    def echo(self, text: str) -> str:
        """
        Echo a text string.

        Args:
            text: The text to echo

        Returns:
            The echoed text
        """
        return text

    @tool("reverse", "Reverse the input text")
    def reverse(self, text: str) -> str:
        """
        Reverse a text string.

        Args:
            text: The text to reverse

        Returns:
            The reversed text
        """
        return text[::-1]

    @tool("uppercase", "Convert text to uppercase")
    def uppercase(self, text: str) -> str:
        """
        Convert text to uppercase.

        Args:
            text: The text to convert

        Returns:
            The text in uppercase
        """
        return text.upper()

    @tool("lowercase", "Convert text to lowercase")
    def lowercase(self, text: str) -> str:
        """
        Convert text to lowercase.

        Args:
            text: The text to convert

        Returns:
            The text in lowercase
        """
        return text.lower()

    @tool("char_count", "Count characters in text")
    def char_count(self, text: str) -> int:
        """
        Count the number of characters in text.

        Args:
            text: The text to count

        Returns:
            The number of characters
        """
        return len(text)

    @tool("word_count", "Count words in text")
    def word_count(self, text: str) -> int:
        """
        Count the number of words in text.

        Args:
            text: The text to count

        Returns:
            The number of words
        """
        return len(text.split())


def main():
    """Run the echo server."""
    print("Echo server started!")
    print(f"Server: {EchoServer.name}")
    print(f"Version: {EchoServer.version}")
    print(f"Description: {EchoServer.description}")
    print("\nAvailable tools:")
    for tool_name, tool_def in EchoServer._tools.items():
        print(f"  - {tool_def['name']}: {tool_def['description']}")


if __name__ == "__main__":
    main()
