"""Application-wide constants.

Paths are resolved lazily through config.paths so that a test can redirect
them via CUSTOMMACRO_DATA_DIR before anything touches the filesystem.
Importing this module must not have side effects.
"""

from __future__ import annotations

from pathlib import Path

from config.paths import data_dir


def macros_file() -> Path:
    return data_dir() / "macros.json"


def vault_file() -> Path:
    return data_dir() / "vault.json"


def manifest_signature_file() -> Path:
    """Detached authentication tag over macros.json.

    macros.json decides what code runs, so it needs integrity protection at
    least as strong as the credential vault's confidentiality. See
    docs/ROADMAP.md C4.
    """
    return data_dir() / "macros.sig"


# UI palette.
COLORS = {
    "primary": "#007ACC",
    "success": "#28A745",
    "warning": "#FFC107",
    "background": "#f3f3f3",
    "secondary_bg": "#e9ecef",
    "text": "#2b2b2b",
    "danger": "#DC3545",
    "border": "#CED4DA",
}
