# CustomMacro

A keyboard-driven macro launcher for Windows. Press a global hotkey, press a
single key, and a saved sequence of actions runs — open a set of URLs, launch
applications, sign in to sites automatically.

## Status

Under active modernisation. See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the
audit, the engineering plan, and the research direction.

**Security notice.** The credential vault is currently *not* secure: the key
derivation input is a constant committed to this repository, so anyone with a
copy of the data directory can decrypt it. This is a known, documented defect
being addressed in Phase 2. Do not store a credential here that you would mind
disclosing.

## Requirements

- Python 3.11+
- Google Chrome (only for the automatic sign-in feature)

## Running

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python main.py
```

## Using it

1. Click **Add New Macro** and choose a single key to bind.
2. Add one or more actions — a URL (`https://github.com`), an application
   (`notepad`), or a Windows protocol handler (`ms-teams`).
3. Press <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>M</kbd> anywhere, then your macro
   key.

Macro mode captures exactly one keystroke and then releases the keyboard. It
also releases automatically after five seconds, so a bug here can never leave
your keyboard captured. <kbd>Esc</kbd> always cancels.

## Where your data lives

`%APPDATA%\CustomMacro\` — macros, the credential vault, and logs. The path is
shown at the bottom of the main window. A legacy `./data` directory is migrated
automatically on first run (copied, not moved).

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

The test suite runs headless: `tests/conftest.py` stubs `pynput` when no
display is available, and every test is redirected to a temporary data
directory via `CUSTOMMACRO_DATA_DIR`.

## Layout

```
main.py                      entry point, logging setup
config/paths.py              app data directory resolution + legacy migration
config/constants.py          lazily-resolved paths, UI palette
config/settings.py           hotkey, KDF parameters, timeouts
core/dispatcher.py           key capture -> macro resolution -> execution
core/hotkey_manager.py       global toggle hotkey registration
core/macro_manager.py        atomic macro persistence
core/credential_manager.py   credential vault (see security notice)
core/action_handler.py       action execution, no shell interpreter
automation/web_automation.py Selenium autofill with origin verification
ui/                          Tkinter interface
tests/                       pytest suite
```
