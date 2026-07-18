"""Tests for the per-origin WebMCP manifest cache."""

from mcpflow.webmcp.cache import ManifestCache
from mcpflow.webmcp.types import WebMCPManifest, WebMCPTool


def _manifest(origin="example.com", content_hash="abc"):
    tool = WebMCPTool(name="t1", description="", input_schema={}, origin=origin)
    return WebMCPManifest(origin=origin, tools=[tool], content_hash=content_hash)


def test_cache_miss_when_empty():
    cache = ManifestCache(default_ttl_seconds=3600)
    assert cache.get("example.com") is None


def test_cache_hit_within_ttl():
    cache = ManifestCache(default_ttl_seconds=3600)
    manifest = _manifest()
    cache.set("example.com", manifest)

    cached = cache.get("example.com")
    assert cached is manifest


def test_cache_expires_after_ttl():
    cache = ManifestCache(default_ttl_seconds=0)
    manifest = _manifest()
    cache.set("example.com", manifest)

    # TTL of 0 means any elapsed time (even ~0s) expires it
    import time

    time.sleep(0.01)
    assert cache.get("example.com") is None


def test_cache_content_hash_mismatch_forces_miss():
    cache = ManifestCache(default_ttl_seconds=3600)
    manifest = _manifest(content_hash="old-hash")
    cache.set("example.com", manifest)

    # Fresh within TTL, but caller supplies a different content hash
    assert cache.get("example.com", content_hash="new-hash") is None


def test_cache_invalidate():
    cache = ManifestCache(default_ttl_seconds=3600)
    cache.set("example.com", _manifest())

    assert cache.invalidate("example.com") is True
    assert cache.get("example.com") is None
    assert cache.invalidate("example.com") is False


def test_cache_per_entry_ttl_override():
    cache = ManifestCache(default_ttl_seconds=3600)
    cache.set("example.com", _manifest(), ttl_seconds=0)

    import time

    time.sleep(0.01)
    assert cache.get("example.com") is None


def test_cache_clear():
    cache = ManifestCache(default_ttl_seconds=3600)
    cache.set("a.com", _manifest("a.com"))
    cache.set("b.com", _manifest("b.com"))

    cache.clear()

    assert cache.get("a.com") is None
    assert cache.get("b.com") is None
