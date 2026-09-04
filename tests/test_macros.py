"""Macro storage."""

from __future__ import annotations

import json

import pytest

from config.constants import macros_file
from core.macro_manager import MacroManager, MacroStorageError


def test_starts_empty_when_no_file():
    assert MacroManager().macros == {}


def test_round_trip():
    manager = MacroManager()
    manager.macros["w"] = ["https://github.com", "notepad"]
    manager.save_macros()

    assert MacroManager().macros == {"w": ["https://github.com", "notepad"]}


def test_malformed_entries_are_dropped_not_fatal():
    macros_file().write_text(
        json.dumps({"good": ["notepad"], "bad": "not-a-list"}), encoding="utf-8"
    )
    macros = MacroManager().macros
    assert "good" in macros
    assert "bad" not in macros


def test_corrupt_file_raises_rather_than_silently_emptying():
    """The original returned {} on any failure, so the next save wrote the
    empty dict over the user's real macros."""
    macros_file().write_text("{ this is not json", encoding="utf-8")
    with pytest.raises(MacroStorageError):
        MacroManager()


def test_save_is_atomic(monkeypatch):
    """An interrupted write must leave the previous file intact."""
    manager = MacroManager()
    manager.macros["w"] = ["notepad"]
    manager.save_macros()

    def explode(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("os.replace", explode)
    manager.macros["w"] = ["destroyed"]
    with pytest.raises(MacroStorageError):
        manager.save_macros()

    assert MacroManager().macros == {"w": ["notepad"]}


def test_get_returns_none_for_unbound_key():
    assert MacroManager().get("zzz") is None
