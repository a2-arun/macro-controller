"""Credential vault and, most importantly, origin canonicalisation.

The canonicalisation tests below are the ones that matter. Phase 2 binds the
canonical origin as AEAD associated data, so a bug in canonical_origin becomes
a bug in the cryptographic guarantee itself. These cases are the lookalike
corpus described in docs/ROADMAP.md Part 3.
"""

from __future__ import annotations

import pytest

from automation.web_automation import canonical_origin
from core.credential_manager import CredentialManager


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
    manager = CredentialManager()
    manager.add_credentials("https://github.com/login", "alice", "hunter2")

    assert CredentialManager().get_credentials("https://github.com") == {
        "username": "alice",
        "password": "hunter2",
    }


def test_lookup_is_origin_scoped_not_url_scoped():
    """A credential stored from a login page must be found from any path on
    the same origin -- and from no other origin."""
    manager = CredentialManager()
    manager.add_credentials("https://github.com/login?next=/settings", "alice", "pw")

    assert manager.get_credentials("https://github.com/anything") is not None
    assert manager.get_credentials("https://githu6.com") is None
    assert manager.get_credentials("http://github.com") is None


def test_removal():
    manager = CredentialManager()
    manager.add_credentials("https://github.com", "alice", "pw")
    assert manager.remove_credentials("https://github.com/") is True
    assert manager.get_credentials("https://github.com") is None
    assert manager.remove_credentials("https://github.com") is False


def test_vault_is_not_plaintext_on_disk():
    from config.constants import credentials_file

    manager = CredentialManager()
    manager.add_credentials("https://github.com", "alice", "hunter2")

    blob = credentials_file().read_bytes()
    assert b"hunter2" not in blob
    assert b"alice" not in blob


def test_tampered_vault_is_rejected_rather_than_silently_discarded():
    """The original caught every exception and returned {}, so a tampered or
    unreadable vault was silently replaced with an empty one on next save."""
    from cryptography.fernet import InvalidToken

    from config.constants import credentials_file

    manager = CredentialManager()
    manager.add_credentials("https://github.com", "alice", "pw")

    blob = bytearray(credentials_file().read_bytes())
    blob[-1] ^= 0xFF
    credentials_file().write_bytes(bytes(blob))

    with pytest.raises(InvalidToken):
        CredentialManager()
