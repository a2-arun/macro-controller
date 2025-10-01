import tkinter as tk
from tkinter import ttk, messagebox
from core.credential_manager import CredentialManager
from core.macro_manager import MacroManager
from core.action_handler import ActionHandler
from core.hotkey_manager import HotkeyManager
from ui.dialogs import CustomDialog, AddActionDialog
from config.constants import COLORS

class MacroControllerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.credential_manager = CredentialManager()
        self.macro_manager = MacroManager()
        self.action_handler = ActionHandler(self.credential_manager)
        self.is_macro_mode = False
        self.keyboard_listener = None
        self.create_gui()
        self.hotkeys = HotkeyManager(self.toggle_macro_mode)
        self.hotkeys.start()

    def toggle_macro_mode(self):
        self.is_macro_mode = not self.is_macro_mode
        status = "ON" if self.is_macro_mode else "OFF"
        self.status_label.config(
            text=f"Macro Mode: {status}",
            foreground=COLORS["warning"] if self.is_macro_mode else COLORS["text"]
        )
        self.toggle_button.config(bg=COLORS["warning"] if self.is_macro_mode else COLORS["success"])

    def add_macro(self):
        macro_key = self.ask_string("Enter Macro Key", "Enter the key for this macro:")
        if macro_key:
            actions = []
            while True:
                dialog = AddActionDialog(self.root, self.credential_manager)
                self.root.wait_window(dialog)
                if not dialog.result:
                    break
                actions.append(dialog.result)
            if actions:
                self.macro_manager.macros[macro_key] = actions
                self.macro_manager.save_macros()
                self.update_macro_list()

    def delete_macro(self):
        selection = self.macro_list.selection()
        if not selection:
            messagebox.showwarning("Warning", "Select a macro to delete")
            return
        key = self.macro_list.item(selection[0])['values'][0]
        del self.macro_manager.macros[key]
        self.macro_manager.save_macros()
        self.update_macro_list()

    def ask_string(self, title, prompt):
        dialog = CustomDialog(self.root, title, prompt)
        return dialog.result

    def update_macro_list(self):
        self.macro_list.delete(*self.macro_list.get_children())
        for key, actions in self.macro_manager.macros.items():
            self.macro_list.insert('', 'end', values=(key, len(actions), ", ".join(actions)))

    def create_gui(self):
        self.root.title("Macro Controller")
        self.root.geometry("900x700")
        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
        self.status_label = tk.Label(container, text="Macro Mode: OFF", font=('Segoe UI', 16),
                                     bg=COLORS["background"], fg=COLORS["text"])
        self.status_label.pack(pady=(0, 20))
        button_frame = ttk.Frame(container)
        button_frame.pack(pady=(0, 20))
        self.toggle_button = tk.Button(button_frame, text="Toggle Macro Mode",
                                       command=self.toggle_macro_mode, font=("Segoe UI", 12),
                                       bg=COLORS["success"], fg="white", width=20, height=2)
        self.toggle_button.pack(side=tk.LEFT, padx=5)
        self.add_button = tk.Button(button_frame, text="Add New Macro",
                                    command=self.add_macro, font=("Segoe UI", 12),
                                    bg=COLORS["primary"], fg="white", width=20, height=2)
        self.add_button.pack(side=tk.LEFT, padx=5)
        self.delete_button = tk.Button(button_frame, text="Delete Macro",
                                       command=self.delete_macro, font=("Segoe UI", 12),
                                       bg=COLORS["danger"], fg="white", width=20, height=2)
        self.delete_button.pack(side=tk.LEFT, padx=5)
        self.macro_list = ttk.Treeview(container, columns=("Key", "Count", "Actions"), show="headings", height=10)
        self.macro_list.heading("Key", text="Key")
        self.macro_list.heading("Count", text="Action Count")
        self.macro_list.heading("Actions", text="Actions")
        self.macro_list.pack(fill=tk.BOTH, expand=True)

    def run(self):
        self.root.mainloop()
