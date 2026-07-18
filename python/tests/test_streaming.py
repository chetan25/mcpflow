"""Tests for streaming functionality."""

import pytest
import asyncio
from datetime import datetime
from mcpflow.webmcp.streaming import (
    ProgressNotification,
    StreamChunk,
    StreamingToolExecutor,
)


def test_progress_notification_creation():
    """Test ProgressNotification creation and serialization."""
    notification = ProgressNotification(
        tool_name="addToCart",
        task_id="task-123",
        progress=50,
        message="Processing order",
    )

    assert notification.tool_name == "addToCart"
    assert notification.task_id == "task-123"
    assert notification.progress == 50
    assert notification.timestamp is not None

    # Test to_dict
    data = notification.to_dict()
    assert data["type"] == "progress"
    assert data["progress"] == 50
    assert "timestamp" in data


def test_progress_notification_with_timestamp():
    """Test ProgressNotification with explicit timestamp."""
    now = datetime.utcnow()
    notification = ProgressNotification(
        tool_name="search",
        task_id="task-456",
        progress=75,
        message="Searching...",
        timestamp=now,
    )

    data = notification.to_dict()
    assert data["timestamp"] == now.isoformat()


def test_stream_chunk_creation():
    """Test StreamChunk creation."""
    chunk = StreamChunk(
        content="Hello world",
        chunk_type="text",
        is_final=False,
    )

    assert chunk.content == "Hello world"
    assert chunk.chunk_type == "text"
    assert chunk.is_final is False


def test_stream_chunk_final():
    """Test final stream chunk."""
    chunk = StreamChunk(
        content='{"result": "done"}',
        chunk_type="json",
        is_final=True,
    )

    assert chunk.is_final is True
    assert chunk.chunk_type == "json"


# Mock bridge for testing
class MockBridge:
    def __init__(self, call_result=None):
        self.manifests = {}
        self.security = MockSecurity()
        self._call_result = call_result
        self.calls = []

    async def call_tool(self, origin, tool_name, args):
        from mcpflow.webmcp.types import ToolCallResult

        self.calls.append((origin, tool_name, args))
        if self._call_result is not None:
            return self._call_result
        return ToolCallResult(success=True, result={"echo": args})


class MockSecurity:
    def __init__(self):
        self.logs = []

    def log_tool_call(self, origin, tool, success, error=None):
        self.logs.append(
            {"origin": origin, "tool": tool, "success": success, "error": error}
        )


@pytest.mark.asyncio
async def test_streaming_executor_creation():
    """Test StreamingToolExecutor initialization."""
    bridge = MockBridge()
    executor = StreamingToolExecutor(bridge)

    assert executor.bridge is bridge
    assert executor.active_tasks == {}


@pytest.mark.asyncio
async def test_streaming_executor_execute_streaming():
    """Test streaming execution."""
    bridge = MockBridge()
    from mcpflow.webmcp.types import WebMCPTool, WebMCPManifest

    # Create a simple tool
    tool = WebMCPTool(
        name="testTool",
        description="Test tool",
        input_schema={"type": "object", "properties": {}},
        origin="test.example.com",
    )

    manifest = WebMCPManifest(origin="test.example.com", tools=[tool])
    bridge.manifests["test.example.com"] = manifest

    executor = StreamingToolExecutor(bridge)

    # Execute streaming
    chunks = []
    async for chunk in executor.execute_streaming(
        origin="test.example.com",
        tool_name="test_example_com__testTool",
        args={},
        task_id="task-999",
    ):
        chunks.append(chunk)

    # Verify chunks were received
    assert len(chunks) > 0

    # First chunk should have tool info
    assert "testTool" in chunks[0].content

    # Last chunk should be final
    assert chunks[-1].is_final is True

    # The real call should have gone through bridge.call_tool with the
    # *original* (non-namespaced) tool name, and the final chunk should
    # carry the real result bridge.call_tool returned -- not a simulated
    # echo of the raw input/schema.
    assert bridge.calls == [("test.example.com", "testTool", {})]
    assert '"status": "success"' in chunks[-1].content
    assert '"echo"' in chunks[-1].content

    # Verify task was cleaned up
    assert "task-999" not in executor.active_tasks


@pytest.mark.asyncio
async def test_streaming_executor_execute_streaming_call_failure():
    """When bridge.call_tool reports failure, streaming surfaces a real
    error chunk instead of a fabricated success."""
    from mcpflow.webmcp.types import ToolCallResult, WebMCPTool, WebMCPManifest

    bridge = MockBridge(call_result=ToolCallResult(success=False, error="boom"))

    tool = WebMCPTool(
        name="testTool",
        description="Test tool",
        input_schema={"type": "object", "properties": {}},
        origin="test.example.com",
    )
    bridge.manifests["test.example.com"] = WebMCPManifest(
        origin="test.example.com", tools=[tool]
    )

    executor = StreamingToolExecutor(bridge)

    chunks = []
    async for chunk in executor.execute_streaming(
        origin="test.example.com",
        tool_name="testTool",
        args={},
        task_id="task-fail",
    ):
        chunks.append(chunk)

    assert chunks[-1].is_final is True
    assert '"status": "error"' in chunks[-1].content
    assert "boom" in chunks[-1].content


@pytest.mark.asyncio
async def test_streaming_executor_cancel_task():
    """Test task cancellation."""
    bridge = MockBridge()
    executor = StreamingToolExecutor(bridge)

    # Manually add a task
    executor.active_tasks["task-cancel"] = {
        "origin": "test.com",
        "tool": "test",
        "start": datetime.utcnow(),
        "chunks_sent": 0,
    }

    # Cancel it
    assert executor.cancel_task("task-cancel") is True
    assert "task-cancel" not in executor.active_tasks

    # Cancel non-existent task
    assert executor.cancel_task("task-nonexistent") is False


@pytest.mark.asyncio
async def test_streaming_executor_get_task_status():
    """Test getting task status."""
    bridge = MockBridge()
    executor = StreamingToolExecutor(bridge)

    # Add a task
    executor.active_tasks["task-status"] = {
        "origin": "test.com",
        "tool": "testTool",
        "start": datetime.utcnow(),
        "chunks_sent": 5,
    }

    # Get status
    status = executor.get_task_status("task-status")
    assert status is not None
    assert status["task_id"] == "task-status"
    assert status["tool"] == "testTool"
    assert status["chunks_sent"] == 5
    assert status["status"] == "executing"

    # Get non-existent task
    assert executor.get_task_status("task-nonexistent") is None
