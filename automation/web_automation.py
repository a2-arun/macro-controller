from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tkinter import messagebox

def handle_web_action(url: str, credentials: dict):
    try:
        driver = webdriver.Chrome()
        driver.get(url)
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'], input[type='email']"))
        )
        username_field.send_keys(credentials['username'])
        password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        password_field.send_keys(credentials['password'])
        password_field.submit()
        input("Press Enter to close browser...")
    except Exception as e:
        messagebox.showerror("Error", f"Failed login automation: {e}")
    finally:
        if 'driver' in locals():
            driver.quit()
