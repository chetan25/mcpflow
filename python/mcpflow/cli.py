"""Command-line interface for MCPFlow."""

import click

from .config import Config
from .server import MCPServer


@click.group()
@click.version_option(version="0.1.0", prog_name="mcpflow")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """MCPFlow - Model Context Protocol flow orchestration framework."""
    pass


@cli.command()
@click.option("--host", default="localhost", help="Server host")
@click.option("--port", default=8000, help="Server port")
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.pass_context
def server(ctx: click.Context, host: str, port: int, debug: bool) -> None:
    """Start MCPFlow server."""
    config = Config(debug=debug, log_level="DEBUG" if debug else "INFO")
    server_instance = MCPServer(config)
    click.echo(f"Starting MCPFlow server on {host}:{port}")
    raise NotImplementedError("Server startup not yet implemented")


@cli.command()
@click.pass_context
def version(ctx: click.Context) -> None:
    """Show version information."""
    click.echo("mcpflow version 0.1.0")


@cli.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """Show server information."""
    config = Config()
    click.echo(f"Server Name: {config.server_name}")
    click.echo(f"Server Version: {config.server_version}")


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
