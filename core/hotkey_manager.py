"""Global toggle hotkey.

Kept deliberately thin: it owns the OS-level hotkey registration and nothing
else. What happens when the hotkey fires is the dispatcher's business.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from pynput import keyboard

from config.settings import GLOBAL_HOTKEY

logger = logging.getLogger(__name__)


class HotkeyManager:
    def __init__(self, toggle_callback: Callable[[], None]) -> None:
        self._toggle_callback = toggle_callback
        self._listener: Optional[keyboard.GlobalHotKeys] = None

    def start(self) -> bool:
        """Register the hotkey. Returns False if registration failed.

        The original called .start() with no error handling, so a failed
        registration left the app running with no way to trigger anything and
        no indication why.
        """
        try:
            self._listener = keyboard.GlobalHotKeys({GLOBAL_HOTKEY: self._fire})
            self._listener.daemon = True
            self._listener.start()
        except Exception:
            logger.exception("could not register global hotkey %s", GLOBAL_HOTKEY)
            self._listener = None
            return False

        logger.info("global hotkey registered: %s", GLOBAL_HOTKEY)
        return True

    def _fire(self) -> None:
        try:
            self._toggle_callback()
        except Exception:
            logger.exception("hotkey callback raised")

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                logger.exception("error stopping hotkey listener")
            self._listener = None
