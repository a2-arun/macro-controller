"""Credential storage.

!! PHASE 1 -- THIS VAULT IS NOT SECURE. !!

It is kept working, on correct paths, with an origin-canonicalised lookup, so
the application functions end to end. Its confidentiality guarantee is still
zero, because the KDF input is a constant committed to the repository:

    DEFAULT_KEY_DERIVATION_PASSWORD = b"macro_controller_key"

An attacker does not guess that password, they read it. PBKDF2 with 100,000
iterations over a known input is not a cost barrier -- it is a fixed,
one-time derivation. Anyone holding a copy of the data directory and the
public repository decrypts the vault in a single call. The salt being random
does not help: it is stored next to the ciphertext, and salts defend against
precomputation, not against a known password.

Phase 2 replaces this wholesale with Argon2id over a user passphrase that is
never written to disk, envelope encryption, and AES-256-GCM binding the
canonical origin as associated data -- so a record for one origin cannot be
decrypted for another. See docs/ROADMAP.md Part 3.

Until then: do not store a credential here that you would mind disclosing.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
from typing import Dict, Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from automation.web_automation import canonical_origin
from config.constants import credentials_file, salt_file
from config.settings import DEFAULT_KEY_DERIVATION_PASSWORD, PBKDF2_ITERATIONS

logger = logging.getLogger(__name__)


class CredentialManager:
    def __init__(self) -> None:
        self.key = self._get_or_create_key()
        self.fernet = Fernet(self.key)
        self.credentials: Dict[str, Dict[str, str]] = self._load_credentials()

    # ------------------------------------------------------------------ key mgmt

    def _get_or_create_key(self) -> bytes:
        path = salt_file()
        if not path.exists():
            # 16 bytes is the PBKDF2 minimum worth using; Phase 2 moves to 32.
            path.write_bytes(os.urandom(16))
            logger.info("generated a new salt at %s", path)

        salt = path.read_bytes()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
        )
        return base64.urlsafe_b64encode(kdf.derive(DEFAULT_KEY_DERIVATION_PASSWORD))

    # ------------------------------------------------------------------ storage

    def _load_credentials(self) -> Dict[str, Dict[str, str]]:
        path = credentials_file()
        if not path.exists():
            return {}

        try:
            decrypted = self.fernet.decrypt(path.read_bytes())
            loaded = json.loads(decrypted)
        except InvalidToken:
            # Wrong key or tampered file. The original swallowed this and
            # returned {}, silently discarding the vault on the next save.
            logger.error("credential vault failed authentication -- not overwriting")
            raise
        except (OSError, json.JSONDecodeError):
            logger.exception("could not read credential vault")
            return {}

        return loaded if isinstance(loaded, dict) else {}

    def save_credentials(self) -> None:
        """Encrypt and write atomically, so an interrupted write cannot
        destroy the vault."""
        path = credentials_file()
        payload = self.fernet.encrypt(json.dumps(self.credentials).encode())

        with tempfile.NamedTemporaryFile(
            "wb", dir=path.parent, delete=False, suffix=".tmp"
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temp_name = handle.name

        os.replace(temp_name, path)

        # Best-effort: restrict to the owner. Real protection arrives in Phase 2.
        try:
            os.chmod(path, 0o600)
        except OSError:
            logger.debug("could not restrict vault permissions", exc_info=True)

    # ------------------------------------------------------------------- records

    def add_credentials(self, url: str, username: str, password: str) -> None:
        """Store a credential keyed by canonical origin.

        Keying by origin rather than the raw URL means a stored login is found
        regardless of path or query string, and -- more importantly -- that
        the key is the same value Phase 2 will bind as AEAD associated data.
        """
        origin = canonical_origin(url)
        self.credentials[origin] = {"username": username, "password": password}
        self.save_credentials()
        logger.info("stored credentials for %s", origin)

    def get_credentials(self, url: str) -> Optional[Dict[str, str]]:
        return self.credentials.get(canonical_origin(url))

    def remove_credentials(self, url: str) -> bool:
        origin = canonical_origin(url)
        if origin in self.credentials:
            del self.credentials[origin]
            self.save_credentials()
            logger.info("removed credentials for %s", origin)
            return True
        return False

    def known_origins(self) -> list[str]:
        return sorted(self.credentials)
