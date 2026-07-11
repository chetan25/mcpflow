"""Streaming and progress notification support for WebMCP bridge."""

import asyncio
import logging
from typing import AsyncIterator, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ProgressNotification:
    """Progress update for a long-running tool call."""

    tool_name: str
    task_id: str
    progress: int  # 0-100
    message: str
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert to MCP notification format."""
        ts = self.timestamp.isoformat() if self.timestamp else datetime.utcnow().isoformat()
        return {
            "type": "progress",
            "tool": self.tool_name,
            "task_id": self.task_id,
            "progress": self.progress,
            "message": self.message,
            "timestamp": ts,
        }


@dataclass
class StreamChunk:
    """A chunk of streamed response data."""

    content: str
    chunk_type: str = "text"  # text, json, html, delta
    is_final: bool = False


class StreamingToolExecutor:
    """Manages streaming execution of WebMCP tools with progress tracking."""

    def __init__(self, bridge):
        """
        Initialize streaming executor.

        Args:
            bridge: WebMCPBridge instance
        """
        self.bridge = bridge
        self.active_tasks = {}  # task_id -> execution context

    async def execute_streaming(
        self,
        origin: str,
        tool_name: str,
        args: dict,
        task_id: str,
    ) -> AsyncIterator[StreamChunk]:
        """
        Execute a tool with streaming results and progress updates.

        Args:
            origin: Origin identifier
            tool_name: Tool name (namespaced or original)
            args: Tool arguments
            task_id: Unique task identifier for tracking

        Yields:
            StreamChunk instances as they become available
        """
        logger.info(f"Starting streaming execution: {tool_name} (task: {task_id})")

        # Store task context
        self.active_tasks[task_id] = {
            "origin": origin,
            "tool": tool_name,
            "start": datetime.utcnow(),
            "chunks_sent": 0,
        }

        try:
            # Get tool metadata
            manifest = self.bridge.manifests.get(origin)
            if not manifest:
                yield StreamChunk(
                    content=f'{{"error": "Origin not discovered: {origin}"}}',
                    chunk_type="json",
                    is_final=True,
                )
                return

            # Find tool
            tool = None
            for t in manifest.tools:
                # Try both namespaced and original names
                namespaced_name = f"{origin}__{t.name}".replace(".", "_").replace("-", "_")
                if namespaced_name == tool_name or t.name == tool_name:
                    tool = t
                    break

            if not tool:
                yield StreamChunk(
                    content=f'{{"error": "Tool not found: {tool_name}"}}',
                    chunk_type="json",
                    is_final=True,
                )
                return

            # Send initial response chunk
            yield StreamChunk(
                content=f'{{"tool": "{tool.name}", "description": "{tool.description}", "status": "executing"}}',
                chunk_type="json",
            )

            # Emit progress notifications (simulated for now; Phase 2.2 adds real execution)
            for progress in [25, 50, 75, 100]:
                await asyncio.sleep(0.1)  # Simulate work

                notification = ProgressNotification(
                    tool_name=tool.name,
                    task_id=task_id,
                    progress=progress,
                    message=f"Executing {tool.name}... {progress}% complete",
                )

                yield StreamChunk(
                    content=f'{{"type": "progress", "data": {notification.to_dict()}}}',
                    chunk_type="json",
                )

                self.active_tasks[task_id]["chunks_sent"] += 1

            # Send final result
            result = {
                "tool": tool.name,
                "status": "success",
                "result": {"input": args, "schema": tool.input_schema},
                "chunks_sent": self.active_tasks[task_id]["chunks_sent"],
            }
            yield StreamChunk(
                content=f'{result}',
                chunk_type="json",
                is_final=True,
            )

            self.bridge.security.log_tool_call(origin, tool.name, True)
            logger.info(f"Streaming execution completed: {tool_name} (task: {task_id})")

        except Exception as e:
            logger.error(f"Streaming execution failed: {e}")
            yield StreamChunk(
                content=f'{{"error": "{str(e)}"}}',
                chunk_type="json",
                is_final=True,
            )
            self.bridge.security.log_tool_call(origin, tool_name, False, error=str(e))

        finally:
            # Clean up task
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running task.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if task was cancelled, False if not found
        """
        if task_id in self.active_tasks:
            logger.info(f"Cancelled task: {task_id}")
            del self.active_tasks[task_id]
            return True
        return False

    def get_task_status(self, task_id: str) -> Optional[dict]:
        """
        Get status of a task.

        Args:
            task_id: Task ID

        Returns:
            Task status dict or None if not found
        """
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            elapsed = (datetime.utcnow() - task["start"]).total_seconds()
            return {
                "task_id": task_id,
                "tool": task["tool"],
                "elapsed_seconds": elapsed,
                "chunks_sent": task["chunks_sent"],
                "status": "executing",
            }
        return None

    async def stream_to_mcp_content_blocks(
        self, origin: str, tool_name: str, args: dict, task_id: str
    ) -> list:
        """
        Execute tool and convert stream to MCP content blocks.

        Args:
            origin: Origin identifier
            tool_name: Tool name
            args: Tool arguments
            task_id: Task ID

        Returns:
            List of MCP content blocks
        """
        blocks = []
        async for chunk in self.execute_streaming(origin, tool_name, args, task_id):
            mcp_block = {
                "type": "text",
                "text": chunk.content,
            }
            if chunk.chunk_type == "json":
                mcp_block["type"] = "json"  # MCP's structured content type

            blocks.append(mcp_block)

        return blocks
