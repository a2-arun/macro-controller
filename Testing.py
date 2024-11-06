from pynput import keyboard
import webbrowser
import os
import tkinter as tk
from tkinter import messagebox

# Initial setup for macro mode
is_macro_mode = False
macros = {
    'w': [
        "https://web.whatsapp.com/",
        "https://mail.google.com/",
        "https://vtopcc.vit.ac.in/vtop/login",
        r""
        
    ],
    'c': [
        "code",  # Assuming VSCode is in your PATH
        "https://github.com/"
    ],
    'r': [
        "https://scholar.google.com",
        "https://docs.google.com/"
    ]
}

# Track which keys are currently pressed
current_keys = set()

def toggle_macro_mode():
    global is_macro_mode
    is_macro_mode = not is_macro_mode
    status_label.config(text="Macro Mode: ON" if is_macro_mode else "Macro Mode: OFF")
    print("Macro Mode Toggled:", "ON" if is_macro_mode else "OFF")

def on_press(key):
    try:
        # Add keys to the set when pressed
        if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
            current_keys.add("ctrl")
        elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
            current_keys.add("alt")
        elif hasattr(key, 'char') and key.char == 'm':
            current_keys.add("m")
        
        # Check if Ctrl + Alt + M are all pressed
        if "ctrl" in current_keys and "alt" in current_keys and "m" in current_keys:
            toggle_macro_mode()
            current_keys.clear()  # Clear to avoid repeated toggling

        # Execute macros if in macro mode
        elif is_macro_mode and hasattr(key, 'char') and key.char in macros:
            execute_macro(key.char)
    except AttributeError:
        pass

def on_release(key):
    # Remove keys from the set when released
    if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
        current_keys.discard("ctrl")
    elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
        current_keys.discard("alt")
    elif hasattr(key, 'char') and key.char == 'm':
        current_keys.discard("m")

def execute_macro(key):
    for command in macros[key]:
        open_command(command)

def open_command(command):
    try:
        if command.startswith("http"):
            webbrowser.open(command)
        else:
            os.system(command)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open {command}: {e}")

# Set up the GUI
def create_gui():
    global status_label
    window = tk.Tk()
    window.title("Macro Mode Controller")
    window.geometry("300x200")
    
    # Status label
    status_label = tk.Label(window, text="Macro Mode: OFF", font=("Arial", 14))
    status_label.pack(pady=10)
    
    # Buttons to toggle macro mode
    toggle_button = tk.Button(window, text="Toggle Macro Mode", command=toggle_macro_mode, font=("Arial", 12))
    toggle_button.pack(pady=10)

    # Instructions
    instructions = tk.Label(window, text="Press 'w', 'c', or 'r' for macros\n(Ctrl + Alt + M to toggle mode)", font=("Arial", 10))
    instructions.pack(pady=10)
    
    # Start listener
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    
    # Start the GUI event loop
    window.mainloop()

# Run the GUI
create_gui()