"""Distributed tracing and observability."""

import asyncio
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, Generator, Optional

import structlog
from opentelemetry import trace as otel_trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Global tracer instance
_global_tracer: Optional["Tracer"] = None


def setup_tracing(
    service_name: str = "mcpflow",
    exporter_endpoint: Optional[str] = None,
    enabled: bool = True,
) -> "Tracer":
    """Setup OpenTelemetry tracing with OTLP exporter.
    
    Args:
        service_name: Name of the service
        exporter_endpoint: OTLP exporter endpoint (e.g., "localhost:4317")
        enabled: Whether tracing is enabled
        
    Returns:
        Configured Tracer instance
    """
    global _global_tracer
    
    if enabled and exporter_endpoint:
        try:
            # Create OTLP exporter
            exporter = OTLPSpanExporter(endpoint=exporter_endpoint)
            tracer_provider = TracerProvider()
            tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
            otel_trace.set_tracer_provider(tracer_provider)
        except Exception as e:
            logger.exception("Failed to setup OTLP exporter", error=str(e))
    
    _global_tracer = Tracer(service_name=service_name, enabled=enabled)
    return _global_tracer


def get_tracer() -> "Tracer":
    """Get the global tracer instance.
    
    Returns:
        Global Tracer instance, creating one if needed
    """
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = Tracer()
    return _global_tracer


class Tracer:
    """Distributed tracer for MCPFlow with OpenTelemetry integration."""

    def __init__(self, service_name: str = "mcpflow", enabled: bool = True):
        """Initialize tracer.
        
        Args:
            service_name: Service name for traces
            enabled: Whether tracing is enabled
        """
        self.service_name = service_name
        self.enabled = enabled
        self._otel_tracer = otel_trace.get_tracer(__name__) if enabled else None

    @contextmanager
    def start_span(
        self,
        operation_name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Generator["Span", None, None]:
        """Start a new trace span.
        
        Args:
            operation_name: Name of the operation
            attributes: Span attributes
            
        Yields:
            Span context manager
        """
        span = Span(operation_name, enabled=self.enabled, attributes=attributes)
        with span:
            yield span

    def record_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Record a traced event.
        
        Args:
            name: Event name
            attributes: Event attributes
        """
        if not self.enabled:
            return
        
        event_attrs = attributes or {}
        logger.info("event", event_name=name, **event_attrs)
        
        if self._otel_tracer:
            # Record in OpenTelemetry if available
            try:
                current_span = otel_trace.get_current_span()
                if current_span and current_span.is_recording():
                    current_span.add_event(name, attributes=event_attrs)
            except Exception as e:
                logger.error("Failed to record event", error=str(e))


class Span:
    """Context manager for distributed trace spans."""

    def __init__(
        self,
        name: str,
        enabled: bool = True,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """Initialize span.
        
        Args:
            name: Span name
            enabled: Whether tracing is enabled
            attributes: Initial span attributes
        """
        self.name = name
        self.enabled = enabled
        self.attributes = attributes or {}
        self._otel_span = None
        self._otel_tracer = otel_trace.get_tracer(__name__) if enabled else None

    def __enter__(self) -> "Span":
        """Enter span context."""
        if self.enabled and self._otel_tracer:
            try:
                self._otel_span = self._otel_tracer.start_span(self.name)
                self._otel_span.__enter__()
                
                # Set attributes
                for key, value in self.attributes.items():
                    if isinstance(value, (str, int, float, bool)):
                        self._otel_span.set_attribute(key, value)
            except Exception as e:
                logger.error("Failed to start span", error=str(e))
        
        logger.info("span_start", span=self.name, **self.attributes)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit span context."""
        if self.enabled and self._otel_span:
            try:
                if exc_type is not None:
                    self._otel_span.set_attribute("error", True)
                    self._otel_span.set_attribute("error.type", exc_type.__name__)
                self._otel_span.__exit__(exc_type, exc_val, exc_tb)
            except Exception as e:
                logger.error("Failed to end span", error=str(e))
        
        logger.info("span_end", span=self.name, error=exc_type is not None)

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute.
        
        Args:
            key: Attribute key
            value: Attribute value
        """
        if not self.enabled:
            return
        
        self.attributes[key] = value
        
        if self._otel_span and isinstance(value, (str, int, float, bool)):
            try:
                self._otel_span.set_attribute(key, value)
            except Exception as e:
                logger.error("Failed to set attribute", error=str(e))

    def record_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Record an event within this span.
        
        Args:
            name: Event name
            attributes: Event attributes
        """
        if not self.enabled:
            return
        
        logger.info("span_event", span=self.name, event=name, **attributes or {})
        
        if self._otel_span:
            try:
                self._otel_span.add_event(name, attributes=attributes or {})
            except Exception as e:
                logger.error("Failed to record span event", error=str(e))


def trace(operation_name: str, **default_attributes: Any) -> Callable:
    """Decorator to trace function execution.
    
    Args:
        operation_name: Name of the operation for the span
        **default_attributes: Default attributes to set on the span
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.start_span(operation_name, attributes=default_attributes):
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.start_span(operation_name, attributes=default_attributes):
                return func(*args, **kwargs)
        
        # Return appropriate wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def trace_tool_call(tool_name: str, mcp_name: str) -> Callable:
    """Decorator to trace tool calls.
    
    Args:
        tool_name: Name of the tool being called
        mcp_name: Name of the MCP server
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.start_span(
                "tool_call",
                attributes={
                    "tool_name": tool_name,
                    "mcp_name": mcp_name,
                },
            ) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("success", True)
                    return result
                except Exception as e:
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", str(e))
                    raise
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.start_span(
                "tool_call",
                attributes={
                    "tool_name": tool_name,
                    "mcp_name": mcp_name,
                },
            ) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("success", True)
                    return result
                except Exception as e:
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", str(e))
                    raise
        
        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
