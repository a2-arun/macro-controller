"""Credential storage: the Origin-Bound Macro Vault (OBMV).

Phase 1's vault derived its key from a constant committed to the repository
(DEFAULT_KEY_DERIVATION_PASSWORD) -- an attacker didn't guess that password,
they read it. This replaces it wholesale:

- Argon2id over a user passphrase that is never written to disk (2.1)
  derives a key-encryption key (KEK).
- Envelope encryption: the KEK wraps a random per-record data-encryption
  key (DEK), so changing the passphrase (rekey()) re-wraps every DEK
  without re-encrypting the secrets themselves (2.2).
- Each record is sealed with AES-256-GCM under its own DEK with the
  canonical origin bound as Additional Authenticated Data (2.3). A record
  for https://github.com cannot be decrypted at all when presented with any
  other origin -- origin confusion degrades to a decryption failure, not a
  policy branch that can be bypassed or patched around.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
from typing import Dict, Optional

import argon2.low_level
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from automation.web_automation import canonical_origin
from config.constants import vault_file
from config.settings import (
    ARGON2_HASH_LEN,
    ARGON2_MEMORY_COST_KIB,
    ARGON2_PARALLELISM,
    ARGON2_SALT_LEN,
    ARGON2_TIME_COST,
)

logger = logging.getLogger(__name__)

VAULT_FORMAT_VERSION = 2

# Fixed AAD for the canary -- it isn't origin-scoped, it just proves the
# derived KEK is the right one before touching any real record.
_CANARY_AAD = b"obmv-vault-canary-v1"
_CANARY_PLAINTEXT = b"obmv-vault-canary-v1"


class VaultLocked(RuntimeError):
    """A write was attempted on a vault opened without a passphrase."""


class WrongPassphrase(RuntimeError):
    """The supplied passphrase does not open this vault."""


class VaultTampered(RuntimeError):
    """The vault file is malformed, corrupted, or failed authentication."""


# ---------------------------------------------------------------- primitives
# Free functions, not methods: they carry no state, and keeping them
# module-level lets tests exercise the AEAD layer directly (e.g. proving an
# origin mismatch fails at the InvalidTag check, not at a dict lookup).


def _derive_kek(passphrase: str, salt: bytes, kdf_params: dict) -> bytes:
    return argon2.low_level.hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=kdf_params["time_cost"],
        memory_cost=kdf_params["memory_cost_kib"],
        parallelism=kdf_params["parallelism"],
        hash_len=ARGON2_HASH_LEN,
        type=argon2.low_level.Type.ID,
    )


def _seal(key: bytes, aad: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
    """AES-256-GCM encrypt. Returns (nonce, ciphertext_with_tag)."""
    nonce = os.urandom(12)
    return nonce, AESGCM(key).encrypt(nonce, plaintext, aad)


def _open(key: bytes, aad: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    """AES-256-GCM decrypt. Raises InvalidTag on any key/AAD/ciphertext
    mismatch -- wrong passphrase, wrong origin, and bit-flip tampering are
    indistinguishable at this layer, by construction."""
    return AESGCM(key).decrypt(nonce, ciphertext, aad)


def _wrap_dek(kek: bytes, origin: str, dek: bytes) -> tuple[bytes, bytes]:
    return _seal(kek, origin.encode("utf-8"), dek)


def _unwrap_dek(kek: bytes, origin: str, record: dict) -> bytes:
    return _open(
        kek,
        origin.encode("utf-8"),
        base64.b64decode(record["wrap_nonce"]),
        base64.b64decode(record["wrapped_dek"]),
    )


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


# --------------------------------------------------------------------- vault


class CredentialManager:
    def __init__(self, passphrase: Optional[str]) -> None:
        self.credentials: Dict[str, Dict[str, str]] = {}
        self._records: Dict[str, dict] = {}
        self._kek: Optional[bytes] = None
        self._salt: Optional[bytes] = None
        self._kdf_params: Optional[dict] = None
        self._locked = passphrase is None

        if self._locked:
            logger.warning("vault opened locked (no passphrase) -- credential features disabled")
            return

        self._open_vault(passphrase)

    @staticmethod
    def vault_exists() -> bool:
        return vault_file().exists()

    @property
    def locked(self) -> bool:
        return self._locked

    # ------------------------------------------------------------------ open

    def _open_vault(self, passphrase: str) -> None:
        path = vault_file()

        if not path.exists():
            self._salt = os.urandom(ARGON2_SALT_LEN)
            self._kdf_params = {
                "time_cost": ARGON2_TIME_COST,
                "memory_cost_kib": ARGON2_MEMORY_COST_KIB,
                "parallelism": ARGON2_PARALLELISM,
            }
            self._kek = _derive_kek(passphrase, self._salt, self._kdf_params)
            self._records = {}
            self._write_vault()
            logger.info("created a new vault at %s", path)
            return

        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            kdf = doc["kdf"]
            self._salt = base64.b64decode(kdf["salt"])
            self._kdf_params = {
                "time_cost": kdf["time_cost"],
                "memory_cost_kib": kdf["memory_cost_kib"],
                "parallelism": kdf["parallelism"],
            }
            canary_nonce = base64.b64decode(doc["canary"]["nonce"])
            canary_ciphertext = base64.b64decode(doc["canary"]["ciphertext"])
            records = doc["records"]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise VaultTampered(f"vault file is malformed: {exc}") from exc

        kek = _derive_kek(passphrase, self._salt, self._kdf_params)

        try:
            _open(kek, _CANARY_AAD, canary_nonce, canary_ciphertext)
        except InvalidTag as exc:
            raise WrongPassphrase("the passphrase does not open this vault") from exc

        credentials: Dict[str, Dict[str, str]] = {}
        for origin, record in records.items():
            try:
                dek = _unwrap_dek(kek, origin, record)
                plaintext = _open(
                    dek,
                    origin.encode("utf-8"),
                    base64.b64decode(record["nonce"]),
                    base64.b64decode(record["ciphertext"]),
                )
                credentials[origin] = json.loads(plaintext)
            except (InvalidTag, KeyError, ValueError, json.JSONDecodeError) as exc:
                raise VaultTampered(f"record for {origin!r} failed verification: {exc}") from exc

        self._kek = kek
        self._records = records
        self.credentials = credentials
        logger.info("unlocked vault at %s (%d records)", path, len(credentials))

    # ---------------------------------------------------------------- write

    def _write_vault(self) -> None:
        doc = {
            "version": VAULT_FORMAT_VERSION,
            "kdf": {
                "type": "argon2id",
                "time_cost": self._kdf_params["time_cost"],
                "memory_cost_kib": self._kdf_params["memory_cost_kib"],
                "parallelism": self._kdf_params["parallelism"],
                "salt": _b64(self._salt),
            },
            "canary": self._seal_canary(),
            "records": self._records,
        }

        path = vault_file()
        with tempfile.NamedTemporaryFile(
            "w", dir=path.parent, delete=False, suffix=".tmp", encoding="utf-8"
        ) as handle:
            json.dump(doc, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
            temp_name = handle.name

        os.replace(temp_name, path)

        try:
            os.chmod(path, 0o600)
        except OSError:
            logger.debug("could not restrict vault permissions", exc_info=True)

    def _seal_canary(self) -> dict:
        nonce, ciphertext = _seal(self._kek, _CANARY_AAD, _CANARY_PLAINTEXT)
        return {"nonce": _b64(nonce), "ciphertext": _b64(ciphertext)}

    # ------------------------------------------------------------------- records

    def add_credentials(self, url: str, username: str, password: str) -> None:
        if self._locked:
            raise VaultLocked("no passphrase was entered this session")

        origin = canonical_origin(url)
        dek = os.urandom(32)
        wrap_nonce, wrapped_dek = _wrap_dek(self._kek, origin, dek)
        plaintext = json.dumps({"username": username, "password": password}).encode()
        nonce, ciphertext = _seal(dek, origin.encode("utf-8"), plaintext)

        self._records[origin] = {
            "wrap_nonce": _b64(wrap_nonce),
            "wrapped_dek": _b64(wrapped_dek),
            "nonce": _b64(nonce),
            "ciphertext": _b64(ciphertext),
        }
        self.credentials[origin] = {"username": username, "password": password}
        self._write_vault()
        logger.info("stored credentials for %s", origin)

    def get_credentials(self, url: str) -> Optional[Dict[str, str]]:
        return self.credentials.get(canonical_origin(url))

    def remove_credentials(self, url: str) -> bool:
        if self._locked:
            raise VaultLocked("no passphrase was entered this session")

        origin = canonical_origin(url)
        if origin in self.credentials:
            del self.credentials[origin]
            del self._records[origin]
            self._write_vault()
            logger.info("removed credentials for %s", origin)
            return True
        return False

    def known_origins(self) -> list[str]:
        return sorted(self.credentials)

    # -------------------------------------------------------------------- rekey

    def rekey(self, new_passphrase: str) -> None:
        """Change the master passphrase.

        Only re-wraps each record's DEK under a freshly derived KEK -- the
        record ciphertexts themselves are untouched. This is envelope
        encryption's actual payoff: an O(records) key-wrap operation instead
        of an O(records) re-encryption of every secret.
        """
        if self._locked:
            raise VaultLocked("no passphrase was entered this session")

        new_salt = os.urandom(ARGON2_SALT_LEN)
        new_kdf_params = {
            "time_cost": ARGON2_TIME_COST,
            "memory_cost_kib": ARGON2_MEMORY_COST_KIB,
            "parallelism": ARGON2_PARALLELISM,
        }
        new_kek = _derive_kek(new_passphrase, new_salt, new_kdf_params)

        rewrapped: Dict[str, dict] = {}
        for origin, record in self._records.items():
            dek = _unwrap_dek(self._kek, origin, record)
            wrap_nonce, wrapped_dek = _wrap_dek(new_kek, origin, dek)
            rewrapped[origin] = {
                **record,
                "wrap_nonce": _b64(wrap_nonce),
                "wrapped_dek": _b64(wrapped_dek),
            }

        self._salt = new_salt
        self._kdf_params = new_kdf_params
        self._kek = new_kek
        self._records = rewrapped
        self._write_vault()
        logger.info("vault rekeyed (%d records rewrapped)", len(rewrapped))
