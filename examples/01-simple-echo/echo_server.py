"""Simple Echo MCP Server - demonstrates @MCPServer and @tool decorators."""

from mcpflow import MCPServerDecorator, tool


@MCPServerDecorator(name="echo-server", version="0.1.0", description="Simple echo server")
class EchoServer:
    """Basic MCP server with two simple tools."""
    
    @tool(description="Echo the input text back")
    def echo(self, text: str) -> dict:
        """Echo: returns the input text as-is."""
        return {"result": text, "length": len(text)}
    
    @tool(description="Reverse the input text")
    def reverse(self, text: str) -> dict:
        """Reverse: returns the reversed text."""
        return {"result": text[::-1], "original": text}
    
    @tool(description="Count words in text")
    def word_count(self, text: str) -> dict:
        """Count words: returns word count and character count."""
        words = text.split()
        return {"words": len(words), "characters": len(text), "text": text}


if __name__ == "__main__":
    # Example usage
    server = EchoServer()
    
    print("=== Echo Server Demo ===\n")
    
    # Test echo tool
    result1 = server.echo("Hello MCPFlow!")
    print(f"echo('Hello MCPFlow!'):")
    print(f"  → {result1}\n")
    
    # Test reverse tool
    result2 = server.reverse("Hello MCPFlow!")
    print(f"reverse('Hello MCPFlow!'):")
    print(f"  → {result2}\n")
    
    # Test word_count tool
    result3 = server.word_count("Hello MCPFlow!")
    print(f"word_count('Hello MCPFlow!'):")
    print(f"  → {result3}\n")
    
    # Show server metadata
    print(f"Server: {server.__class__._server_def.name}")
    print(f"Version: {server.__class__._server_def.version}")
    print(f"Tools registered: {list(server.__class__._tools.keys())}")
