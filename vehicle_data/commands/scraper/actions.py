import time
from dataclasses import dataclass
import alog
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from .scraper import Scraper
from vehicle_data import settings

REMEMBER_PROMPT = 'remember-me-prompt__form-primary'
VERIFY_LOGIN_ID = "global-nav__me-photo"

@dataclass
class MarketPlaceActions(Scraper):
    # def __prompt_email_password():
    #   u = input("Email: ")
    #   p = getpass.getpass(prompt="Password: ")
    #   return (u, p)
    #
    # def page_has_loaded(driver):
    #     page_state = driver.execute_script('return document.readyState;')
    #     return page_state == 'complete'

    def _login(self, email, password, timeout=10):
        driver = self.driver
        driver.get(f'{settings.URL}/login')

        WebDriverWait(driver, timeout)\
            .until(EC.presence_of_element_located((By.ID, "email")))

        email_elem = driver.find_element(By.ID, "email")

        email_elem.send_keys(email)

        password_elem = driver.find_element(By.ID, "pass")

        password_elem.send_keys(password)

        password_elem.submit()
