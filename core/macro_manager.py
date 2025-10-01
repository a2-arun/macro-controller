import os, json
from typing import Dict, List
from tkinter import messagebox
from config.constants import MACROS_FILE

class MacroManager:
    def __init__(self):
        self.macros: Dict[str, List[str]] = self.load_macros()

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
