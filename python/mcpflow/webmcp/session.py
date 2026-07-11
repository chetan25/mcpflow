"""SessionProfile management with encrypted persistence."""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class SessionCredential:
    """A credential stored in a session profile."""

    type: str  # "cookie", "header", "localStorage"
    name: str
    value: str
    domain: Optional[str] = None
    path: str = "/"
    expires: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        """Create from dict."""
        return cls(**data)


class EncryptedSessionStore:
    """
    Manages encrypted persistent storage of session profiles.

    Uses OS keychain for master key, Fernet for AES encryption.
    """

    def __init__(self, profile_dir: Optional[Path] = None):
        """
        Initialize session store.

        Args:
            profile_dir: Directory to store encrypted profiles (default: ~/.mcpflow/profiles/)
        """
        if profile_dir is None:
            profile_dir = Path.home() / ".mcpflow" / "profiles"

        self.profile_dir = Path(profile_dir)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._cipher = None
        self._master_key = None

    def _get_or_create_master_key(self) -> bytes:
        """Get or create master encryption key from OS keychain."""
        if self._master_key:
            return self._master_key

        try:
            import keyring
        except ImportError:
            logger.warning("keyring not installed; using file-based key storage (less secure)")
            # Fallback: use a file-based key
            key_file = self.profile_dir / ".master_key"
            if key_file.exists():
                with open(key_file, "rb") as f:
                    self._master_key = f.read()
            else:
                from cryptography.fernet import Fernet

                self._master_key = Fernet.generate_key()
                key_file.write_bytes(self._master_key)
                logger.info(f"Generated master key at {key_file}")
            return self._master_key

        # Try keyring
        service_name = "mcpflow"
        username = "profile_encryption_key"

        try:
            key_b64 = keyring.get_password(service_name, username)
            if key_b64:
                from cryptography.fernet import Fernet

                self._master_key = key_b64.encode()
                return self._master_key
        except Exception as e:
            logger.warning(f"Keyring retrieval failed: {e}")

        # Generate and store new key
        from cryptography.fernet import Fernet

        self._master_key = Fernet.generate_key()
        try:
            keyring.set_password(service_name, username, self._master_key.decode())
            logger.info("Stored master key in system keychain")
        except Exception as e:
            logger.warning(f"Could not store key in keychain: {e}")

        return self._master_key

    def _get_cipher(self):
        """Get Fernet cipher."""
        if not self._cipher:
            from cryptography.fernet import Fernet

            key = self._get_or_create_master_key()
            self._cipher = Fernet(key)

        return self._cipher

    def save_profile(
        self,
        name: str,
        credentials: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """
        Save encrypted session profile.

        Args:
            name: Profile name
            credentials: Credentials dict (cookies, headers, etc.)
            metadata: Optional metadata (origin, description, etc.)

        Returns:
            Path to saved profile file
        """
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            logger.error("cryptography not installed. Run: pip install cryptography")
            raise

        profile_data = {
            "name": name,
            "credentials": credentials,
            "metadata": metadata or {},
            "saved_at": datetime.utcnow().isoformat(),
        }

        # Encrypt
        json_str = json.dumps(profile_data)
        cipher = self._get_cipher()
        encrypted = cipher.encrypt(json_str.encode())

        # Save
        profile_file = self.profile_dir / f"{name}.enc"
        profile_file.write_bytes(encrypted)

        logger.info(f"Saved encrypted profile: {profile_file}")
        return profile_file

    def load_profile(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Load encrypted session profile.

        Args:
            name: Profile name

        Returns:
            Profile data dict or None if not found
        """
        profile_file = self.profile_dir / f"{name}.enc"

        if not profile_file.exists():
            logger.warning(f"Profile not found: {name}")
            return None

        try:
            from cryptography.fernet import Fernet
        except ImportError:
            logger.error("cryptography not installed. Run: pip install cryptography")
            raise

        try:
            encrypted = profile_file.read_bytes()
            cipher = self._get_cipher()
            decrypted = cipher.decrypt(encrypted)
            profile_data = json.loads(decrypted.decode())

            logger.info(f"Loaded encrypted profile: {name}")
            return profile_data

        except Exception as e:
            logger.error(f"Failed to decrypt profile {name}: {e}")
            return None

    def list_profiles(self) -> list:
        """List all available profiles."""
        profiles = []
        for file in self.profile_dir.glob("*.enc"):
            profile_name = file.stem
            profiles.append(profile_name)
        return sorted(profiles)

    def delete_profile(self, name: str) -> bool:
        """
        Delete a profile.

        Args:
            name: Profile name

        Returns:
            True if deleted, False if not found
        """
        profile_file = self.profile_dir / f"{name}.enc"

        if not profile_file.exists():
            return False

        profile_file.unlink()
        logger.info(f"Deleted profile: {name}")
        return True


class SessionProfileManager:
    """
    Manages browser session profiles with persistence and authentication.

    Allows reusing authenticated browser sessions across bridge invocations.
    """

    def __init__(self, store: Optional[EncryptedSessionStore] = None):
        """
        Initialize session profile manager.

        Args:
            store: EncryptedSessionStore instance (created if not provided)
        """
        self.store = store or EncryptedSessionStore()
        self.active_profiles = {}  # name -> browser context

    async def create_profile(
        self,
        name: str,
        browser,
        origin: str,
        headed: bool = False,
    ):
        """
        Create and save a new session profile via headed browser.

        User logs in manually in headed browser; profile is saved encrypted.

        Args:
            name: Profile name
            browser: BrowserController instance
            origin: Origin URL to authenticate for
            headed: If True, show visual browser window
        """
        logger.info(f"Creating new profile: {name} at {origin}")

        try:
            # Create headed browser context
            context = await browser.create_context(
                headless=not headed,
                record_video=False,
            )

            # Navigate to origin
            page = await context.new_page()
            await page.goto(origin, wait_until="networkidle")

            if headed:
                # Show for manual login (wait for user action)
                logger.info(f"⏳ Browser window opened for {name} profile creation")
                logger.info(f"📝 Please log in to {origin} manually")
                logger.info("⏰ Waiting for 5 minutes... (You can close the window when done)")

                # Wait up to 5 minutes for user to complete login
                try:
                    await asyncio.wait_for(
                        page.wait_for_load_state("networkidle", timeout=60000),
                        timeout=300,  # 5 minutes
                    )
                except asyncio.TimeoutError:
                    logger.info("Profile creation timeout (expected if user closed browser)")

            # Extract credentials
            credentials = await self._extract_credentials(page)
            await context.close()

            # Save profile
            metadata = {
                "origin": origin,
                "created_at": datetime.utcnow().isoformat(),
                "headless_capable": True,
            }

            self.store.save_profile(name, credentials, metadata)
            logger.info(f"✓ Profile saved: {name}")

            return True

        except Exception as e:
            logger.error(f"Failed to create profile: {e}")
            return False

    async def load_profile_for_browser(
        self,
        name: str,
        browser,
        origin: str,
    ) -> bool:
        """
        Load a saved profile into a new browser context.

        Args:
            name: Profile name
            browser: BrowserController instance
            origin: Origin URL

        Returns:
            True if profile loaded successfully, False otherwise
        """
        profile_data = self.store.load_profile(name)

        if not profile_data:
            logger.warning(f"Profile not found: {name}")
            return False

        credentials = profile_data.get("credentials", {})

        try:
            # Create context
            context = await browser.create_context(
                headless=True,
                record_video=False,
                # Inject cookies/headers from profile
                extra_http_headers=credentials.get("headers", {}),
            )

            # Inject cookies
            if credentials.get("cookies"):
                await context.add_cookies(credentials["cookies"])

            # Inject localStorage
            page = await context.new_page()
            if credentials.get("localStorage"):
                await page.evaluate(
                    """(items) => {
                        for (const [key, value] of Object.entries(items)) {
                            localStorage.setItem(key, value);
                        }
                    }""",
                    credentials["localStorage"],
                )

            await page.close()

            self.active_profiles[name] = context
            logger.info(f"Loaded profile: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to load profile: {e}")
            return False

    async def _extract_credentials(self, page) -> Dict[str, Any]:
        """Extract credentials from a page."""
        credentials = {}

        try:
            # Get cookies
            cookies = await page.context.cookies()
            credentials["cookies"] = cookies
            logger.info(f"Captured {len(cookies)} cookies")
        except Exception as e:
            logger.warning(f"Could not capture cookies: {e}")

        try:
            # Get localStorage
            local_storage = await page.evaluate("() => JSON.parse(JSON.stringify(localStorage))")
            credentials["localStorage"] = local_storage
            logger.info(f"Captured {len(local_storage)} localStorage items")
        except Exception as e:
            logger.warning(f"Could not capture localStorage: {e}")

        try:
            # Get sessionStorage
            session_storage = await page.evaluate("() => JSON.parse(JSON.stringify(sessionStorage))")
            credentials["sessionStorage"] = session_storage
        except Exception as e:
            logger.warning(f"Could not capture sessionStorage: {e}")

        return credentials

    def get_profile_path(self, name: str) -> Optional[Path]:
        """Get file path of a profile."""
        profile_file = self.store.profile_dir / f"{name}.enc"
        return profile_file if profile_file.exists() else None

    def list_profiles(self) -> list:
        """List available profiles."""
        return self.store.list_profiles()


# Lazy import asyncio to avoid circular dependencies
import asyncio
