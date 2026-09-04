"""Path resolution -- the bug that made the packaged build start empty."""

from __future__ import annotations

import os

from config.constants import macros_file
from config.paths import data_dir


def test_paths_are_absolute():
    """Relative paths resolve against CWD, so launching from a shortcut or a
    PyInstaller bundle silently pointed the app at the wrong directory."""
    assert macros_file().is_absolute()
    assert data_dir().is_absolute()


def test_data_dir_is_created():
    assert data_dir().is_dir()


def test_paths_do_not_depend_on_cwd(tmp_path, monkeypatch):
    before = macros_file()
    monkeypatch.chdir(tmp_path)
    assert macros_file() == before
