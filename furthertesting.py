
from pynput import keyboard
import webbrowser
import os
import json
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText
import subprocess
import platform

# Constants
MACROS_FILE = "macros.json"
COLORS = {
    "primary": "#2196F3",
    "success": "#4CAF50",
    "warning": "#FF5722",
    "background": "#ffffff",
    "secondary_bg": "#f8f9fa",
    "text": "#333333",
    "danger": "#dc3545",
    "border": "#dee2e6"
}

class CustomDialog(simpledialog.Dialog):
    def __init__(self, parent, title, prompt):
        self.prompt = prompt
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text=self.prompt, anchor="center", justify="center").grid(row=0, padx=5, pady=5, columnspan=2)
        self.entry = ttk.Entry(master, width=40)
        self.entry.grid(row=1, padx=5, pady=5, columnspan=2)
        return self.entry

    def apply(self):
        self.result = self.entry.get()

class MacroController:
    def __init__(self):
        self.is_macro_mode = False
        self.macros = self.load_macros()
        self.keyboard_listener = None
        self.create_gui()
        
    def load_macros(self):
        try:
            if os.path.exists(MACROS_FILE):
                with open(MACROS_FILE, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load macros: {e}")
            return {}

    def save_macros(self):
        try:
            with open(MACROS_FILE, 'w') as f:
                json.dump(self.macros, f, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save macros: {e}")

    def on_key_press(self, key):
        if not self.is_macro_mode:
            return

        try:
            key_char = key.char if hasattr(key, 'char') else str(key)
            
            if key_char in self.macros:
                self.execute_macro(key_char)
        except AttributeError:
            pass

    def toggle_macro_mode(self):
        self.is_macro_mode = not self.is_macro_mode
        status = "ON" if self.is_macro_mode else "OFF"
        
        if self.is_macro_mode:
            if not self.keyboard_listener:
                self.keyboard_listener = keyboard.Listener(on_press=self.on_key_press)
                self.keyboard_listener.start()
        else:
            if self.keyboard_listener:
                self.keyboard_listener.stop()
                self.keyboard_listener = None

        self.status_label['text'] = f"Macro Mode: {status}"
        self.status_label['foreground'] = COLORS["warning"] if self.is_macro_mode else COLORS["text"]
        self.toggle_button.config(
            bg=COLORS["warning"] if self.is_macro_mode else COLORS["success"]
        )

    def execute_macro(self, key):
        if key in self.macros:
            for command in self.macros[key]:
                self.open_command(command)

    def open_command(self, command):
        try:
            if any(command.startswith(prefix) for prefix in ['http://', 'https://', 'www.']):
                if command.startswith('www.'):
                    command = 'https://' + command
                webbrowser.open(command)
                return

            if command.lower() == 'code':
                if platform.system() == 'Windows':
                    subprocess.Popen(['code'])
                else:
                    subprocess.Popen(['code'])
                return
                
            if platform.system() == 'Windows':
                try:
                    subprocess.Popen(command, shell=True)
                except Exception:
                    os.startfile(command)
            else:
                subprocess.Popen([command], shell=True)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to execute {command}: {e}")

    def ask_string(self, title, prompt):
        dialog = CustomDialog(self.window, title, prompt)
        return dialog.result

    def add_macro(self):
        key = self.ask_string("Add Macro", "Enter the key to assign a macro:")
        if key and len(key) == 1:
            actions = []
            while True:
                action = self.ask_string(
                    "Add Action",
                    "Enter a URL or command (or leave blank to finish):"
                )
                if action:
                    actions.append(action)
                else:
                    break
            if actions:
                self.macros[key] = actions
                self.save_macros()
                self.update_macro_list()
                messagebox.showinfo(
                    "Success",
                    f"Macro '{key}' added with {len(actions)} actions."
                )
            else:
                messagebox.showwarning("No Actions", "No actions were added for this macro.")
        else:
            messagebox.showerror(
                "Invalid Key",
                "Please enter a single character for the macro key."
            )

    def delete_macro(self):
        selection = self.macro_list.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a macro to delete")
            return
        
        item = self.macro_list.item(selection[0])
        key = item['values'][0]
        if messagebox.askyesno("Confirm Delete", f"Delete macro for key '{key}'?"):
            del self.macros[key]
            self.save_macros()
            self.update_macro_list()

    def update_macro_list(self):
        self.macro_list.delete(*self.macro_list.get_children())
        for key, actions in self.macros.items():
            self.macro_list.insert(
                '',
                'end',
                values=(key, len(actions), ", ".join(actions))
            )

    def create_gui(self):
        self.window = tk.Tk()
        self.window.title("Macro Controller")
        self.window.geometry("900x700")
        self.window.configure(bg=COLORS["background"])
        
        self.center_window()

        self.create_styles()

        container = ttk.Frame(self.window, style='Main.TFrame')
        container.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        header_frame = ttk.Frame(container, style='Main.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 20))

        app_title = ttk.Label(
            header_frame,
            text="Macro Controller",
            style='AppTitle.TLabel'
        )
        app_title.pack()

        self.status_label = tk.Label(
            container,
            text="Macro Mode: OFF",
            font=('Segoe UI', 16),
            bg=COLORS["background"],
            fg=COLORS["text"]
        )
        self.status_label.pack(pady=(0, 20))

        button_frame = ttk.Frame(container, style='Main.TFrame')
        button_frame.pack(fill=tk.X, pady=(0, 20))

        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(4, weight=1)

        self.toggle_button = tk.Button(
            button_frame,
            text="Toggle Macro Mode",
            command=self.toggle_macro_mode,
            font=("Segoe UI", 10),
            bg=COLORS["success"],
            fg="white",
            relief="flat",
            width=15,
            height=2,
            cursor="hand2"
        )
        self.toggle_button.grid(row=0, column=1, padx=5)

        self.add_button = tk.Button(
            button_frame,
            text="Add New Macro",
            command=self.add_macro,
            font=("Segoe UI", 10),
            bg=COLORS["primary"],
            fg="white",
            relief="flat",
            width=15,
            height=2,
            cursor="hand2"
        )
        self.add_button.grid(row=0, column=2, padx=5)

        self.delete_button = tk.Button(
            button_frame,
            text="Delete Macro",
            command=self.delete_macro,
            font=("Segoe UI", 10),
            bg=COLORS["danger"],
            fg="white",
            relief="flat",
            width=15,
            height=2,
            cursor="hand2"
        )
        self.delete_button.grid(row=0, column=3, padx=5)

        self.macro_list = ttk.Treeview(
            container,
            columns=("Key", "Action Count", "Actions"),
            show="headings",
            height=10
        )
        self.macro_list.heading("Key", text="Key")
        self.macro_list.heading("Action Count", text="Action Count")
        self.macro_list.heading("Actions", text="Actions")
        self.macro_list.pack(fill=tk.BOTH, expand=True)

        self.update_macro_list()

        self.window.mainloop()

    def center_window(self):
        width = 900
        height = 700
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.window.geometry(f'{width}x{height}+{x}+{y}')

    def create_styles(self):
        style = ttk.Style()
        style.configure("Main.TFrame", background=COLORS["secondary_bg"])
        style.configure("AppTitle.TLabel", font=("Segoe UI", 22, "bold"), background=COLORS["secondary_bg"])

if __name__ == "__main__":
    MacroController()
