"""Main window.

The important change here is that the dispatcher is actually wired up, so
pressing the global hotkey and then a macro key runs the macro. Previously
toggle_macro_mode flipped a boolean and recoloured a label, and nothing ever
called execute_macro.

Threading matters now. pynput delivers its callbacks on listener threads, and
Tk is not thread-safe -- touching a widget from another thread corrupts the
interpreter or crashes outright. Every cross-thread update goes through
_post(), which marshals onto the Tk main loop with after().
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from config.constants import COLORS
from config.paths import data_dir, migrate_legacy_data
from config.settings import GLOBAL_HOTKEY
from core.action_handler import ActionHandler
from core.credential_manager import CredentialManager
from core.dispatcher import MacroDispatcher
from core.hotkey_manager import HotkeyManager
from core.macro_manager import MacroManager, MacroStorageError
from ui.dialogs import AddActionDialog, CustomDialog

logger = logging.getLogger(__name__)


class MacroControllerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()

        migrated = migrate_legacy_data()
        if migrated:
            logger.info("migrated legacy data: %s", ", ".join(migrated))

        self.credential_manager = CredentialManager()

        self.macro_manager = MacroManager()
        self.action_handler = ActionHandler(
            self.credential_manager,
            on_error=lambda message: self._post(self._show_error, message),
        )

        self.dispatcher = MacroDispatcher(
            resolve=self.macro_manager.get,
            execute=self.action_handler.execute_macro,
            on_state_change=self._on_dispatch_state,
        )

        self.create_gui()
        self.update_macro_list()

        self.hotkeys = HotkeyManager(self.dispatcher.toggle)
        if not self.hotkeys.start():
            self._show_error(
                f"Could not register the global hotkey ({GLOBAL_HOTKEY}).\n\n"
                "Another application may already own it. You can still run "
                "macros from this window."
            )

        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

    # ---------------------------------------------------------- thread marshalling

    def _post(self, callback, *args) -> None:
        """Run `callback` on the Tk main thread."""
        try:
            self.root.after(0, lambda: callback(*args))
        except RuntimeError:
            # Interpreter is already tearing down.
            logger.debug("dropped UI update during shutdown", exc_info=True)

    def _on_dispatch_state(self, armed: bool, reason: str) -> None:
        """Called from the dispatcher's threads."""
        self._post(self._render_mode, armed, reason)

    def _render_mode(self, armed: bool, reason: str) -> None:
        self.status_label.config(
            text="Macro Mode: ON  —  press a macro key" if armed else "Macro Mode: OFF",
            foreground=COLORS["warning"] if armed else COLORS["text"],
        )
        self.toggle_button.config(
            bg=COLORS["warning"] if armed else COLORS["success"],
            text="Listening…" if armed else "Toggle Macro Mode",
        )
        self.hint_label.config(text=reason.capitalize() if reason else "")

    def _show_error(self, message: str) -> None:
        messagebox.showerror("Macro Controller", message)

    # -------------------------------------------------------------------- actions

    def toggle_macro_mode(self) -> None:
        self.dispatcher.toggle()

    def add_macro(self) -> None:
        macro_key = self.ask_string(
            "New Macro", "Press-key for this macro (a single character):"
        )
        if not macro_key:
            return

        macro_key = macro_key.strip().lower()
        if len(macro_key) != 1:
            self._show_error("A macro key must be exactly one character.")
            return

        if macro_key in self.macro_manager.macros:
            if not messagebox.askyesno(
                "Replace macro?",
                f"A macro is already bound to {macro_key!r}. Replace it?",
            ):
                return

        actions: list[str] = []
        while True:
            dialog = AddActionDialog(self.root, self.credential_manager)
            self.root.wait_window(dialog)
            if not dialog.result:
                break
            actions.append(dialog.result)

            if not messagebox.askyesno("Add another?", "Add another action to this macro?"):
                break

        if not actions:
            return

        self.macro_manager.macros[macro_key] = actions
        self._save_macros()

    def delete_macro(self) -> None:
        selection = self.macro_list.selection()
        if not selection:
            messagebox.showwarning("Nothing selected", "Select a macro to delete.")
            return

        key = self.macro_list.item(selection[0])["values"][0]
        key = str(key)
        if not messagebox.askyesno("Delete macro", f"Delete the macro bound to {key!r}?"):
            return

        self.macro_manager.macros.pop(key, None)
        self._save_macros()

    def run_selected_macro(self) -> None:
        """Run a macro from the window, without using the hotkey."""
        selection = self.macro_list.selection()
        if not selection:
            messagebox.showwarning("Nothing selected", "Select a macro to run.")
            return

        key = str(self.macro_list.item(selection[0])["values"][0])
        actions = self.macro_manager.get(key)
        if actions:
            import threading

            threading.Thread(
                target=self.action_handler.execute_macro,
                args=(list(actions),),
                daemon=True,
                name=f"macro-{key}",
            ).start()

    def _save_macros(self) -> None:
        try:
            self.macro_manager.save_macros()
        except MacroStorageError as exc:
            self._show_error(str(exc))
        self.update_macro_list()

    def ask_string(self, title: str, prompt: str):
        return CustomDialog(self.root, title, prompt).result

    def update_macro_list(self) -> None:
        self.macro_list.delete(*self.macro_list.get_children())
        for key, actions in sorted(self.macro_manager.macros.items()):
            summary = ", ".join(actions)
            if len(summary) > 90:
                summary = summary[:87] + "…"
            self.macro_list.insert("", "end", values=(key, len(actions), summary))

    # ------------------------------------------------------------------------- ui

    def create_gui(self) -> None:
        self.root.title("Macro Controller")
        self.root.geometry("900x700")
        self.root.minsize(720, 480)

        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        self.status_label = tk.Label(
            container,
            text="Macro Mode: OFF",
            font=("Segoe UI", 16),
            bg=COLORS["background"],
            fg=COLORS["text"],
        )
        self.status_label.pack(pady=(0, 4))

        self.hint_label = ttk.Label(container, text="", foreground="#666")
        self.hint_label.pack(pady=(0, 12))

        ttk.Label(
            container,
            text=f"Press {GLOBAL_HOTKEY} anywhere, then a macro key.",
            foreground="#666",
        ).pack(pady=(0, 16))

        button_frame = ttk.Frame(container)
        button_frame.pack(pady=(0, 20))

        self.toggle_button = tk.Button(
            button_frame,
            text="Toggle Macro Mode",
            command=self.toggle_macro_mode,
            font=("Segoe UI", 12),
            bg=COLORS["success"],
            fg="white",
            width=18,
            height=2,
        )
        self.toggle_button.pack(side=tk.LEFT, padx=5)

        for label, command, colour in (
            ("Add New Macro", self.add_macro, COLORS["primary"]),
            ("Run Selected", self.run_selected_macro, COLORS["primary"]),
            ("Delete Macro", self.delete_macro, COLORS["danger"]),
        ):
            tk.Button(
                button_frame,
                text=label,
                command=command,
                font=("Segoe UI", 12),
                bg=colour,
                fg="white",
                width=18,
                height=2,
            ).pack(side=tk.LEFT, padx=5)

        self.macro_list = ttk.Treeview(
            container, columns=("Key", "Count", "Actions"), show="headings", height=10
        )
        self.macro_list.heading("Key", text="Key")
        self.macro_list.heading("Count", text="Actions")
        self.macro_list.heading("Actions", text="Details")
        self.macro_list.column("Key", width=60, anchor="center")
        self.macro_list.column("Count", width=80, anchor="center")
        self.macro_list.pack(fill=tk.BOTH, expand=True)
        self.macro_list.bind("<Double-1>", lambda _e: self.run_selected_macro())

        ttk.Label(
            container, text=f"Data: {data_dir()}", foreground="#888"
        ).pack(anchor="w", pady=(10, 0))

    # ------------------------------------------------------------------ lifecycle

    def shutdown(self) -> None:
        """Release the global keyboard hooks before the window goes away.

        Without this, a suppressing listener can outlive the UI and leave the
        user's keyboard captured.
        """
        logger.info("shutting down")
        try:
            self.dispatcher.shutdown()
            self.hotkeys.stop()
        finally:
            self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
