import os, subprocess, webbrowser
from tkinter import messagebox
from automation.web_automation import handle_web_action

class ActionHandler:
    def __init__(self, credential_manager):
        self.credential_manager = credential_manager

    def execute_macro(self, actions):
        for command in actions:
            if command.startswith(("http://", "https://", "www.")):
                self.open_web(command)
            else:
                self.open_command(command)

    def open_web(self, url: str):
        if url.startswith("www."): url = "https://" + url
        credentials = self.credential_manager.get_credentials(url)
        if credentials:
            handle_web_action(url, credentials)
        else:
            webbrowser.open(url)

    def open_command(self, command: str):
        try:
            if command.startswith(("http://", "https://", "www.")):
                webbrowser.open(command)
                return
            if os.name == "nt":
                subprocess.Popen(command, shell=True)
            else:
                subprocess.Popen([command], shell=True)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to execute {command}: {e}")
