"""Tests for distributed tracing and observability."""

import pytest

from mcpflow import Tracer, setup_tracing, get_tracer, trace, trace_tool_call


class TestTracer:
    """Tests for Tracer class."""

    def test_tracer_init_enabled(self):
        """Test initializing a tracer with enabled=True."""
        tracer = Tracer(service_name="test-service", enabled=True)
        assert tracer.service_name == "test-service"
        assert tracer.enabled is True

    def test_tracer_init_disabled(self):
        """Test initializing a tracer with enabled=False."""
        tracer = Tracer(service_name="test-service", enabled=False)
        assert tracer.service_name == "test-service"
        assert tracer.enabled is False

    def test_tracer_default_service_name(self):
        """Test tracer with default service name."""
        tracer = Tracer()
        assert tracer.service_name == "mcpflow"

    def test_start_span_context_manager(self):
        """Test starting a span as context manager."""
        tracer = Tracer(enabled=False)
        with tracer.start_span("test_operation") as span:
            assert span.name == "test_operation"
            assert span.enabled is False

    def test_start_span_with_attributes(self):
        """Test starting span with attributes."""
        tracer = Tracer(enabled=False)
        attrs = {"user_id": "123", "request_id": "abc"}
        with tracer.start_span("operation", attributes=attrs) as span:
            assert span.attributes == attrs

    def test_record_event_when_disabled(self):
        """Test recording event when tracing is disabled."""
        tracer = Tracer(enabled=False)
        # Should not raise
        tracer.record_event("test_event")

    def test_record_event_with_attributes(self):
        """Test recording event with attributes."""
        tracer = Tracer(enabled=True)
        attrs = {"status": "success"}
        # Should not raise
        tracer.record_event("event_name", attributes=attrs)


class TestSpan:
    """Tests for Span class."""

    def test_span_init(self):
        """Test initializing a span."""
        from mcpflow.tracing import Span

        span = Span("operation_name", enabled=False)
        assert span.name == "operation_name"
        assert span.enabled is False
        assert span.attributes == {}

    def test_span_context_manager_enter_exit(self):
        """Test span as context manager."""
        from mcpflow.tracing import Span

        span = Span("test_op", enabled=False)
        with span as s:
            assert s is span
            assert s.name == "test_op"

    def test_span_set_attribute(self):
        """Test setting span attributes."""
        from mcpflow.tracing import Span

        span = Span("test", enabled=True)
        span.set_attribute("key", "value")
        assert span.attributes["key"] == "value"

    def test_span_set_multiple_attributes(self):
        """Test setting multiple span attributes."""
        from mcpflow.tracing import Span

        span = Span("test", enabled=True)
        span.set_attribute("key1", "value1")
        span.set_attribute("key2", 42)
        span.set_attribute("key3", True)

        assert span.attributes["key1"] == "value1"
        assert span.attributes["key2"] == 42
        assert span.attributes["key3"] is True

    def test_span_record_event(self):
        """Test recording event in span."""
        from mcpflow.tracing import Span

        span = Span("test", enabled=False)
        # Should not raise
        span.record_event("event_name")

    def test_span_record_event_with_attributes(self):
        """Test recording event with attributes."""
        from mcpflow.tracing import Span

        span = Span("test", enabled=False)
        attrs = {"status": "success"}
        # Should not raise
        span.record_event("event", attributes=attrs)

    def test_span_exit_with_exception(self):
        """Test span exit with exception."""
        from mcpflow.tracing import Span

        span = Span("test", enabled=False)
        with span:
            pass  # Normal exit

        # Test with exception
        span2 = Span("test", enabled=False)
        try:
            with span2:
                raise ValueError("Test error")
        except ValueError:
            pass  # Expected


class TestTracingFunctions:
    """Tests for tracing module functions."""

    def test_setup_tracing_default(self):
        """Test setting up tracing with defaults."""
        tracer = setup_tracing()
        assert tracer.service_name == "mcpflow"
        assert tracer.enabled is True

    def test_setup_tracing_custom_service_name(self):
        """Test setting up tracing with custom service name."""
        tracer = setup_tracing(service_name="my-service")
        assert tracer.service_name == "my-service"

    def test_setup_tracing_disabled(self):
        """Test setting up tracing disabled."""
        tracer = setup_tracing(enabled=False)
        assert tracer.enabled is False

    def test_get_tracer_returns_same_instance(self):
        """Test that get_tracer returns the same instance."""
        tracer1 = get_tracer()
        tracer2 = get_tracer()
        assert tracer1 is tracer2

    def test_get_tracer_creates_default(self):
        """Test that get_tracer creates a default tracer."""
        tracer = get_tracer()
        assert isinstance(tracer, Tracer)
        assert tracer.service_name == "mcpflow"


class TestTraceDecorator:
    """Tests for @trace decorator."""

    def test_trace_sync_function(self):
        """Test tracing a synchronous function."""

        @trace("test_operation")
        def sync_func():
            return "result"

        result = sync_func()
        assert result == "result"

    def test_trace_async_function(self):
        """Test tracing an asynchronous function."""

        @trace("test_operation")
        async def async_func():
            return "async_result"

        import asyncio

        result = asyncio.run(async_func())
        assert result == "async_result"

    def test_trace_with_attributes(self):
        """Test trace decorator with attributes."""

        @trace("operation", user_id="123", request_id="abc")
        def func_with_attrs():
            return "result"

        result = func_with_attrs()
        assert result == "result"

    def test_trace_function_with_args(self):
        """Test tracing function with arguments."""

        @trace("add_operation")
        def add(a, b):
            return a + b

        result = add(1, 2)
        assert result == 3

    def test_trace_async_function_with_args(self):
        """Test tracing async function with arguments."""

        @trace("async_add")
        async def async_add(a, b):
            return a + b

        import asyncio

        result = asyncio.run(async_add(5, 3))
        assert result == 8


class TestToolCallDecorator:
    """Tests for @trace_tool_call decorator."""

    def test_trace_tool_call_sync(self):
        """Test tracing a tool call in sync function."""

        @trace_tool_call("get_weather", "weather_api")
        def get_weather():
            return {"temperature": 72}

        result = get_weather()
        assert result["temperature"] == 72

    def test_trace_tool_call_async(self):
        """Test tracing a tool call in async function."""

        @trace_tool_call("search", "search_service")
        async def search(query):
            return {"results": [query]}

        import asyncio

        result = asyncio.run(search("python"))
        assert result["results"] == ["python"]

    def test_trace_tool_call_with_exception(self):
        """Test tool call tracing with exception."""

        @trace_tool_call("failing_tool", "bad_service")
        def failing_tool():
            raise RuntimeError("Tool failed")

        with pytest.raises(RuntimeError, match="Tool failed"):
            failing_tool()

    def test_trace_tool_call_async_with_exception(self):
        """Test async tool call tracing with exception."""

        @trace_tool_call("async_failing_tool", "bad_service")
        async def async_failing_tool():
            raise ValueError("Async tool failed")

        import asyncio

        with pytest.raises(ValueError, match="Async tool failed"):
            asyncio.run(async_failing_tool())

    def test_trace_tool_call_with_args(self):
        """Test tool call tracing with arguments."""

        @trace_tool_call("multiply", "math_service")
        def multiply(a, b):
            return a * b

        result = multiply(3, 4)
        assert result == 12
