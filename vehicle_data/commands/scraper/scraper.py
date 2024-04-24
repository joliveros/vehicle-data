from vehicle_data import settings
from .base_scraper import BaseScraper
from dataclasses import dataclass
import alog
import os
import pickle

URL = "https://facebook.com"

@dataclass
class Scraper(BaseScraper):


    def _login(self):
        raise NotImplementedError()
