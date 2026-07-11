"""Tests for policy enforcement."""

import pytest
from tempfile import TemporaryDirectory
from pathlib import Path
import yaml
from mcpflow.webmcp.policy import (
    ToolPolicy,
    PolicyFile,
    PolicyEnforcer,
    create_default_policy_yaml,
)


def test_tool_policy_creation():
    """Test ToolPolicy creation."""
    policy = ToolPolicy(
        name_pattern="add*",
        allowed=True,
        destructive=False,
        max_calls_per_session=100,
    )

    assert policy.name_pattern == "add*"
    assert policy.allowed is True
    assert policy.max_calls_per_session == 100


def test_tool_policy_with_confirmation():
    """Test ToolPolicy with confirmation requirement."""
    policy = ToolPolicy(
        name_pattern="delete*",
        allowed=True,
        destructive=True,
        requires_confirmation=True,
    )

    assert policy.requires_confirmation is True
    assert policy.destructive is True


def test_policy_file_creation_empty():
    """Test PolicyFile creation with no file."""
    pf = PolicyFile()
    assert pf.policies == []
    assert pf.origin is None


def test_policy_file_roundtrip():
    """Test PolicyFile save and load."""
    with TemporaryDirectory() as tmpdir:
        policy_file = Path(tmpdir) / "policy.yaml"

        # Create policies
        pf = PolicyFile()
        pf.origin = "https://example.com"
        pf.policies = [
            ToolPolicy(name_pattern="add*", allowed=True),
            ToolPolicy(name_pattern="delete*", allowed=True, destructive=True),
            ToolPolicy(name_pattern="*", allowed=False),
        ]

        # Save to YAML
        yaml_str = pf.to_yaml()
        policy_file.write_text(yaml_str)

        # Load back
        pf2 = PolicyFile(policy_file)

        assert pf2.origin == "https://example.com"
        assert len(pf2.policies) == 3
        assert pf2.policies[0].name_pattern == "add*"


def test_policy_enforcer_is_allowed():
    """Test policy enforcement for allowed tools."""
    pf = PolicyFile()
    pf.policies = [
        ToolPolicy(name_pattern="add*", allowed=True),
        ToolPolicy(name_pattern="delete*", allowed=True),
        ToolPolicy(name_pattern="*", allowed=False),  # Default deny
    ]

    enforcer = PolicyEnforcer(pf)

    assert enforcer.is_allowed("addToCart") is True
    assert enforcer.is_allowed("addItem") is True
    assert enforcer.is_allowed("delete") is True
    assert enforcer.is_allowed("unknown_tool") is False


def test_policy_enforcer_is_destructive():
    """Test detecting destructive operations."""
    pf = PolicyFile()
    pf.policies = [
        ToolPolicy(name_pattern="add*", destructive=False),
        ToolPolicy(name_pattern="delete*", destructive=True),
    ]

    enforcer = PolicyEnforcer(pf)

    assert enforcer.is_destructive("addToCart") is False
    assert enforcer.is_destructive("deleteUser") is True


def test_policy_enforcer_requires_confirmation():
    """Test confirmation requirements."""
    pf = PolicyFile()
    pf.policies = [
        ToolPolicy(name_pattern="delete*", requires_confirmation=True),
        ToolPolicy(name_pattern="pay*", requires_confirmation=True),
        ToolPolicy(name_pattern="*", requires_confirmation=False),
    ]

    enforcer = PolicyEnforcer(pf)

    assert enforcer.requires_confirmation("deleteUser") is True
    assert enforcer.requires_confirmation("payNow") is True
    assert enforcer.requires_confirmation("addItem") is False


def test_policy_enforcer_can_call():
    """Test comprehensive call validation."""
    pf = PolicyFile()
    pf.policies = [
        ToolPolicy(name_pattern="add*", allowed=True),
        ToolPolicy(name_pattern="delete*", allowed=False),
    ]

    enforcer = PolicyEnforcer(pf)

    allowed, reason = enforcer.can_call("addItem")
    assert allowed is True
    assert reason is None

    allowed, reason = enforcer.can_call("deleteUser")
    assert allowed is False
    assert reason and "not allowed" in reason


def test_policy_enforcer_call_limit():
    """Test call rate limiting."""
    pf = PolicyFile()
    pf.policies = [
        ToolPolicy(name_pattern="post*", allowed=True, max_calls_per_session=3),
    ]

    enforcer = PolicyEnforcer(pf)

    # Record calls
    enforcer.record_call("postComment")
    enforcer.record_call("postComment")
    enforcer.record_call("postComment")

    # Should exceed limit now
    allowed, reason = enforcer.can_call("postComment")
    assert allowed is False
    assert reason and "call limit" in reason.lower()


def test_policy_enforcer_record_call():
    """Test call recording."""
    pf = PolicyFile()
    pf.policies = [
        ToolPolicy(name_pattern="*", allowed=True),
    ]

    enforcer = PolicyEnforcer(pf)

    enforcer.record_call("test_tool")
    enforcer.record_call("test_tool")
    assert enforcer.call_counts["test_tool"] == 2

    enforcer.record_call("another_tool")
    assert enforcer.call_counts["another_tool"] == 1


def test_policy_enforcer_get_policy_for_tool():
    """Test retrieving policy for a specific tool."""
    pf = PolicyFile()
    policy1 = ToolPolicy(name_pattern="add*", destructive=False)
    policy2 = ToolPolicy(name_pattern="*", destructive=False)

    pf.policies = [policy1, policy2]

    enforcer = PolicyEnforcer(pf)

    # Should match first pattern
    found = enforcer.get_policy_for_tool("addItem")
    assert found is policy1

    # Should match wildcard
    found = enforcer.get_policy_for_tool("unknown")
    assert found is policy2


def test_create_default_policy_yaml():
    """Test default policy template generation."""
    yaml_str = create_default_policy_yaml("https://example.com")

    assert "example.com" in yaml_str
    assert "version: 1" in yaml_str
    assert "list*" in yaml_str
    assert "delete*" in yaml_str

    # Parse to verify valid YAML
    data = yaml.safe_load(yaml_str)
    assert data["origin"] == "https://example.com"
    assert len(data["policies"]) > 0


def test_policy_glob_patterns():
    """Test glob pattern matching."""
    pf = PolicyFile()
    pf.policies = [
        ToolPolicy(name_pattern="add*", allowed=True),
        ToolPolicy(name_pattern="list_*", allowed=True),
        ToolPolicy(name_pattern="*_delete", allowed=False),
    ]

    enforcer = PolicyEnforcer(pf)

    # add* matches
    assert enforcer.is_allowed("addToCart") is True
    assert enforcer.is_allowed("addItem") is True
    assert enforcer.is_allowed("add") is True

    # list_* matches
    assert enforcer.is_allowed("list_users") is True
    assert enforcer.is_allowed("list_items") is True
    assert enforcer.is_allowed("listAll") is False  # underscore required

    # *_delete matches
    assert enforcer.is_allowed("user_delete") is False
    assert enforcer.is_allowed("item_delete") is False

    # No match - denied by explicit policy
    assert enforcer.is_allowed("unknown") is False
