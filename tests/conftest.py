"""Test fixtures.

Two jobs: keep every test off the developer's real profile directory, and
make the pynput-dependent modules importable on a headless machine (pynput's
Linux backend refuses to import without an X display, and CI has none).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _install_pynput_stub() -> None:
    """Provide a minimal pynput surface if the real one cannot import."""
    try:
        import pynput  # noqa: F401
        return
    except Exception:
        pass

    keyboard = types.ModuleType("pynput.keyboard")

    class _Key:
        def __init__(self, name):
            self.name = name

        def __repr__(self):
            return f"Key.{self.name}"

    for name in (
        "esc", "shift", "shift_r", "shift_l", "ctrl", "ctrl_r", "ctrl_l",
        "alt", "alt_r", "alt_l", "cmd", "cmd_r", "cmd_l", "f1", "space",
    ):
        setattr(_Key, name, _Key(name))

    class _KeyCode:
        def __init__(self, char=None):
            self.char = char

    class _Listener:
        def __init__(self, *args, **kwargs):
            self.on_press = kwargs.get("on_press")
            self.running = False

        def start(self):
            self.running = True

        def stop(self):
            self.running = False

    class _GlobalHotKeys(_Listener):
        def __init__(self, mapping, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.mapping = mapping
            self.daemon = True

    keyboard.Key = _Key
    keyboard.KeyCode = _KeyCode
    keyboard.Listener = _Listener
    keyboard.GlobalHotKeys = _GlobalHotKeys

    pynput_module = types.ModuleType("pynput")
    pynput_module.keyboard = keyboard

    sys.modules["pynput"] = pynput_module
    sys.modules["pynput.keyboard"] = keyboard


_install_pynput_stub()


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Redirect all application state into a temp directory."""
    monkeypatch.setenv("CUSTOMMACRO_DATA_DIR", str(tmp_path / "appdata"))
    yield tmp_path / "appdata"
