"""Action dispatch.

The original ran every non-URL action through subprocess.Popen(cmd,
shell=True) on strings read from an unsigned, plaintext macros.json. Any
process running as the user could append an action and get arbitrary command
execution the next time a macro fired -- the vault was encrypted, but the
thing deciding *what code runs* was not protected at all.

This removes shell=True and splits arguments properly. A signed manifest to
make the file itself trustworthy is not yet implemented.
"""

from __future__ import annotations

import logging
import shlex
import subprocess
import sys
import webbrowser
from typing import Callable, List, Optional

from automation.web_automation import OriginMismatch, handle_web_action

logger = logging.getLogger(__name__)

URL_PREFIXES = ("http://", "https://", "www.")


class ActionHandler:
    def __init__(self, credential_manager, on_error: Optional[Callable] = None) -> None:
        self.credential_manager = credential_manager
        self._on_error = on_error or (lambda message: logger.error(message))

    def execute_macro(self, actions: List[str]) -> None:
        """Run a macro's actions in order.

        One failing action does not abort the rest -- a macro that opens four
        things should still open three if one app was uninstalled.
        """
        for command in actions:
            try:
                if command.startswith(URL_PREFIXES):
                    self.open_web(command)
                else:
                    self.open_command(command)
            except Exception as exc:
                logger.exception("action failed: %s", command)
                self._on_error(f"Failed to execute {command}: {exc}")

    def open_web(self, url: str) -> None:
        if url.startswith("www."):
            url = "https://" + url

        credentials = self.credential_manager.get_credentials(url)
        if not credentials:
            webbrowser.open(url)
            return

        try:
            handle_web_action(url, credentials, on_error=self._on_error)
        except OriginMismatch as exc:
            # Surface loudly: this is a security event, not a glitch.
            self._on_error(f"Blocked credential autofill.\n\n{exc}")

    def open_command(self, command: str) -> None:
        """Launch an application or shell command without a shell.

        shell=True passes the string to cmd.exe / sh for interpretation,
        which turns any injected metacharacter into execution. Splitting the
        string and passing an argv list removes that interpreter entirely.
        """
        if sys.platform == "win32":
            argv = shlex.split(command, posix=False)
        else:
            argv = shlex.split(command)

        if not argv:
            return

        try:
            subprocess.Popen(argv, shell=False)
            logger.info("launched %s", argv[0])
        except FileNotFoundError:
            # Windows URI protocol handlers (ms-teams:, ms-settings:) are not
            # executables; the shell resolves them. webbrowser hands them to
            # the OS handler without invoking a command interpreter.
            if sys.platform == "win32" and ":" in command:
                logger.info("falling back to protocol handler for %s", command)
                webbrowser.open(command)
            else:
                raise
