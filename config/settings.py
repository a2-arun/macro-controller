"""Global settings."""

# Global toggle hotkey. pynput syntax.
GLOBAL_HOTKEY = "<ctrl>+<alt>+m"

# Seconds the keyboard may stay captured while waiting for a macro key.
ARM_TIMEOUT_SECONDS = 5.0

# Argon2id parameters for deriving the vault's key-encryption key (KEK) from
# the user's passphrase. Named constants (not inlined) because they're a
# tuning knob: docs/ROADMAP.md Part 3 Contribution 3 wants an unlock-latency
# vs. memory sweep as part of the eventual evaluation.
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST_KIB = 65536  # 64 MiB
ARGON2_PARALLELISM = 4
ARGON2_HASH_LEN = 32  # bytes -> AES-256 key length
ARGON2_SALT_LEN = 16  # bytes

MIN_PASSPHRASE_LENGTH = 8
