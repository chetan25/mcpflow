"""Tests for session profile management."""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from mcpflow.webmcp.session import (
    SessionCredential,
    EncryptedSessionStore,
    SessionProfileManager,
)


def test_session_credential_creation():
    """Test SessionCredential creation."""
    cred = SessionCredential(
        type="cookie",
        name="session_id",
        value="abc123",
        domain="example.com",
    )

    assert cred.type == "cookie"
    assert cred.name == "session_id"
    assert cred.value == "abc123"


def test_session_credential_to_dict():
    """Test SessionCredential serialization."""
    cred = SessionCredential(
        type="header",
        name="Authorization",
        value="Bearer token",
    )

    data = cred.to_dict()
    assert data["type"] == "header"
    assert data["name"] == "Authorization"


def test_session_credential_from_dict():
    """Test SessionCredential deserialization."""
    data = {
        "type": "cookie",
        "name": "test_cookie",
        "value": "test_value",
        "domain": "test.com",
    }

    cred = SessionCredential.from_dict(data)
    assert cred.type == "cookie"
    assert cred.name == "test_cookie"


def test_encrypted_session_store_creation():
    """Test EncryptedSessionStore creation."""
    with TemporaryDirectory() as tmpdir:
        store = EncryptedSessionStore(profile_dir=Path(tmpdir))

        assert store.profile_dir.exists()
        assert store.profile_dir == Path(tmpdir)


def test_encrypted_session_store_save_profile():
    """Test saving an encrypted profile."""
    with TemporaryDirectory() as tmpdir:
        store = EncryptedSessionStore(profile_dir=Path(tmpdir))

        credentials = {
            "cookies": [
                {"name": "id", "value": "123", "domain": ".example.com"}
            ],
        }
        metadata = {"origin": "https://example.com", "created_by": "test"}

        profile_file = store.save_profile("test_profile", credentials, metadata)

        assert profile_file.exists()
        assert profile_file.name == "test_profile.enc"


def test_encrypted_session_store_load_profile():
    """Test loading an encrypted profile."""
    with TemporaryDirectory() as tmpdir:
        store = EncryptedSessionStore(profile_dir=Path(tmpdir))

        # Save a profile
        original_data = {
            "cookies": [{"name": "session", "value": "xyz"}],
        }
        metadata = {"origin": "https://test.com"}
        store.save_profile("my_profile", original_data, metadata)

        # Load it back
        profile_data = store.load_profile("my_profile")

        assert profile_data is not None
        assert profile_data["name"] == "my_profile"
        assert profile_data["credentials"]["cookies"][0]["name"] == "session"
        assert profile_data["metadata"]["origin"] == "https://test.com"


def test_encrypted_session_store_profile_not_found():
    """Test loading a non-existent profile."""
    with TemporaryDirectory() as tmpdir:
        store = EncryptedSessionStore(profile_dir=Path(tmpdir))

        result = store.load_profile("nonexistent")
        assert result is None


def test_encrypted_session_store_list_profiles():
    """Test listing profiles."""
    with TemporaryDirectory() as tmpdir:
        store = EncryptedSessionStore(profile_dir=Path(tmpdir))

        # Save a few profiles
        store.save_profile("profile1", {})
        store.save_profile("profile2", {})
        store.save_profile("profile3", {})

        profiles = store.list_profiles()
        assert len(profiles) == 3
        assert "profile1" in profiles
        assert "profile2" in profiles
        assert "profile3" in profiles


def test_encrypted_session_store_delete_profile():
    """Test deleting a profile."""
    with TemporaryDirectory() as tmpdir:
        store = EncryptedSessionStore(profile_dir=Path(tmpdir))

        # Save and delete
        store.save_profile("to_delete", {})
        assert "to_delete" in store.list_profiles()

        deleted = store.delete_profile("to_delete")
        assert deleted is True
        assert "to_delete" not in store.list_profiles()

        # Try to delete non-existent
        deleted = store.delete_profile("nonexistent")
        assert deleted is False


def test_session_profile_manager_creation():
    """Test SessionProfileManager creation."""
    with TemporaryDirectory() as tmpdir:
        store = EncryptedSessionStore(profile_dir=Path(tmpdir))
        manager = SessionProfileManager(store=store)

        assert manager.store is store
        assert manager.active_profiles == {}


def test_session_profile_manager_list_profiles():
    """Test listing profiles from manager."""
    with TemporaryDirectory() as tmpdir:
        store = EncryptedSessionStore(profile_dir=Path(tmpdir))
        manager = SessionProfileManager(store=store)

        # Save profiles via store
        store.save_profile("profile_a", {})
        store.save_profile("profile_b", {})

        profiles = manager.list_profiles()
        assert len(profiles) == 2
        assert "profile_a" in profiles


def test_session_profile_manager_get_profile_path():
    """Test getting profile file path."""
    with TemporaryDirectory() as tmpdir:
        store = EncryptedSessionStore(profile_dir=Path(tmpdir))
        manager = SessionProfileManager(store=store)

        store.save_profile("my_profile", {})

        path = manager.get_profile_path("my_profile")
        assert path is not None
        assert path.exists()
        assert path.name == "my_profile.enc"

        # Non-existent profile
        path = manager.get_profile_path("nonexistent")
        assert path is None
