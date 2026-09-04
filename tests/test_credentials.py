"""Credential vault and, most importantly, origin canonicalisation.

The canonicalisation tests below are the ones that matter. The vault binds
the canonical origin as AEAD associated data, so a bug in canonical_origin
becomes a bug in the cryptographic guarantee itself. These cases are the
lookalike corpus described in docs/ROADMAP.md Part 3.
"""

from __future__ import annotations

import base64
import json

import pytest
from cryptography.exceptions import InvalidTag

from automation.web_automation import canonical_origin
from core.credential_manager import (
    CredentialManager,
    VaultTampered,
    WrongPassphrase,
    _open,
    _unwrap_dek,
)

PASSPHRASE = "correct horse battery staple"


# ------------------------------------------------------------- canonicalisation

@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://github.com", "https://github.com"),
        ("https://github.com/", "https://github.com"),
        ("https://github.com/user/repo?x=1#frag", "https://github.com"),
        ("https://GitHub.COM", "https://github.com"),
        ("https://github.com:443", "https://github.com"),
        ("http://example.com:80", "http://example.com"),
        ("https://github.com.", "https://github.com"),
        ("www.github.com", "https://www.github.com"),
        ("https://example.com:8443", "https://example.com:8443"),
    ],
)
def test_canonical_origin_normalises(url, expected):
    assert canonical_origin(url) == expected


@pytest.mark.parametrize(
    "lookalike",
    [
        "https://githu6.com",          # typosquat
        "https://github.co",           # TLD swap
        "https://github.com.evil.io",  # suffix confusion
        "https://evil.io/github.com",  # path confusion
        "https://www.github.com",      # different host, genuinely
        "http://github.com",           # scheme downgrade
        "https://xn--githb-9va.com",   # IDN homograph (gіthub with Cyrillic i)
    ],
)
def test_lookalikes_do_not_collide_with_the_real_origin(lookalike):
    """Every one of these must produce a different origin than github.com.

    In the original code none of this was checked at all: the password went
    into the first password field on whatever page loaded."""
    assert canonical_origin(lookalike) != canonical_origin("https://github.com")


def test_subdomain_is_a_distinct_origin():
    assert canonical_origin("https://gist.github.com") != canonical_origin(
        "https://github.com"
    )


# --------------------------------------------------------------------- the vault

def test_credentials_round_trip():
    manager = CredentialManager(PASSPHRASE)
    manager.add_credentials("https://github.com/login", "alice", "hunter2")

    assert CredentialManager(PASSPHRASE).get_credentials("https://github.com") == {
        "username": "alice",
        "password": "hunter2",
    }


def test_lookup_is_origin_scoped_not_url_scoped():
    """A credential stored from a login page must be found from any path on
    the same origin -- and from no other origin."""
    manager = CredentialManager(PASSPHRASE)
    manager.add_credentials("https://github.com/login?next=/settings", "alice", "pw")

    assert manager.get_credentials("https://github.com/anything") is not None
    assert manager.get_credentials("https://githu6.com") is None
    assert manager.get_credentials("http://github.com") is None


def test_removal():
    manager = CredentialManager(PASSPHRASE)
    manager.add_credentials("https://github.com", "alice", "pw")
    assert manager.remove_credentials("https://github.com/") is True
    assert manager.get_credentials("https://github.com") is None
    assert manager.remove_credentials("https://github.com") is False


def test_vault_is_not_plaintext_on_disk():
    from config.constants import vault_file

    manager = CredentialManager(PASSPHRASE)
    manager.add_credentials("https://github.com", "alice", "hunter2")

    blob = vault_file().read_bytes()
    assert b"hunter2" not in blob
    assert b"alice" not in blob


def test_tampered_vault_is_rejected_rather_than_silently_discarded():
    """The original caught every exception and returned {}, so a tampered or
    unreadable vault was silently replaced with an empty one on next save."""
    from config.constants import vault_file

    manager = CredentialManager(PASSPHRASE)
    manager.add_credentials("https://github.com", "alice", "pw")

    path = vault_file()
    doc = json.loads(path.read_text(encoding="utf-8"))
    ciphertext = bytearray(base64.b64decode(doc["records"]["https://github.com"]["ciphertext"]))
    ciphertext[-1] ^= 0xFF
    doc["records"]["https://github.com"]["ciphertext"] = base64.b64encode(
        bytes(ciphertext)
    ).decode("ascii")
    path.write_text(json.dumps(doc), encoding="utf-8")

    with pytest.raises(VaultTampered):
        CredentialManager(PASSPHRASE)


def test_wrong_passphrase_is_rejected_cleanly():
    CredentialManager(PASSPHRASE).add_credentials("https://github.com", "alice", "pw")

    with pytest.raises(WrongPassphrase):
        CredentialManager("a completely different passphrase")


def test_corrupted_vault_json_raises_rather_than_silently_emptying():
    from config.constants import vault_file

    CredentialManager(PASSPHRASE)  # creates the vault file
    vault_file().write_text("not valid json at all {{{", encoding="utf-8")

    with pytest.raises(VaultTampered):
        CredentialManager(PASSPHRASE)


def test_record_cannot_be_decrypted_under_the_wrong_origin():
    """The headline guarantee: origin binding is cryptographic, not a policy
    branch. A record sealed for github.com must fail AEAD authentication --
    not just fail a dict lookup -- when opened with any other origin."""
    manager = CredentialManager(PASSPHRASE)
    manager.add_credentials("https://github.com", "alice", "hunter2")

    record = manager._records["https://github.com"]
    dek = _unwrap_dek(manager._kek, "https://github.com", record)

    nonce = base64.b64decode(record["nonce"])
    ciphertext = base64.b64decode(record["ciphertext"])

    # Sanity check: the correct origin decrypts fine.
    _open(dek, b"https://github.com", nonce, ciphertext)

    with pytest.raises(InvalidTag):
        _open(dek, b"https://githu6.com", nonce, ciphertext)


def test_rekey_changes_wrapping_without_reencrypting_payload():
    manager = CredentialManager(PASSPHRASE)
    manager.add_credentials("https://github.com", "alice", "hunter2")

    old_ciphertext = manager._records["https://github.com"]["ciphertext"]
    old_wrapped_dek = manager._records["https://github.com"]["wrapped_dek"]

    manager.rekey("a brand new passphrase")

    assert manager._records["https://github.com"]["ciphertext"] == old_ciphertext
    assert manager._records["https://github.com"]["wrapped_dek"] != old_wrapped_dek

    with pytest.raises(WrongPassphrase):
        CredentialManager(PASSPHRASE)

    assert CredentialManager("a brand new passphrase").get_credentials(
        "https://github.com"
    ) == {"username": "alice", "password": "hunter2"}
