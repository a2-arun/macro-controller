import webbrowser
import subprocess
import keyboard

macro_mode = False

def toggle_macro_mode():
    global macro_mode
    macro_mode = not macro_mode
    print("Macro Mode:", "ON" if macro_mode else "OFF")  # Confirm toggle status
    if macro_mode:
        print("Macro Mode activated. Use 'W', 'C', or 'R'.")
    else:
        print("Exited Macro Mode.")

def open_work_apps():
    print("Opening Work Apps...")
    webbrowser.open("https://web.whatsapp.com")
    webbrowser.open("https://your-university-email.com")
    webbrowser.open("https://your-university-website.com")
    webbrowser.open("https://teams.microsoft.com")

def open_code_apps():
    print("Opening Code Apps...")
    subprocess.Popen(["code"])  # Assuming "code" opens VSCode
    webbrowser.open("https://github.com")

def open_research_apps():
    print("Opening Research Apps...")
    webbrowser.open("https://scholar.google.com")
    webbrowser.open("https://docs.google.com")

def macro_mode_listener(event):
    if event.name == 'w':
        open_work_apps()
    elif event.name == 'c':
        open_code_apps()
    elif event.name == 'r':
        open_research_apps()

# Assign Ctrl + Alt + M to toggle macro mode
keyboard.add_hotkey("ctrl+alt+m", toggle_macro_mode)

print("Press Ctrl+Alt+M to enter Macro Mode. Press again to exit.")

while True:
    if macro_mode:
        keyboard.on_press(macro_mode_listener)
    else:
        keyboard.unhook_all()
