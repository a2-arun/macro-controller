import pynput
from config.settings import GLOBAL_HOTKEY

class HotkeyManager:
    def __init__(self, toggle_callback):
        self.listener = pynput.keyboard.GlobalHotKeys({GLOBAL_HOTKEY: toggle_callback})

    def start(self):
        self.listener.start()
