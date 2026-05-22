"""Configuration management for MCPFlow."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class Config(BaseModel):
    """MCPFlow configuration."""

    server_name: str = Field(default="mcpflow", description="Server name")
    server_version: str = Field(default="0.1.0", description="Server version")
    debug: bool = Field(default=False, description="Enable debug logging")
    log_level: str = Field(default="INFO", description="Logging level")
    enable_tracing: bool = Field(default=False, description="Enable distributed tracing")
    trace_exporter: str = Field(default="otlp", description="Trace exporter type")
    max_message_size: int = Field(default=1024 * 1024, description="Max message size in bytes")
    timeout: float = Field(default=30.0, description="Request timeout in seconds")
    extra: Dict[str, Any] = Field(default_factory=dict, description="Extra configuration")

    class Config:
        """Pydantic config."""

        env_prefix = "MCPFLOW_"
        case_sensitive = False

    @classmethod
    def from_file(cls, path: str) -> "Config":
        """Load configuration from a YAML file.
        
        Args:
            path: Path to configuration file
            
        Returns:
            Config instance
        """
        raise NotImplementedError("Configuration file loading not yet implemented")

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary.
        
        Returns:
            Dictionary representation
        """
        return self.model_dump()
