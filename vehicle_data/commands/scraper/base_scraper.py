import os
import pickle
from dataclasses import dataclass
import time

from redis_collections import Dict
from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import alog
from vehicle_data import settings


URL = "https://facebook.com"

@dataclass
class BaseScraper:
    driver: WebDriver = None
    driver_options: ChromeOptions = ChromeOptions()
    config: Dict = None
    headless: bool = True
    clear_cookies: bool = False


    def __post_init__(self):
        alog.info('### init scraper ###')

    def login(self):
        cookiesFile = './cookies.pkl'

        if os.path.exists(cookiesFile):
            if self.clear_cookies:
                os.remove(cookiesFile)
            else:
                cookies = pickle.load(open(cookiesFile, 'rb'))
                self.driver.get(URL)
                for cookie in cookies:
                    self.driver.add_cookie(cookie)
                self.driver.get(URL)

        if not os.path.exists(cookiesFile):
            email = settings.facebook_user
            password = settings.facebook_password
            self._login(email, password)

            time.sleep(30)

            pickle.dump(self.driver.get_cookies(), open(cookiesFile, 'wb'))

    def is_signed_in(self, VERIFY_LOGIN_ID=None):

        try:
            self.__find_element_by_class_name__(VERIFY_LOGIN_ID)
            return True
        except:
            pass
        return False

    def __find_element_by_class_name__(self, class_name):
        try:
            self.driver.find_element(By.CLASS_NAME, class_name)
            return True
        except:
            pass
        return False

    def __find_element_by_xpath__(self, tag_name):
        try:
            self.driver.find_element(By.XPATH,tag_name)
            return True
        except:
            pass
        return False

    def __find_enabled_element_by_xpath__(self, tag_name):
        try:
            elem = self.driver.find_element(By.XPATH,tag_name)
            return elem.is_enabled()
        except:
            pass
        return False

    @classmethod
    def __find_first_available_element__(cls, *args):
        for elem in args:
            if elem:
                return elem[0]
