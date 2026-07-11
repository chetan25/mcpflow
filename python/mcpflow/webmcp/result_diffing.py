"""Result diffing to show DOM and state changes from tool invocation."""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import difflib

logger = logging.getLogger(__name__)


class DeltaType(str, Enum):
    """Type of change."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class PropertyDelta:
    """Change to a single property."""

    path: str  # JSONPath to property: "$.html.body", "$.user.name"
    delta_type: DeltaType
    old_value: Any = None
    new_value: Any = None

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "path": self.path,
            "type": self.delta_type.value,
            "old_value": self._serialize_value(self.old_value),
            "new_value": self._serialize_value(self.new_value),
        }

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """Serialize value (truncate large values)."""
        if isinstance(value, str) and len(value) > 1000:
            return value[:1000] + "... [truncated]"
        if isinstance(value, (dict, list)) and len(str(value)) > 1000:
            return f"{type(value).__name__} [too large]"
        return value


@dataclass
class StateDiff:
    """Complete state diff for before/after tool invocation."""

    tool_name: str
    origin: str
    tool_result_summary: str  # What the tool returned
    deltas: List[PropertyDelta]
    dom_summary: Optional[str] = None  # Human summary of visible changes
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "tool": self.tool_name,
            "origin": self.origin,
            "result_summary": self.tool_result_summary,
            "changes": [d.to_dict() for d in self.deltas],
            "dom_summary": self.dom_summary,
            "error": self.error,
        }

    def get_changed_fields(self) -> List[str]:
        """Get list of fields that changed."""
        return [d.path for d in self.deltas if d.delta_type != DeltaType.UNCHANGED]

    def has_destructive_changes(self) -> bool:
        """Check if diff contains removals/modifications (potentially destructive)."""
        for delta in self.deltas:
            if delta.delta_type in (DeltaType.REMOVED, DeltaType.MODIFIED):
                return True
        return False

    def summary(self) -> str:
        """Human-readable summary."""
        changed = len(self.get_changed_fields())
        added = len([d for d in self.deltas if d.delta_type == DeltaType.ADDED])
        removed = len([d for d in self.deltas if d.delta_type == DeltaType.REMOVED])

        parts = [
            f"Tool: {self.tool_name}",
            f"Result: {self.tool_result_summary}",
        ]

        if changed > 0:
            parts.append(f"State changes: {added} added, {removed} removed, {changed-added-removed} modified")

        if self.dom_summary:
            parts.append(f"DOM: {self.dom_summary}")

        if self.error:
            parts.append(f"Error: {self.error}")

        return " | ".join(parts)


class ResultDiffer:
    """Calculate diffs between tool invocations."""

    @staticmethod
    def diff_dicts(
        before: Dict[str, Any],
        after: Dict[str, Any],
        tool_name: str,
        origin: str,
        tool_result: Any,
    ) -> StateDiff:
        """
        Compare before/after state dicts.

        Args:
            before: State before tool invocation (as dict)
            after: State after tool invocation (as dict)
            tool_name: Name of tool invoked
            origin: Origin URL
            tool_result: What the tool returned

        Returns:
            StateDiff with deltas
        """
        deltas = ResultDiffer._compute_deltas(before, after)

        # Make summary of tool result
        result_summary = ResultDiffer._summarize_value(tool_result)

        return StateDiff(
            tool_name=tool_name,
            origin=origin,
            tool_result_summary=result_summary,
            deltas=deltas,
            dom_summary=ResultDiffer._infer_dom_changes(deltas),
        )

    @staticmethod
    def _compute_deltas(before: Dict, after: Dict, prefix: str = "$") -> List[PropertyDelta]:
        """Recursively compute deltas between two dicts."""
        deltas: List[PropertyDelta] = []

        # Check all keys in before
        for key in before:
            path = f"{prefix}.{key}"
            if key not in after:
                deltas.append(
                    PropertyDelta(
                        path=path,
                        delta_type=DeltaType.REMOVED,
                        old_value=before[key],
                    )
                )
            elif before[key] == after[key]:
                pass  # No change
            elif isinstance(before[key], dict) and isinstance(after[key], dict):
                # Recurse
                deltas.extend(
                    ResultDiffer._compute_deltas(before[key], after[key], path)
                )
            else:
                deltas.append(
                    PropertyDelta(
                        path=path,
                        delta_type=DeltaType.MODIFIED,
                        old_value=before[key],
                        new_value=after[key],
                    )
                )

        # Check keys in after that weren't in before
        for key in after:
            if key not in before:
                path = f"{prefix}.{key}"
                deltas.append(
                    PropertyDelta(
                        path=path,
                        delta_type=DeltaType.ADDED,
                        new_value=after[key],
                    )
                )

        return deltas

    @staticmethod
    def _summarize_value(value: Any) -> str:
        """Create a brief summary of a value."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            if len(value) > 50:
                return f'"{value[:50]}..."'
            return f'"{value}"'
        if isinstance(value, list):
            return f"list({len(value)} items)"
        if isinstance(value, dict):
            return f"dict({len(value)} keys)"
        return str(type(value).__name__)

    @staticmethod
    def _infer_dom_changes(deltas: List[PropertyDelta]) -> Optional[str]:
        """Infer human-readable DOM changes from deltas."""
        if not deltas:
            return None

        changes = []

        for delta in deltas:
            if "html" in delta.path.lower() or "dom" in delta.path.lower():
                if delta.delta_type == DeltaType.ADDED:
                    changes.append(f"Added {delta.path}")
                elif delta.delta_type == DeltaType.REMOVED:
                    changes.append(f"Removed {delta.path}")
                elif delta.delta_type == DeltaType.MODIFIED:
                    changes.append(f"Modified {delta.path}")

        if changes:
            return "; ".join(changes[:3])
        return None


class DOMCapture:
    """Capture and serialize DOM state for diffing."""

    @staticmethod
    def capture_state(
        page_json: Dict[str, Any],
        include_html: bool = False,
        include_cookies: bool = False,
    ) -> Dict[str, Any]:
        """
        Capture page state for diffing.

        Args:
            page_json: JSON representation of page (e.g., from browser.capture_json())
            include_html: Include full HTML
            include_cookies: Include cookies/session storage

        Returns:
            State dict suitable for diffing
        """
        state = {
            "url": page_json.get("url"),
            "title": page_json.get("title"),
            "forms": page_json.get("forms", []),
            "inputs": page_json.get("inputs", []),
            "buttons": page_json.get("buttons", []),
        }

        if include_html:
            state["html"] = page_json.get("html", "")[:5000]

        if include_cookies:
            state["cookies"] = page_json.get("cookies", [])
            state["localStorage"] = page_json.get("localStorage", {})

        return state

    @staticmethod
    def simple_text_diff(before_text: str, after_text: str) -> List[str]:
        """
        Create a simple text diff (for debugging).

        Returns list of additions/removals.
        """
        before_lines = before_text.split("\n")
        after_lines = after_text.split("\n")

        differ = difflib.unified_diff(before_lines, after_lines, lineterm="")
        return list(differ)[:20]  # Limit to 20 lines
