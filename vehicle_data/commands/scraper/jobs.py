from datetime import datetime

from django.conf import settings
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager

from .actions import LinkedInActions
from dataclasses import dataclass
from django.forms import model_to_dict
from functools import cached_property
from selenium.common import StaleElementReferenceException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from urllib.parse import urlencode
from .key_store import KeyStore
from selenium.webdriver.chrome.service import Service
from ....models.linkedin_job import \
    LinkedInJob, LinkedInOrgSector, LinkedInOrgLevel, LinkedInLaborCategory

import alog
import moment
import re
import time

from redis_collections import Dict


@dataclass
class Jobs(LinkedInActions, KeyStore):
    wait: bool = 30
    dry_run: bool = True
    reset_page_counter: bool = True

    def __post_init__(self):
        self.driver_options.headless = self.headless
        self.driver_options.add_argument('--headless')
        self.driver_options.add_argument('--no-sandbox')
        self.driver_options.add_argument('--disable-dev-shm-usage')

        self.driver = webdriver \
            .Chrome(
            # service=Service(ChromeDriverManager().install()),
            options=self.driver_options)

        self.config = Dict(key='linkedin_jobs', redis=self.redis_client)

        self.login()

        if self.reset_page_counter:
            self.config['last_start'] = 0

        keywords = ['python', 'javascript', 'typescript', 'react', 'react native', 'angular']
        keyword = keywords[0]

        if 'last_start' not in self.config:
            self.config['last_start'] = 0

        last_start = self.config['last_start']

        self.driver.get(self.jobs_url(start=last_start, keyword=keyword))

        # time.sleep(60 * 3)

        self.close_messaging()

        job_item_class = 'jobs-search-results__list-item'

        no_results = None

        try:
            no_results = self.driver.find_element(By.CLASS_NAME, 'jobs-search-no-results-banner__image')
        except NoSuchElementException:
            pass

        if no_results is not None:
            self.config['last_start'] = 0
            last_start = self.config['last_start']
            self.driver.get(self.jobs_url(start=last_start, keyword=keyword))

        results_remaining = self.results_count

        while results_remaining > 0:
            last_start = self.config['last_start']
            job_items = self.driver.find_elements(By.CLASS_NAME, job_item_class)
            page_size = len(job_items)

            scrape_count = 0

            for job_item in job_items:
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView();", job_item)
                    job_item.click()
                    time.sleep(2)
                    listing_url = self.listing_url(job_item)

                    if len(LinkedInJob.objects.filter(listing_url=listing_url)) == 0:
                        self.get_listing(listing_url)
                        scrape_count += 1
                        time.sleep(int(self.wait))

                except StaleElementReferenceException:
                    pass

                time.sleep(2)

            if scrape_count == 0 and last_start > 200:
                self.config['last_start'] = 0
                last_start = 0
                k_index = keywords.index(keyword)
                last_k = len(keywords) - 1

                if k_index == last_k:
                    keyword = keywords[0]
                else:
                    keyword = keywords[k_index + 1]

                # time.sleep(60 * 3)
            else:
                last_start = last_start + page_size
                _last_start = self.config['last_start']

                if last_start > _last_start:
                    self.config['last_start'] = last_start
                else:
                    self.config['last_start'] = _last_start + page_size

            self.driver.get(self.jobs_url(start=last_start, keyword=keyword))

            time.sleep(10)

        self.driver.close()

    def get_listing(self, listing_url):
            job = self.driver.find_element(By.CLASS_NAME, 'jobs-details__main-content')

            top_card = job.find_element(By.CLASS_NAME, 'job-details-jobs-unified-top-card__content--two-pane')

            title = top_card.find_element(By.CLASS_NAME, 'job-details-jobs-unified-top-card__job-title').text

            company_name = top_card.find_element(By.CLASS_NAME, 'job-details-jobs-unified-top-card__primary-description-without-tagline > a').text

            description = top_card.find_elements(By.CLASS_NAME, 'job-details-jobs-unified-top-card__primary-description-without-tagline > span')

            alog.info([span.text for span in description])
            created = [span.text for span in description][2]

            if 'Reposted' in created:
                created = created.replace('Reposted', '')

            alog.info(created)

            if len(created) > 0:
                created = moment.date(created).date.astimezone()
            else:
                created = datetime.now()

            applicant_count = self.applicant_count(top_card)
            job_insight = top_card.find_element(By.CLASS_NAME, 'job-details-jobs-unified-top-card__job-insight')

            salary = self.salary(job_insight)

            labor_category, level = self.category_and_level(job_insight)

            size_and_sector = top_card \
                .find_elements(By.CLASS_NAME, 'job-details-jobs-unified-top-card__job-insight')[1].text

            # time.sleep(60 * 2)

            size_and_sector = [val.strip() for val in size_and_sector.split('·')]

            size = self.company_size(size_and_sector)

            sector = self.sector(size_and_sector)

            cards = job.find_elements(By.CLASS_NAME, 'artdeco-card')

            hiring_person_url = self.hiring_person_url(cards)

            description = job.find_element(By.CLASS_NAME, 'jobs-description').get_attribute('innerHTML')

            company_url = self.company_url(job)

            listing_defaults = dict(applicant_count=applicant_count,
                                    company_name=company_name,
                                    created=created,
                                    description=description,
                                    company_url=company_url,
                                    hiring_person_url=hiring_person_url,
                                    labor_category=LinkedInLaborCategory.objects.get_or_create(name=labor_category)[0],
                                    level=LinkedInOrgLevel.objects.get_or_create(name=level)[0], listing_url=listing_url,
                                    salary_max=salary[1] if salary is not None else None,
                                    size_max=size[1] if size is not None else None,
                                    salary_min=salary[0] if salary is not None else None,
                                    size_min=size[0] if size is not None else None,
                                    sector=LinkedInOrgSector.objects.get_or_create(name=sector)[0], title=title)

            if not self.dry_run:
                listing, _ = LinkedInJob.objects\
                    .get_or_create(listing_url=listing_url, defaults=listing_defaults)

                alog.info(alog.pformat(model_to_dict(listing)))
            else:
                alog.info(alog.pformat(listing_defaults))

    def listing_url(self, job_item):
        listing_url = job_item.find_element(By.CLASS_NAME, 'job-card-container__link') \
            .get_attribute('href').split('?')[0]
        return listing_url

    def company_url(self, job):
        company_url = ''
        try:
            company_url = job.find_element(By.CLASS_NAME, 'jobs-company__box') \
                .find_element(By.CSS_SELECTOR, '.artdeco-entity-lockup__title a').get_attribute('href')
        except NoSuchElementException:
            pass
        return company_url

    def hiring_person_url(self, cards):
        hiring_person = [card for card in cards if 'Meet the hiring team' in card.text]
        hiring_person_url = None
        if len(hiring_person) > 0:
            hiring_person_url = hiring_person[0].find_element(By.CLASS_NAME, 'app-aware-link').get_attribute('href')
        return hiring_person_url

    def sector(self, size_and_sector):
        sector = ''
        if len(size_and_sector) > 1:
            sector = size_and_sector[1]
        return sector

    def company_size(self, size_and_sector):
        if len(size_and_sector) > 1:
            size = size_and_sector[0].replace('employees', '').strip()

            if '-' in size:
                size = [int(re.sub(r"\D", "", size)) for size in size.split('-')]
            if '+' in size:
                size = [int(re.sub(r"\D", "", size)), None]
            return size
        else:
            return [None, None]

    def salary(self, job_insight):
        salary = job_insight.text

        if '-' in salary:
            salary = salary.split('-')
            min = re.sub(r"\D", "", salary[0])
            max = re.sub(r"\D", "", salary[1])

            if len(min) == 0:
                min = 0

            if len(max) == 0:
                max = 0

            return [int(min), int(max)]
        else:
            return None

    def category_and_level(self, job_insight):
        span = job_insight.find_elements(By.CSS_SELECTOR, 'span')
        max_ix = len(span)

        level = span[max_ix - 1].text
        labor_category = span[max_ix - 2].text

        return labor_category, level

    def applicant_count(self, top_card):
        applicant_count = ''
        try:
            applicant_count = top_card \
                .find_element(By.CLASS_NAME, 'jobs-unified-top-card__applicant-count') \
                .text
        except NoSuchElementException:
            pass
        try:
            applicant_count = top_card \
                .find_element(By.CSS_SELECTOR,
                              '.jobs-unified-top-card__subtitle-secondary-grouping > .jobs-unified-top-card__bullet') \
                .text
        except NoSuchElementException:
            pass
        applicant_count = re.sub(r"\D", "", applicant_count)
        if len(applicant_count) == 0:
            applicant_count = 0

        return int(applicant_count)

    def jobs_url(self, keyword, start=0):
        jobs_url = 'https://www.linkedin.com/jobs/search/'
        query_params = dict(
            keywords=keyword,
            location='United States'
        )

        if start > 0:
            query_params['start'] = start

        jobs_url += f'?{urlencode(query_params)}'

        return jobs_url

    @cached_property
    def results_count(self):
        results_count = self.driver \
            .find_element(By.CSS_SELECTOR,
                          '.jobs-search-results-list__title-heading > small.jobs-search-results-list__text').text
        results_count = re.sub(r"\D", "", results_count)
        return int(results_count)

    def close_messaging(self):
        self.wait_until_class_presence('.msg-overlay-bubble-header__control')
        time.sleep(1)

        messaging_open = self.driver.find_element(By.CSS_SELECTOR, '[data-test-icon="chevron-down-small"]')

        if messaging_open:
            messaging_open.click()

    def wait_until_class_presence(self, job_item_class, timeout=4):
        WebDriverWait(self.driver, timeout) \
            .until(EC.presence_of_element_located((By.CSS_SELECTOR, job_item_class)))
