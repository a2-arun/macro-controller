"""Dialogs.

The original AddActionDialog accepted a credential_manager and never used it,
and CredentialManager.add_credentials was never called from anywhere -- so
there was no way to store a credential and the vault was always empty. This
adds the missing path.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from config.settings import MIN_PASSPHRASE_LENGTH

URL_PREFIXES = ("http://", "https://", "www.")


class PassphraseDialog(simpledialog.Dialog):
    """Prompt for the vault's master passphrase.

    first_run=True asks the user to choose a new passphrase (with
    confirmation); first_run=False asks for the existing one. Cancel is
    relabelled "Skip" -- declining leaves self.result as None, which the
    caller treats as "run this session without the vault" rather than an
    error.
    """

    def __init__(self, parent, *, first_run: bool):
        self.first_run = first_run
        self.result = None
        title = "Choose a Vault Passphrase" if first_run else "Unlock Credential Vault"
        super().__init__(parent, title)

    def body(self, master):
        if self.first_run:
            message = (
                "Choose a passphrase to protect stored credentials.\n"
                "It is never written to disk -- if you forget it, stored\n"
                "credentials cannot be recovered."
            )
        else:
            message = "Enter your vault passphrase, or Skip to run without stored credentials."

        ttk.Label(master, text=message, justify="left").grid(
            row=0, column=0, columnspan=2, padx=8, pady=(8, 12), sticky="w"
        )

        ttk.Label(master, text="Passphrase").grid(row=1, column=0, padx=8, sticky="w")
        self.entry = ttk.Entry(master, width=32, show="•")
        self.entry.grid(row=1, column=1, padx=8, pady=3)

        self.confirm_entry = None
        if self.first_run:
            ttk.Label(master, text="Confirm").grid(row=2, column=0, padx=8, sticky="w")
            self.confirm_entry = ttk.Entry(master, width=32, show="•")
            self.confirm_entry.grid(row=2, column=1, padx=8, pady=3)

        return self.entry

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text="OK", command=self.ok, default=tk.ACTIVE).pack(
            side=tk.LEFT, padx=5, pady=8
        )
        ttk.Button(box, text="Skip", command=self.cancel).pack(side=tk.LEFT, padx=5, pady=8)
        self.bind("<Return>", lambda _event: self.ok())
        self.bind("<Escape>", lambda _event: self.cancel())
        box.pack()

    def validate(self) -> bool:
        passphrase = self.entry.get()

        if self.first_run:
            if len(passphrase) < MIN_PASSPHRASE_LENGTH:
                messagebox.showwarning(
                    "Passphrase too short",
                    f"Use at least {MIN_PASSPHRASE_LENGTH} characters.",
                    parent=self,
                )
                return False
            if passphrase != self.confirm_entry.get():
                messagebox.showwarning(
                    "Passphrases don't match", "Try again.", parent=self
                )
                return False
        elif not passphrase:
            messagebox.showwarning(
                "Passphrase required", "Enter your passphrase, or Skip.", parent=self
            )
            return False

        return True

    def apply(self):
        self.result = self.entry.get()


class CustomDialog(simpledialog.Dialog):
    """Single-line text prompt."""

    def __init__(self, parent, title: str, prompt: str, initial: str = ""):
        self.prompt = prompt
        self.initial = initial
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text=self.prompt).grid(row=0, column=0, padx=8, pady=8, sticky="w")
        self.entry = ttk.Entry(master, width=44)
        self.entry.grid(row=1, column=0, padx=8, pady=(0, 8))
        self.entry.insert(0, self.initial)
        return self.entry

    def apply(self):
        self.result = self.entry.get().strip()


class AddActionDialog(tk.Toplevel):
    """Add one action to a macro, optionally with stored credentials."""

    def __init__(self, parent, credential_manager):
        super().__init__(parent)
        self.credential_manager = credential_manager
        self.result = None

        self.title("Add Action")
        self.geometry("460x380")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text="URL or application to launch",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text="e.g. https://github.com, www.gmail.com, notepad, ms-teams",
            foreground="#666",
        ).pack(anchor="w", pady=(0, 6))

        self.url_entry = ttk.Entry(frame, width=52)
        self.url_entry.pack(fill=tk.X)
        self.url_entry.bind("<KeyRelease>", self._on_target_changed)
        self.url_entry.focus_set()

        self.cred_frame = ttk.LabelFrame(
            frame, text="Automatic sign-in (optional)", padding=12
        )

        self.use_credentials = tk.BooleanVar(value=False)
        self.cred_check = ttk.Checkbutton(
            self.cred_frame,
            text="Store credentials and sign in automatically",
            variable=self.use_credentials,
            command=self._toggle_credential_fields,
        )
        self.cred_check.pack(anchor="w", pady=(0, 8))

        self.cred_fields = ttk.Frame(self.cred_frame)

        ttk.Label(self.cred_fields, text="Username").grid(row=0, column=0, sticky="w")
        self.username_entry = ttk.Entry(self.cred_fields, width=34)
        self.username_entry.grid(row=0, column=1, padx=(8, 0), pady=3)

        ttk.Label(self.cred_fields, text="Password").grid(row=1, column=0, sticky="w")
        self.password_entry = ttk.Entry(self.cred_fields, width=34, show="•")
        self.password_entry.grid(row=1, column=1, padx=(8, 0), pady=3)

        ttk.Label(
            self.cred_fields,
            text=("Credentials are bound to this exact origin and will not be\n"
                  "filled on any other site."),
            foreground="#666",
            justify="left",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        buttons = ttk.Frame(frame)
        buttons.pack(side=tk.BOTTOM, fill=tk.X, pady=(16, 0))
        ttk.Button(buttons, text="Cancel", command=self._cancel).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="Add", command=self._ok).pack(side=tk.RIGHT, padx=(0, 8))

        self.bind("<Return>", lambda _event: self._ok())
        self.bind("<Escape>", lambda _event: self._cancel())

    # ------------------------------------------------------------------ helpers

    def _looks_like_url(self, value: str) -> bool:
        return value.startswith(URL_PREFIXES)

    def _on_target_changed(self, _event=None) -> None:
        """Only offer credential storage for things that can have a login."""
        if self._looks_like_url(self.url_entry.get().strip()):
            self.cred_frame.pack(fill=tk.X, pady=(16, 0))
        else:
            self.cred_frame.pack_forget()

    def _toggle_credential_fields(self) -> None:
        if self.use_credentials.get():
            self.cred_fields.pack(fill=tk.X)
        else:
            self.cred_fields.pack_forget()

    # ------------------------------------------------------------------ actions

    def _ok(self) -> None:
        target = self.url_entry.get().strip()
        if not target:
            messagebox.showwarning("Missing action", "Enter a URL or application.", parent=self)
            return

        if self._looks_like_url(target) and self.use_credentials.get():
            username = self.username_entry.get().strip()
            password = self.password_entry.get()

            if not username or not password:
                messagebox.showwarning(
                    "Missing credentials",
                    "Enter both a username and a password, or turn off automatic sign-in.",
                    parent=self,
                )
                return

            url = "https://" + target if target.startswith("www.") else target
            try:
                self.credential_manager.add_credentials(url, username, password)
            except Exception as exc:
                messagebox.showerror(
                    "Could not save credentials", str(exc), parent=self
                )
                return
            finally:
                # Do not leave the secret sitting in a widget.
                self.password_entry.delete(0, tk.END)

        self.result = target
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()
