"""Tests for result diffing."""

import pytest
from mcpflow.webmcp.result_diffing import (
    ResultDiffer,
    DOMCapture,
    PropertyDelta,
    StateDiff,
    DeltaType,
)


def test_property_delta_creation():
    """Test PropertyDelta creation."""
    delta = PropertyDelta(
        path="$.user.name",
        delta_type=DeltaType.MODIFIED,
        old_value="Alice",
        new_value="Bob",
    )

    assert delta.path == "$.user.name"
    assert delta.delta_type == DeltaType.MODIFIED


def test_property_delta_to_dict():
    """Test PropertyDelta serialization."""
    delta = PropertyDelta(
        path="$.count",
        delta_type=DeltaType.ADDED,
        new_value=42,
    )

    data = delta.to_dict()
    assert data["path"] == "$.count"
    assert data["type"] == "added"
    assert data["new_value"] == 42


def test_property_delta_large_value_truncation():
    """Test that large values are truncated in serialization."""
    large_str = "x" * 2000
    delta = PropertyDelta(
        path="$.html",
        delta_type=DeltaType.MODIFIED,
        old_value="old",
        new_value=large_str,
    )

    data = delta.to_dict()
    assert len(data["new_value"]) < 1100  # Truncated


def test_state_diff_creation():
    """Test StateDiff creation."""
    deltas = [
        PropertyDelta(path="$.items", delta_type=DeltaType.ADDED, new_value=[1, 2, 3]),
        PropertyDelta(path="$.total", delta_type=DeltaType.MODIFIED, old_value=0, new_value=100),
    ]

    diff = StateDiff(
        tool_name="addItem",
        origin="https://shop.com",
        tool_result_summary="item added successfully",
        deltas=deltas,
    )

    assert diff.tool_name == "addItem"
    assert len(diff.deltas) == 2


def test_state_diff_to_dict():
    """Test StateDiff serialization."""
    deltas = [
        PropertyDelta(path="$.count", delta_type=DeltaType.MODIFIED, old_value=5, new_value=6),
    ]

    diff = StateDiff(
        tool_name="increment",
        origin="https://app.com",
        tool_result_summary="incremented",
        deltas=deltas,
    )

    data = diff.to_dict()
    assert data["tool"] == "increment"
    assert len(data["changes"]) == 1


def test_state_diff_get_changed_fields():
    """Test getting changed fields."""
    deltas = [
        PropertyDelta(path="$.a", delta_type=DeltaType.ADDED, new_value=1),
        PropertyDelta(path="$.b", delta_type=DeltaType.UNCHANGED),
        PropertyDelta(path="$.c", delta_type=DeltaType.REMOVED, old_value=3),
    ]

    diff = StateDiff(
        tool_name="test",
        origin="https://test.com",
        tool_result_summary="test",
        deltas=deltas,
    )

    changed = diff.get_changed_fields()
    assert len(changed) == 2
    assert "$.a" in changed
    assert "$.c" in changed


def test_state_diff_has_destructive_changes():
    """Test checking for destructive changes."""
    # Non-destructive (only additions)
    deltas1 = [
        PropertyDelta(path="$.new", delta_type=DeltaType.ADDED, new_value="value"),
    ]

    diff1 = StateDiff(
        tool_name="test",
        origin="https://test.com",
        tool_result_summary="test",
        deltas=deltas1,
    )

    assert diff1.has_destructive_changes() is False

    # Destructive (removes)
    deltas2 = [
        PropertyDelta(path="$.old", delta_type=DeltaType.REMOVED, old_value="value"),
    ]

    diff2 = StateDiff(
        tool_name="test",
        origin="https://test.com",
        tool_result_summary="test",
        deltas=deltas2,
    )

    assert diff2.has_destructive_changes() is True


def test_result_differ_simple_dict_diff():
    """Test simple dict diffing."""
    before = {"name": "Alice", "age": 30}
    after = {"name": "Alice", "age": 31}

    diff = ResultDiffer.diff_dicts(before, after, "updateAge", "https://test.com", "age updated")

    assert len(diff.deltas) == 1
    assert diff.deltas[0].path == "$.age"
    assert diff.deltas[0].delta_type == DeltaType.MODIFIED


def test_result_differ_nested_dict_diff():
    """Test nested dict diffing."""
    before = {
        "user": {"name": "Alice", "email": "alice@example.com"},
        "settings": {"theme": "light"},
    }

    after = {
        "user": {"name": "Alice", "email": "alice@example.com"},
        "settings": {"theme": "dark"},
    }

    diff = ResultDiffer.diff_dicts(before, after, "changeTheme", "https://test.com", "theme changed")

    changed = diff.get_changed_fields()
    assert "$.settings.theme" in changed


def test_result_differ_added_fields():
    """Test detecting added fields."""
    before = {"name": "Bob"}
    after = {"name": "Bob", "age": 25}

    diff = ResultDiffer.diff_dicts(before, after, "addAge", "https://test.com", "age added")

    added = [d for d in diff.deltas if d.delta_type == DeltaType.ADDED]
    assert len(added) == 1
    assert added[0].path == "$.age"


def test_result_differ_removed_fields():
    """Test detecting removed fields."""
    before = {"name": "Bob", "age": 25}
    after = {"name": "Bob"}

    diff = ResultDiffer.diff_dicts(before, after, "removeAge", "https://test.com", "age removed")

    removed = [d for d in diff.deltas if d.delta_type == DeltaType.REMOVED]
    assert len(removed) == 1
    assert removed[0].path == "$.age"


def test_result_differ_summarize_value():
    """Test value summarization."""
    assert ResultDiffer._summarize_value(None) == "null"
    assert ResultDiffer._summarize_value(True) == "true"
    assert ResultDiffer._summarize_value(42) == "42"
    assert ResultDiffer._summarize_value("hello") == '"hello"'
    assert "list" in ResultDiffer._summarize_value([1, 2, 3])
    assert "dict" in ResultDiffer._summarize_value({"a": 1})


def test_result_differ_infer_dom_changes():
    """Test DOM change inference."""
    deltas = [
        PropertyDelta(path="$.html.body.innerHTML", delta_type=DeltaType.MODIFIED, old_value="old", new_value="new"),
    ]

    summary = ResultDiffer._infer_dom_changes(deltas)
    assert summary is not None
    assert "Modified" in summary


def test_dom_capture_basic_state():
    """Test basic DOM state capture."""
    page_json = {
        "url": "https://test.com",
        "title": "Test Page",
        "forms": [{"id": "form1", "fields": 3}],
        "inputs": [{"id": "input1", "type": "text"}],
        "buttons": [{"id": "btn1", "text": "Submit"}],
    }

    state = DOMCapture.capture_state(page_json)

    assert state["url"] == "https://test.com"
    assert state["title"] == "Test Page"
    assert len(state["forms"]) == 1


def test_dom_capture_with_html():
    """Test DOM capture with HTML included."""
    page_json = {
        "url": "https://test.com",
        "html": "<html><body>Test</body></html>",
    }

    state = DOMCapture.capture_state(page_json, include_html=True)

    assert "html" in state
    assert "<body>" in state["html"]


def test_dom_capture_with_cookies():
    """Test DOM capture with cookies."""
    page_json = {
        "url": "https://test.com",
        "cookies": [{"name": "session", "value": "abc123"}],
        "localStorage": {"theme": "dark"},
    }

    state = DOMCapture.capture_state(page_json, include_cookies=True)

    assert "cookies" in state
    assert "localStorage" in state


def test_dom_capture_text_diff():
    """Test simple text diffing."""
    before = "line 1\nline 2\nline 3"
    after = "line 1\nline 2 modified\nline 3"

    diff = DOMCapture.simple_text_diff(before, after)

    assert len(diff) > 0


def test_state_diff_summary():
    """Test summary generation."""
    deltas = [
        PropertyDelta(path="$.count", delta_type=DeltaType.MODIFIED, old_value=0, new_value=1),
    ]

    diff = StateDiff(
        tool_name="increment",
        origin="https://test.com",
        tool_result_summary="count incremented",
        deltas=deltas,
        dom_summary="Updated counter display",
    )

    summary = diff.summary()
    assert "increment" in summary
    assert "count incremented" in summary
    assert "Updated counter" in summary


def test_result_differ_complex_state():
    """Test complex state diffing."""
    before = {
        "cart": {"items": [{"id": 1, "qty": 2}], "total": 100},
        "user": {"name": "Alice", "logged_in": True},
    }

    after = {
        "cart": {"items": [{"id": 1, "qty": 3}, {"id": 2, "qty": 1}], "total": 150},
        "user": {"name": "Alice", "logged_in": True},
    }

    diff = ResultDiffer.diff_dicts(before, after, "addToCart", "https://shop.com", "item added")

    assert len(diff.get_changed_fields()) > 0
    # Modifications are considered destructive (even if not explicitly removing)
    assert diff.has_destructive_changes() is True
