"""Macro persistence.

The original imported tkinter.messagebox into this data layer and popped a
dialog on failure. That couples storage to the GUI and crashes outright if
ever called off the Tk main thread -- which, now that macros fire from a
listener thread, is exactly what happens. Storage raises; the UI decides how
to present the failure.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Dict, List

from config.constants import macros_file

logger = logging.getLogger(__name__)


class MacroStorageError(RuntimeError):
    """Raised when macros cannot be read or written."""


class MacroManager:
    def __init__(self) -> None:
        self.macros: Dict[str, List[str]] = {}
        self.load_macros()

    def load_macros(self) -> Dict[str, List[str]]:
        path = macros_file()
        if not path.exists():
            self.macros = {}
            return self.macros

        try:
            with open(path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            logger.exception("failed to load macros from %s", path)
            raise MacroStorageError(f"Failed to load macros: {exc}") from exc

        if not isinstance(loaded, dict):
            raise MacroStorageError("macros.json must contain a JSON object")

        # Normalise: every value must be a list of action strings.
        clean: Dict[str, List[str]] = {}
        for key, actions in loaded.items():
            if isinstance(actions, list):
                clean[str(key)] = [str(a) for a in actions]
            else:
                logger.warning("dropping malformed macro %r", key)

        self.macros = clean
        logger.info("loaded %d macros from %s", len(clean), path)
        return self.macros

    def save_macros(self) -> None:
        """Write atomically.

        The original truncated the real file and wrote into it directly, so an
        interrupted write left a corrupt macros.json and the user lost every
        macro. Write to a temp file in the same directory, then replace.
        """
        path = macros_file()
        try:
            directory = path.parent
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=directory, delete=False, suffix=".tmp"
            ) as handle:
                json.dump(self.macros, handle, indent=4)
                handle.flush()
                os.fsync(handle.fileno())
                temp_name = handle.name
            os.replace(temp_name, path)
        except OSError as exc:
            logger.exception("failed to save macros to %s", path)
            raise MacroStorageError(f"Failed to save macros: {exc}") from exc

        logger.info("saved %d macros", len(self.macros))

    def get(self, key: str):
        return self.macros.get(key)
