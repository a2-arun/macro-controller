"""Action dispatch and the key listener that fires it."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.action_handler import ActionHandler


class FakeCredentialManager:
    def __init__(self, store=None):
        self.store = store or {}

    def get_credentials(self, url):
        from automation.web_automation import canonical_origin

        return self.store.get(canonical_origin(url))


# ------------------------------------------------------------------- dispatching

def test_urls_route_to_the_browser():
    handler = ActionHandler(FakeCredentialManager())
    with patch("core.action_handler.webbrowser.open") as opener:
        handler.execute_macro(["https://github.com"])
    opener.assert_called_once_with("https://github.com")


def test_bare_www_is_upgraded_to_https():
    handler = ActionHandler(FakeCredentialManager())
    with patch("core.action_handler.webbrowser.open") as opener:
        handler.execute_macro(["www.github.com"])
    opener.assert_called_once_with("https://www.github.com")


def test_commands_run_without_a_shell():
    """shell=True on strings from an unsigned macros.json was arbitrary code
    execution for anyone who could write that file."""
    handler = ActionHandler(FakeCredentialManager())
    with patch("core.action_handler.subprocess.Popen") as popen:
        handler.execute_macro(["notepad"])

    args, kwargs = popen.call_args
    assert kwargs.get("shell") is False
    assert isinstance(args[0], list)


def test_shell_metacharacters_are_not_interpreted():
    handler = ActionHandler(FakeCredentialManager())
    with patch("core.action_handler.subprocess.Popen") as popen:
        handler.execute_macro(["notepad && calc"])

    argv = popen.call_args[0][0]
    # The payload survives as inert argv entries, never as a shell operator.
    assert argv[0] == "notepad"
    assert "&&" not in argv[0]


def test_one_failing_action_does_not_abort_the_macro():
    errors = []
    handler = ActionHandler(FakeCredentialManager(), on_error=errors.append)

    with patch("core.action_handler.subprocess.Popen", side_effect=OSError("boom")), \
         patch("core.action_handler.webbrowser.open") as opener:
        handler.execute_macro(["definitely-not-a-real-binary", "https://github.com"])

    assert errors, "the failure should have been reported"
    opener.assert_called_once()  # and the macro continued


def test_origin_mismatch_is_surfaced_as_a_security_error():
    from automation.web_automation import OriginMismatch

    creds = FakeCredentialManager({"https://github.com": {"username": "a", "password": "b"}})
    errors = []
    handler = ActionHandler(creds, on_error=errors.append)

    with patch(
        "core.action_handler.handle_web_action",
        side_effect=OriginMismatch("expected https://github.com, landed on https://evil.io"),
    ):
        handler.execute_macro(["https://github.com"])

    assert len(errors) == 1
    assert "Blocked credential autofill" in errors[0]


# --------------------------------------------------------------------- dispatch

def test_dispatcher_resolves_a_key_to_a_macro():
    from core.dispatcher import MacroDispatcher
    from pynput import keyboard

    executed = []
    dispatcher = MacroDispatcher(
        resolve=lambda key: ["notepad"] if key == "w" else None,
        execute=executed.append,
        on_state_change=lambda armed, reason: None,
    )

    key = keyboard.KeyCode(char="w")
    dispatcher._on_press(key)

    import time
    time.sleep(0.1)  # the macro runs on a worker thread
    assert executed == [["notepad"]]


def test_dispatcher_uppercase_keys_normalise():
    from core.dispatcher import MacroDispatcher

    assert MacroDispatcher._key_label(type("K", (), {"char": "W"})()) == "w"


def test_bare_modifiers_do_not_consume_the_arm_window():
    from core.dispatcher import MacroDispatcher
    from pynput import keyboard

    assert MacroDispatcher._key_label(keyboard.Key.shift) is None
    assert MacroDispatcher._key_label(keyboard.Key.ctrl) is None
    assert MacroDispatcher._key_label(keyboard.Key.f1) == "<f1>"
