"""Construccion del driver y login (Selenium). Productivizado de sync_dryrun.py."""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


def build_driver(headless=False, base_dir="."):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--start-maximized")
    options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.notifications": 2,
        "download.default_directory": base_dir,
        "download.prompt_for_download": False,
    })
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def login(driver, base_url, email, password):
    base_url = base_url.rstrip("/")
    driver.get(f"{base_url}/login")
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.ID, "member_email"))).send_keys(email)
    driver.find_element(By.ID, "member_password").send_keys(password)
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    time.sleep(6)
    if "login" not in driver.current_url:
        return True
    # Posible 2FA/captcha: dar margen a resolverlo en la ventana
    time.sleep(20)
    return "login" not in driver.current_url
