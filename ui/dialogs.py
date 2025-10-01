import tkinter as tk
from tkinter import simpledialog, ttk

class CustomDialog(simpledialog.Dialog):
    def __init__(self, parent, title, prompt):
        self.prompt = prompt
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text=self.prompt).grid(row=0, padx=5, pady=5)
        self.entry = ttk.Entry(master, width=40)
        self.entry.grid(row=1, padx=5, pady=5)
        return self.entry

    def apply(self):
        self.result = self.entry.get()

class AddActionDialog(tk.Toplevel):
    def __init__(self, parent, credential_manager):
        super().__init__(parent)
        self.credential_manager = credential_manager
        self.result = None
        self.title("Add Action")
        self.geometry("400x300")
        ttk.Label(self, text="Enter URL/App:").pack(pady=10)
        self.url_entry = ttk.Entry(self, width=40)
        self.url_entry.pack()
        ttk.Button(self, text="OK", command=self.ok_clicked).pack(pady=10)

    def ok_clicked(self):
        url = self.url_entry.get().strip()
        if url:
            self.result = url
        self.destroy()
