"""Global settings."""

# Global toggle hotkey. pynput syntax.
GLOBAL_HOTKEY = "<ctrl>+<alt>+m"

# !! Phase 1 only. See the module docstring in core/credential_manager.py.
# A KDF input committed to source provides no confidentiality whatsoever.
# Phase 2 replaces this with a user passphrase run through Argon2id.
DEFAULT_KEY_DERIVATION_PASSWORD = b"macro_controller_key"
PBKDF2_ITERATIONS = 600_000  # OWASP 2023 floor for PBKDF2-HMAC-SHA256

# Seconds the keyboard may stay captured while waiting for a macro key.
ARM_TIMEOUT_SECONDS = 5.0
