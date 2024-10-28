import keyboard
import webbrowser
import time

# URLs for opening multiple websites
urls = {
    "W": ["https://mail.college.edu", "https://college.edu", "https://chat.openai.com", "https://web.whatsapp.com"]
}

# Flag for macro mode
macro_mode = False

# Function to open assigned URLs
def open_urls(url_list):
    for url in url_list:
        webbrowser.open(url)

# Define the macro toggle function
def toggle_macro_mode():
    global macro_mode
    macro_mode = not macro_mode
    print(f"Macro mode {'enabled' if macro_mode else 'disabled'}.")

# Listen for the macro mode activation
keyboard.add_hotkey("ctrl+shift+m", toggle_macro_mode)

# Listen for specific keys in macro mode
def on_key(event):
    global macro_mode
    if macro_mode and event.name.upper() in urls:
        open_urls(urls[event.name.upper()])

# Register the key press event
keyboard.on_press(on_key)

# Keep the script running
keyboard.wait("esc")  # Press "Esc" to exit the program
