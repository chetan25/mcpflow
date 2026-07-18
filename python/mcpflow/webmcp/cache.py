"""Per-origin WebMCP manifest cache with TTL and content-hash change detection."""

import logging
import time
from typing import Dict, Optional, Tuple

from .types import WebMCPManifest

logger = logging.getLogger(__name__)


class ManifestCache:
    """
    Caches discovered WebMCP manifests per origin.

    A cached manifest is considered fresh until its TTL expires. Even before
    expiry, callers can pass a freshly-computed content hash to force a miss
    when the underlying page has changed (e.g. detected SPA route change).
    """

    def __init__(self, default_ttl_seconds: int = 3600):
        """
        Args:
            default_ttl_seconds: Default cache lifetime, in seconds, applied
                to entries that don't specify their own TTL
        """
        self.default_ttl_seconds = default_ttl_seconds
        self._entries: Dict[str, Tuple[WebMCPManifest, float, int]] = {}
        # origin_slug -> (manifest, cached_at_monotonic, ttl_seconds)

    def get(self, origin_slug: str, content_hash: Optional[str] = None) -> Optional[WebMCPManifest]:
        """
        Get a cached manifest if it's still fresh.

        Args:
            origin_slug: Origin identifier
            content_hash: If given, a mismatch against the cached manifest's
                own content_hash forces a cache miss even within the TTL window

        Returns:
            The cached WebMCPManifest, or None on a miss/expiry
        """
        entry = self._entries.get(origin_slug)
        if not entry:
            return None

        manifest, cached_at, ttl_seconds = entry

        if time.monotonic() - cached_at > ttl_seconds:
            logger.debug(f"Manifest cache expired for {origin_slug}")
            del self._entries[origin_slug]
            return None

        if content_hash is not None and manifest.content_hash != content_hash:
            logger.debug(f"Content hash changed for {origin_slug}; cache invalidated")
            del self._entries[origin_slug]
            return None

        return manifest

    def set(
        self,
        origin_slug: str,
        manifest: WebMCPManifest,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """
        Cache a manifest for an origin.

        Args:
            origin_slug: Origin identifier
            manifest: Manifest to cache
            ttl_seconds: Override the default TTL for this entry
        """
        self._entries[origin_slug] = (
            manifest,
            time.monotonic(),
            ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds,
        )

    def invalidate(self, origin_slug: str) -> bool:
        """
        Force-invalidate a cached manifest (e.g. on a detected SPA route change).

        Args:
            origin_slug: Origin identifier

        Returns:
            True if an entry was removed, False if there was nothing cached
        """
        return self._entries.pop(origin_slug, None) is not None

    def clear(self) -> None:
        """Clear all cached manifests."""
        self._entries.clear()
