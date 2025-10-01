
import os
import pynput
import json
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Dict, List, Optional
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Constants
MACROS_FILE = "macros.json"
CREDENTIALS_FILE = "credentials.enc"
SALT_FILE = "salt.bin"
COLORS = {
    "primary": "#007ACC",
    "success": "#28A745",
    "warning": "#FFC107",
    "background": "#f3f3f3",
    "secondary_bg": "#e9ecef",
    "text": "#2b2b2b",
    "danger": "#DC3545",
    "border": "#CED4DA"
}

class CredentialManager:
    def __init__(self):
        self.key = self._get_or_create_key()
        self.fernet = Fernet(self.key)
        self.credentials = self._load_credentials()

    def _get_or_create_key(self) -> bytes:
        if not os.path.exists(SALT_FILE):
            salt = os.urandom(16)
            with open(SALT_FILE, 'wb') as f:
                f.write(salt)
        else:
            with open(SALT_FILE, 'rb') as f:
                salt = f.read()

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(b"macro_controller_key"))
        return key

    def _load_credentials(self) -> Dict[str, Dict[str, str]]:
        if not os.path.exists(CREDENTIALS_FILE):
            return {}
        
        try:
            with open(CREDENTIALS_FILE, 'rb') as f:
                encrypted_data = f.read()
                decrypted_data = self.fernet.decrypt(encrypted_data)
                return json.loads(decrypted_data)
        except Exception:
            return {}

    def save_credentials(self) -> None:
        encrypted_data = self.fernet.encrypt(json.dumps(self.credentials).encode())
        with open(CREDENTIALS_FILE, 'wb') as f:
            f.write(encrypted_data)

    def add_credentials(self, url: str, username: str, password: str) -> None:
        self.credentials[url] = {
            'username': username,
            'password': password
        }
        self.save_credentials()

    def get_credentials(self, url: str) -> Optional[Dict[str, str]]:
        return self.credentials.get(url)

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

class AddActionDialog(tk.Toplevel):
    def __init__(self, parent, credential_manager):
        super().__init__(parent)
        self.parent = parent
        self.credential_manager = credential_manager
        self.result = None
        self.credentials = None
        
        self.title("Add Action")
        self.geometry("400x300")
        self.resizable(False, False)
        
        self.create_widgets()
        self.center_window()

    def create_widgets(self):
        # URL Entry
        ttk.Label(self, text="Enter app/URL for this macro (Leave blank to stop):",
                 wraplength=350).pack(pady=10, padx=20)
        self.url_entry = ttk.Entry(self, width=40)
        self.url_entry.pack(pady=5, padx=20)

        # Credentials Frame (initially hidden)
        self.cred_frame = ttk.Frame(self)
        ttk.Label(self.cred_frame, text="Username:").pack(pady=5)
        self.username_entry = ttk.Entry(self.cred_frame, width=40)
        self.username_entry.pack(pady=5)
        
        ttk.Label(self.cred_frame, text="Password:").pack(pady=5)
        self.password_entry = ttk.Entry(self.cred_frame, width=40, show="*")
        self.password_entry.pack(pady=5)

        # Add Credentials Button
        self.cred_button = ttk.Button(
            self,
            text="Add Credentials",
            command=self.toggle_credentials
        )
        self.cred_button.pack(pady=10)

        # OK/Cancel Buttons
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=20, side=tk.BOTTOM)
        
        ttk.Button(button_frame, text="OK", command=self.ok_clicked).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Cancel", command=self.cancel_clicked).pack(side=tk.LEFT)

    def toggle_credentials(self):
        if self.cred_frame.winfo_ismapped():
            self.cred_frame.pack_forget()
            self.geometry("400x300")
        else:
            self.cred_frame.pack(pady=10)
            self.geometry("400x400")

    def ok_clicked(self):
        url = self.url_entry.get().strip()
        if url:
            self.result = url
            if self.cred_frame.winfo_ismapped():
                username = self.username_entry.get().strip()
                password = self.password_entry.get().strip()
                if username and password:
                    self.credential_manager.add_credentials(url, username, password)
        self.destroy()

    def cancel_clicked(self):
        self.result = None
        self.destroy()

    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

class MacroController:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.is_macro_mode = False
        self.credential_manager = CredentialManager()
        self.macros: Dict[str, List[str]] = self.load_macros()
        self.keyboard_listener = None
        self.create_gui()
        self.setup_global_hotkey()

    def load_macros(self) -> Dict[str, List[str]]:
        try:
            if os.path.exists(MACROS_FILE):
                with open(MACROS_FILE, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load macros: {e}")
            return {}

    def save_macros(self) -> None:
        try:
            with open(MACROS_FILE, 'w') as f:
                json.dump(self.macros, f, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save macros: {e}")

    def on_key_press(self, key) -> None:
        if not self.is_macro_mode:
            return

        try:
            key_char = key.char if hasattr(key, 'char') else str(key)
            if key_char in self.macros:
                self.execute_macro(key_char)
        except AttributeError:
            pass

    def toggle_macro_mode(self) -> None:
        self.is_macro_mode = not self.is_macro_mode
        status = "ON" if self.is_macro_mode else "OFF"

        if self.is_macro_mode:
            if not self.keyboard_listener:
                self.keyboard_listener = pynput.keyboard.Listener(on_press=self.on_key_press)
                self.keyboard_listener.start()
        else:
            if self.keyboard_listener:
                self.keyboard_listener.stop()
                self.keyboard_listener = None

        self.status_label.config(
            text=f"Macro Mode: {status}",
            foreground=COLORS["warning"] if self.is_macro_mode else COLORS["text"]
        )
        self.toggle_button.config(
            bg=COLORS["warning"] if self.is_macro_mode else COLORS["success"]
        )

    def execute_macro(self, key: str) -> None:
        if key in self.macros:
            for command in self.macros[key]:
                if any(command.startswith(prefix) for prefix in ['http://', 'https://', 'www.']):
                    self.handle_web_action(command)
                else:
                    self.open_command(command)

    def handle_web_action(self, url: str) -> None:
        if url.startswith('www.'):
            url = 'https://' + url
            
        credentials = self.credential_manager.get_credentials(url)
        if credentials:
            try:
                driver = webdriver.Chrome()  # You might want to add options for headless mode
                driver.get(url)
                
                # Wait for and fill username field
                username_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'], input[type='email']"))
                )
                username_field.send_keys(credentials['username'])
                
                # Fill password field
                password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                password_field.send_keys(credentials['password'])
                
                # Submit form
                password_field.submit()
                
                # Keep the browser window open
                input("Press Enter to close the browser...") #Added this line to keep the browser open
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to automate login: {e}")
                
            finally:
                if 'driver' in locals():
                    driver.quit()
        else:
            import webbrowser
            webbrowser.open(url)

    def open_command(self, command: str) -> None:
        try:
            if any(command.startswith(prefix) for prefix in ['http://', 'https://', 'www.']):
                if command.startswith('www.'):
                    command = 'https://' + command
                import webbrowser
                webbrowser.open(command)
                return

            import subprocess
            if os.name == 'nt':  # Windows
                try:
                    subprocess.Popen(command, shell=True)
                except Exception:
                    os.startfile(command)
            else:  # Non-Windows
                subprocess.Popen([command], shell=True)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to execute {command}: {e}")

    def add_macro(self) -> None:
        macro_key = self.ask_string("Enter Macro Key", "Enter the key for this macro:")
        if macro_key:
            actions = []
            while True:
                dialog = AddActionDialog(self.root, self.credential_manager)
                self.root.wait_window(dialog)
                action = dialog.result
                if not action:
                    break
                actions.append(action)

            if actions:
                self.macros[macro_key] = actions
                self.save_macros()
                self.update_macro_list()
                messagebox.showinfo("Success", f"Macro with key '{macro_key}' added.")
            else:
                messagebox.showinfo("Cancel", "No actions added. Macro creation canceled.")

    def delete_macro(self) -> None:
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

    def update_macro_list(self) -> None:
        self.macro_list.delete(*self.macro_list.get_children())
        for key, actions in self.macros.items():
            self.macro_list.insert(
                '',
                'end',
                values=(key, len(actions), ", ".join(actions))
            )

    def ask_string(self, title: str, prompt: str) -> str:
        dialog = CustomDialog(self.root, title, prompt)
        return dialog.result

    def create_gui(self) -> None:
        self.root.title("Macro Controller")
        self.root.geometry("900x700")
        self.root.configure(bg=COLORS["background"])

        self.center_window()
        self.create_styles()

        container = ttk.Frame(self.root, style='Main.TFrame')
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

        # Uniform button size for all buttons
        button_width = 20
        button_height = 2

        self.toggle_button = tk.Button(
            button_frame,
            text="Toggle Macro Mode",
            command=self.toggle_macro_mode,
            font=("Segoe UI", 12),
            bg=COLORS["success"],
            fg="white",
            relief="flat",
            width=button_width,
            height=button_height,
            cursor="hand2"
        )
        self.toggle_button.grid(row=0, column=1, padx=5)

        self.add_button = tk.Button(
            button_frame,
            text="Add New Macro",
            command=self.add_macro,
            font=("Segoe UI", 12),
            bg=COLORS["primary"],
            fg="white",
            relief="flat",
            width=button_width,
            height=button_height,
            cursor="hand2"
        )
        self.add_button.grid(row=0, column=2, padx=5)

        self.delete_button = tk.Button(
            button_frame,
            text="Delete Macro",
            command=self.delete_macro,
            font=("Segoe UI", 12),
            bg=COLORS["danger"],
            fg="white",
            relief="flat",
            width=button_width,
            height=button_height,
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

    def create_styles(self) -> None:
        style = ttk.Style(self.root)
        style.configure('Main.TFrame', background=COLORS["background"])
        style.configure('AppTitle.TLabel', font=("Segoe UI", 24), background=COLORS["background"], foreground=COLORS["primary"])

    def center_window(self) -> None:
        window_width = 900
        window_height = 700
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        x = int((screen_width / 2) - (window_width / 2))
        y = int((screen_height / 2) - (window_height / 2))

        self.root.geometry(f'{window_width}x{window_height}+{x}+{y}')

    def setup_global_hotkey(self) -> None:
        # Use `Ctrl + Alt + M` as the hotkey for toggling macro mode
        listener = pynput.keyboard.GlobalHotKeys({
            '<ctrl>+<alt>+m': self.toggle_macro_mode
        })
        listener.start()


if __name__ == "__main__":
    root = tk.Tk()
    app = MacroController(root)
    root.mainloop()
