"""Tests for multi-origin configuration."""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
import yaml
from mcpflow.webmcp.multi_origin import (
    OriginConfig,
    MultiOriginConfig,
    create_default_multi_origin_config,
)


def test_origin_config_creation():
    """Test OriginConfig creation."""
    config = OriginConfig(
        origin="https://example.com",
        enabled=True,
        description="Test origin",
    )

    assert config.origin == "https://example.com"
    assert config.enabled is True


def test_origin_config_to_dict():
    """Test OriginConfig serialization."""
    config = OriginConfig(
        origin="https://test.com",
        enabled=True,
        session_profile="test_profile",
    )

    data = config.to_dict()
    assert data["origin"] == "https://test.com"
    assert data["session_profile"] == "test_profile"


def test_origin_config_from_dict():
    """Test OriginConfig deserialization."""
    data = {
        "origin": "https://api.example.com",
        "enabled": True,
        "description": "API endpoint",
        "session_profile": "api_session",
    }

    config = OriginConfig.from_dict(data)
    assert config.origin == "https://api.example.com"
    assert config.session_profile == "api_session"


def test_multi_origin_config_creation():
    """Test MultiOriginConfig creation."""
    config = MultiOriginConfig()
    assert config.origins == {}


def test_multi_origin_config_add_origin():
    """Test adding origins."""
    config = MultiOriginConfig()

    origin1 = OriginConfig(origin="https://shop.com", enabled=True)
    origin2 = OriginConfig(origin="https://travel.com", enabled=True)

    config.add_origin(origin1)
    config.add_origin(origin2)

    assert len(config.origins) == 2
    assert "https://shop.com" in config.origins


def test_multi_origin_config_remove_origin():
    """Test removing origins."""
    config = MultiOriginConfig()

    origin = OriginConfig(origin="https://example.com")
    config.add_origin(origin)

    removed = config.remove_origin("https://example.com")
    assert removed is True
    assert len(config.origins) == 0

    # Remove non-existent
    removed = config.remove_origin("https://nonexistent.com")
    assert removed is False


def test_multi_origin_config_get_origin():
    """Test getting origin config."""
    config = MultiOriginConfig()

    origin = OriginConfig(origin="https://test.com", enabled=True)
    config.add_origin(origin)

    retrieved = config.get_origin("https://test.com")
    assert retrieved.origin == "https://test.com"

    # Get non-existent (returns default)
    default = config.get_origin("https://unknown.com")
    assert default.origin == "https://unknown.com"
    assert default.enabled is True


def test_multi_origin_config_is_enabled():
    """Test checking if origin is enabled."""
    config = MultiOriginConfig()

    enabled_origin = OriginConfig(origin="https://enabled.com", enabled=True)
    disabled_origin = OriginConfig(origin="https://disabled.com", enabled=False)

    config.add_origin(enabled_origin)
    config.add_origin(disabled_origin)

    assert config.is_enabled("https://enabled.com") is True
    assert config.is_enabled("https://disabled.com") is False


def test_multi_origin_config_list_origins():
    """Test listing origins."""
    config = MultiOriginConfig()

    config.add_origin(OriginConfig(origin="shop.com", enabled=True))
    config.add_origin(OriginConfig(origin="travel.com", enabled=False))
    config.add_origin(OriginConfig(origin="api.com", enabled=True))

    all_origins = config.list_origins()
    assert len(all_origins) == 3

    enabled_only = config.list_origins(enabled_only=True)
    assert len(enabled_only) == 2
    assert "travel.com" not in enabled_only


def test_multi_origin_config_get_session_profile():
    """Test getting session profile."""
    config = MultiOriginConfig()

    origin = OriginConfig(
        origin="https://example.com", session_profile="my_profile"
    )
    config.add_origin(origin)

    profile = config.get_session_profile("https://example.com")
    assert profile == "my_profile"

    # Non-existent origin
    profile = config.get_session_profile("https://unknown.com")
    assert profile is None


def test_multi_origin_config_requires_headed():
    """Test checking headed browser requirement."""
    config = MultiOriginConfig()

    origin = OriginConfig(
        origin="https://example.com",
        require_headed_for=["payment*", "checkout"],
    )
    config.add_origin(origin)

    assert config.requires_headed("https://example.com", "payment_now") is True
    assert config.requires_headed("https://example.com", "paymentProcess") is True
    assert config.requires_headed("https://example.com", "checkout") is True
    assert config.requires_headed("https://example.com", "addItem") is False


def test_multi_origin_config_roundtrip():
    """Test save and load configuration."""
    with TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.yaml"

        # Create and save
        config = MultiOriginConfig()
        config.add_origin(
            OriginConfig(
                origin="https://shop.com",
                enabled=True,
                session_profile="shop_profile",
            )
        )
        config.add_origin(
            OriginConfig(
                origin="https://travel.com",
                enabled=True,
                require_headed_for=["booking*"],
            )
        )

        yaml_str = config.to_yaml()
        config_file.write_text(yaml_str)

        # Load back
        config2 = MultiOriginConfig(config_file)

        assert len(config2.origins) == 2
        assert config2.get_session_profile("https://shop.com") == "shop_profile"
        assert config2.requires_headed("https://travel.com", "booking_flight") is True


def test_multi_origin_config_to_yaml():
    """Test YAML export."""
    config = MultiOriginConfig()
    config.add_origin(OriginConfig(origin="https://example.com", enabled=True))

    yaml_str = config.to_yaml()

    # Parse to verify valid YAML
    data = yaml.safe_load(yaml_str)
    assert data["version"] == 1
    assert len(data["origins"]) == 1


def test_create_default_multi_origin_config():
    """Test default config template generation."""
    origins = ["https://shop.com", "https://travel.com"]
    template = create_default_multi_origin_config(origins)

    assert "shop.com" in template
    assert "travel.com" in template
    assert "version: 1" in template
    assert "session_profile:" in template

    # Verify it's valid YAML
    data = yaml.safe_load(template)
    assert data["version"] == 1
    assert len(data["origins"]) == 2
