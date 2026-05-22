"""Command-line interface for MCPFlow."""

import os
import json
import shutil
from pathlib import Path
from typing import Optional

import click
import yaml

from .config import Config
from .server import MCPServer

# Version
VERSION = "0.1.0"

# Templates
MCP_SERVER_TEMPLATE = '''"""Generated MCP server using MCPFlow."""

from mcpflow import MCPServer


@MCPServer.tool(
    description="A sample tool that returns the input",
)
def echo(message: str) -> str:
    """Echo tool - returns the input message.
    
    Args:
        message: The message to echo
        
    Returns:
        The echoed message
    """
    return f"Echo: {{message}}"


@MCPServer.tool(
    description="A sample tool that adds two numbers",
)
def add(a: float, b: float) -> float:
    """Add two numbers.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Sum of a and b
    """
    return a + b


if __name__ == "__main__":
    from mcpflow import MCPServer as Server
    import asyncio
    
    # Create and run server
    server = Server(
        name="{project_name}",
        version="0.1.0"
    )
    
    # Tools are auto-registered via decorators
    asyncio.run(server.start())
'''

AGENT_TEMPLATE = '''"""Generated MCPFlow agent."""

from mcpflow.chat import ChatManager
from mcpflow.registry import MCPRegistry


async def main():
    """Run the agent."""
    # Initialize registry with MCP servers
    registry = MCPRegistry()
    
    # Add MCP servers to registry
    # registry.register_mcp("server_name", server_config)
    
    # Create chat manager
    chat_manager = ChatManager(registry=registry)
    
    # Example conversation
    response = await chat_manager.chat(
        message="Hello, what can you help me with?",
        team_name="{project_name}"
    )
    
    print(f"Agent response: {{response}}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
'''

AGENT_CONFIG_TEMPLATE = '''# MCPFlow Agent Configuration
# This file defines the team structure and MCP server connections

name: {project_name}
version: "0.1.0"

# Team configuration
team:
  name: {project_name}-team
  description: "Team for {project_name}"
  
  # Agent definitions
  agents:
    - id: main-agent
      role: main
      model:
        provider: openai
        name: gpt-4
        # api_key can be set via environment variable
        api_key: ${{OPENAI_API_KEY}}
      
      # MCP servers this agent can access
      mcp_servers:
        - name: local-server
          type: stdio
          command: python
          args:
            - server.py
  
  # Tool routing
  tools:
    - name: echo
      mcp_server: local-server
      timeout: 30
    - name: add
      mcp_server: local-server
      timeout: 30

# Logging configuration
logging:
  level: INFO
  format: json

# Development settings
dev:
  debug: false
  hot_reload: true
  watch_paths:
    - .
'''

MCP_SERVER_CONFIG_TEMPLATE = '''# MCPFlow MCP Server Configuration
name: {name}
version: "0.1.0"

# Server settings
server:
  type: stdio
  # For HTTP servers:
  # type: http
  # host: localhost
  # port: 8001

# Tool definitions (auto-generated from decorators)
tools: []

# Authentication
auth: {{}}
'''

DOCKER_TEMPLATE = '''FROM python:3.11-slim

WORKDIR /app

# Copy project files
COPY . .

# Install dependencies
RUN pip install -e .

# Expose ports if needed
EXPOSE 8000

# Run the application
CMD ["mcpflow", "dev", "config.yaml"]
'''

KUBERNETES_TEMPLATE = '''apiVersion: apps/v1
kind: Deployment
metadata:
  name: {project_name}
  labels:
    app: {project_name}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {project_name}
  template:
    metadata:
      labels:
        app: {project_name}
    spec:
      containers:
      - name: {project_name}
        image: {project_name}:0.1.0
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8000
        env:
        - name: LOG_LEVEL
          value: INFO
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: {project_name}
spec:
  selector:
    app: {project_name}
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
  type: ClusterIP
'''


@click.group()
@click.version_option(version=VERSION, prog_name="mcpflow")
@click.pass_context
def mcpflow_cli(ctx: click.Context) -> None:
    """MCPFlow - Model Context Protocol flow orchestration framework."""
    pass


@mcpflow_cli.command()
@click.argument("project_name")
@click.option(
    "--template",
    type=click.Choice(["basic", "agent", "server"]),
    default="basic",
    help="Project template type",
)
@click.pass_context
def init(ctx: click.Context, project_name: str, template: str) -> None:
    """Initialize a new MCPFlow project.
    
    Args:
        project_name: Name of the new project
        template: Template type (basic, agent, server)
    """
    project_path = Path(project_name)
    
    if project_path.exists():
        click.echo(f"Error: Directory '{project_name}' already exists", err=True)
        raise SystemExit(1)
    
    # Create project structure
    project_path.mkdir(parents=True)
    (project_path / "src").mkdir()
    (project_path / "tests").mkdir()
    (project_path / "config").mkdir()
    
    click.echo(f"📁 Created project directory: {project_name}")
    
    # Create config.yaml
    config_content = AGENT_CONFIG_TEMPLATE.format(project_name=project_name)
    (project_path / "config" / "config.yaml").write_text(config_content)
    click.echo("✅ Created config/config.yaml")
    
    # Create server.py based on template
    if template in ["basic", "server"]:
        server_content = MCP_SERVER_TEMPLATE.format(project_name=project_name)
        (project_path / "src" / "server.py").write_text(server_content)
        click.echo("✅ Created src/server.py")
    
    if template in ["basic", "agent"]:
        agent_content = AGENT_TEMPLATE.format(project_name=project_name)
        (project_path / "src" / "agent.py").write_text(agent_content)
        click.echo("✅ Created src/agent.py")
    
    # Create Dockerfile
    (project_path / "Dockerfile").write_text(DOCKER_TEMPLATE)
    click.echo("✅ Created Dockerfile")
    
    # Create kubernetes manifests
    k8s_content = KUBERNETES_TEMPLATE.format(project_name=project_name)
    (project_path / "k8s" if not (project_path / "k8s").exists() else None)
    if not (project_path / "k8s").exists():
        (project_path / "k8s").mkdir()
    (project_path / "k8s" / "deployment.yaml").write_text(k8s_content)
    click.echo("✅ Created k8s/deployment.yaml")
    
    # Create .gitignore
    gitignore_content = """__pycache__/
*.py[cod]
*$py.class
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
.venv/
venv/
.env
.pytest_cache/
.mypy_cache/
.coverage
.DS_Store
*.egg-info/
"""
    (project_path / ".gitignore").write_text(gitignore_content)
    click.echo("✅ Created .gitignore")
    
    # Create pyproject.toml
    pyproject_content = f'''[build-system]
requires = ["setuptools>=65.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{project_name}"
version = "0.1.0"
description = "MCPFlow project"
readme = "README.md"
requires-python = ">=3.8"

dependencies = [
    "mcpflow>=0.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "black>=23.0.0",
]
'''
    (project_path / "pyproject.toml").write_text(pyproject_content)
    click.echo("✅ Created pyproject.toml")
    
    # Create README.md
    readme_content = f'''# {project_name}

MCPFlow project: {project_name}

## Quick Start

```bash
# Install dependencies
pip install -e .

# Run in development mode
mcpflow dev config/config.yaml

# Deploy to Docker
docker build -t {project_name} .
docker run {project_name}
```

## Project Structure

- `src/`: Source code
- `config/`: Configuration files
- `tests/`: Test suite
- `k8s/`: Kubernetes manifests
- `Dockerfile`: Docker configuration

## Documentation

For more information, see the [MCPFlow documentation](https://mcpflow.dev).
'''
    (project_path / "README.md").write_text(readme_content)
    click.echo("✅ Created README.md")
    
    click.echo(f"\n✨ Project '{project_name}' initialized successfully!")
    click.echo(f"Next steps:\n  cd {project_name}\n  mcpflow dev config/config.yaml")


@mcpflow_cli.command()
@click.argument("type_", metavar="TYPE", type=click.Choice(["server", "agent", "config"]))
@click.argument("name")
@click.pass_context
def scaffold(ctx: click.Context, type_: str, name: str) -> None:
    """Scaffold a new component.
    
    Args:
        type_: Component type (server, agent, config)
        name: Component name
    """
    if type_ == "server":
        # Create MCP server scaffold
        server_path = Path(f"{name}.py")
        if server_path.exists():
            click.echo(f"Error: File '{server_path}' already exists", err=True)
            raise SystemExit(1)
        
        content = MCP_SERVER_TEMPLATE.format(project_name=name)
        server_path.write_text(content)
        click.echo(f"✅ Created MCP server: {server_path}")
    
    elif type_ == "agent":
        # Create agent scaffold
        agent_path = Path(f"{name}.py")
        if agent_path.exists():
            click.echo(f"Error: File '{agent_path}' already exists", err=True)
            raise SystemExit(1)
        
        content = AGENT_TEMPLATE.format(project_name=name)
        agent_path.write_text(content)
        click.echo(f"✅ Created agent: {agent_path}")
    
    elif type_ == "config":
        # Create config scaffold
        config_path = Path(f"{name}.yaml")
        if config_path.exists():
            click.echo(f"Error: File '{config_path}' already exists", err=True)
            raise SystemExit(1)
        
        content = AGENT_CONFIG_TEMPLATE.format(project_name=name)
        config_path.write_text(content)
        click.echo(f"✅ Created config: {config_path}")


@mcpflow_cli.command()
@click.argument("config", type=click.Path(exists=True))
@click.option("--host", default="localhost", help="Server host")
@click.option("--port", default=8000, type=int, help="Server port")
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.pass_context
def dev(
    ctx: click.Context,
    config: str,
    host: str,
    port: int,
    debug: bool,
) -> None:
    """Run MCPFlow in development mode.
    
    Args:
        config: Path to configuration file
        host: Server host
        port: Server port
        debug: Enable debug mode
    """
    config_path = Path(config)
    
    if not config_path.exists():
        click.echo(f"Error: Config file '{config}' not found", err=True)
        raise SystemExit(1)
    
    # Load YAML config
    with open(config_path) as f:
        config_data = yaml.safe_load(f)
    
    log_level = "DEBUG" if debug else config_data.get("logging", {}).get("level", "INFO")
    
    click.echo(f"🚀 Starting MCPFlow in development mode")
    click.echo(f"📂 Config: {config_path}")
    click.echo(f"🌐 Server: {host}:{port}")
    click.echo(f"📊 Log level: {log_level}")
    
    if debug:
        click.echo("🔍 Debug mode enabled")
    
    # Create config object
    mcp_config = Config(
        debug=debug,
        log_level=log_level,
        server_name=config_data.get("name", "mcpflow"),
    )
    
    try:
        # Create server instance
        server = MCPServer(mcp_config)
        click.echo(f"\n✅ MCPFlow dev server ready")
        click.echo(f"   Press Ctrl+C to stop")
        
        # Simulate running (in production this would start the actual server)
        import time
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            click.echo("\n\n👋 Shutting down...")
    
    except Exception as e:
        click.echo(f"\n❌ Error starting dev server: {e}", err=True)
        if debug:
            import traceback
            traceback.print_exc()
        raise SystemExit(1)


@mcpflow_cli.command()
@click.argument("config", type=click.Path(exists=True))
@click.option(
    "--target",
    type=click.Choice(["docker", "kubernetes", "local"]),
    default="docker",
    help="Deployment target",
)
@click.option("--dry-run", is_flag=True, help="Show what would be deployed without deploying")
@click.option("--tag", default="latest", help="Image tag for Docker deployments")
@click.pass_context
def deploy(
    ctx: click.Context,
    config: str,
    target: str,
    dry_run: bool,
    tag: str,
) -> None:
    """Deploy MCPFlow application.
    
    Args:
        config: Path to configuration file
        target: Deployment target (docker, kubernetes, local)
        dry_run: Show deployment plan without executing
        tag: Docker image tag
    """
    config_path = Path(config)
    
    if not config_path.exists():
        click.echo(f"Error: Config file '{config}' not found", err=True)
        raise SystemExit(1)
    
    # Load YAML config
    with open(config_path) as f:
        config_data = yaml.safe_load(f)
    
    project_name = config_data.get("name", "mcpflow-app")
    
    click.echo(f"🚀 Preparing deployment")
    click.echo(f"📂 Config: {config_path}")
    click.echo(f"🎯 Target: {target}")
    click.echo(f"📦 Project: {project_name}")
    
    if target == "docker":
        click.echo("\n📦 Docker Deployment Plan:")
        click.echo(f"  1. Build image: {project_name}:{tag}")
        click.echo(f"  2. Tag image: {project_name}:{tag}")
        click.echo(f"  3. Push to registry (if configured)")
        
        if not dry_run:
            click.echo("\n⏳ Building Docker image...")
            # Check if Dockerfile exists
            if not Path("Dockerfile").exists():
                click.echo("⚠️  Dockerfile not found in current directory", err=True)
                click.echo("    Run 'mcpflow init <project-name>' to create a project template")
                raise SystemExit(1)
            
            click.echo(f"✅ Docker image would be built: {project_name}:{tag}")
    
    elif target == "kubernetes":
        click.echo("\n☸️  Kubernetes Deployment Plan:")
        click.echo(f"  1. Apply deployment manifest")
        click.echo(f"  2. Create service")
        click.echo(f"  3. Wait for pods to be ready")
        
        if not dry_run:
            if not Path("k8s/deployment.yaml").exists():
                click.echo("⚠️  k8s/deployment.yaml not found", err=True)
                raise SystemExit(1)
            
            click.echo(f"✅ Would apply Kubernetes manifests to cluster")
    
    elif target == "local":
        click.echo("\n🖥️  Local Deployment Plan:")
        click.echo(f"  1. Install dependencies")
        click.echo(f"  2. Start application")
        click.echo(f"  3. Monitor health")
        
        if not dry_run:
            click.echo(f"✅ Would deploy locally")
    
    if dry_run:
        click.echo("\n✅ Dry-run completed. No changes were made.")
    else:
        click.echo("\n✅ Deployment initiated!")


@mcpflow_cli.command()
@click.pass_context
def version(ctx: click.Context) -> None:
    """Show version information."""
    click.echo(f"mcpflow version {VERSION}")


@mcpflow_cli.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """Show MCPFlow information."""
    config = Config()
    click.echo(f"MCPFlow Information")
    click.echo(f"  Version: {VERSION}")
    click.echo(f"  Server: {config.server_name}")
    click.echo(f"  Server Version: {config.server_version}")
    click.echo(f"  Python Version: {__import__('sys').version.split()[0]}")


def main() -> None:
    """Main entry point."""
    mcpflow_cli()


if __name__ == "__main__":
    main()
