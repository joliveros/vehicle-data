import urllib
from .actions import MarketPlaceActions
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from redis import Redis
from redis_collections import Dict, Set
from selenium import webdriver
from selenium.common import StaleElementReferenceException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from urllib.parse import urlencode
from vehicle_data import settings
from webdriver_manager.chrome import ChromeDriverManager

import alog
import dateparser
import moment
import re
import time
from prisma import Prisma

redis = Redis(host=settings.REDIS_HOST, port=6379, db=0)


def find_idx(s, ch):
    return [i for i, ltr in enumerate(s) if ltr == ch]


@dataclass
class Cars(MarketPlaceActions):
    wait: bool = 30
    dry_run: bool = True
    reset_page_counter: bool = True

    def __post_init__(self):

        if self.headless:
            self.driver_options.add_argument('--headless')

        self.listing_urls = Set(key='listing_urls', redis=redis)

        self.db = Prisma()
        self.db.connect()

        self.driver_options.add_argument('--no-sandbox')
        self.driver_options.add_argument("--disable-notifications")
        self.driver_options.add_argument('--disable-dev-shm-usage')

        self.driver = webdriver \
            .Chrome(
            service=Service(ChromeDriverManager().install()),
            options=self.driver_options)

        self.login()

        cities = ['tijuana', 'mexicali', 'zapopan']
        makes = ['ford', 'volkswagen', 'chevrolet', 'dodge', 'toyota', 'honda', 'nissan']
        years = ['2017', '2016', '2015']

        while True:
            for city in cities:
                for make in makes:
                    for year in years:
                        self.get_listings_for_query(f'{year} {make}', city)

        time.sleep(5)

        self.driver.close()

    def get_listings_for_query(self, value, city):
        query = dict(query=value)
        query_str = urllib.parse.urlencode(query, doseq=False)
        self.driver.get(f'{settings.URL}/marketplace/{city}/search?{query_str}')
        time.sleep(2)
        self.get_preliminary_listing()
        alog.info(len(self.listing_urls))

        while len(self.listing_urls) > 0:
            listing_data = dict()
            
            url = self.listing_urls.pop()

            alog.info(url)

            listing_data['url'] = url

            id = re.findall("https:\/\/www\.facebook\.com\/marketplace\/item\/(\d+)\/", url)[0]

            vehicle = self.db.vehicle.find_unique(where=dict(id=id))

            if not vehicle:
                self.get_listing_details(id, listing_data, url)
                time.sleep(5)

    def get_listing_details(self, id, listing_data, url):
        listing_data['id'] = id
        self.driver.get(url)
        time.sleep(2)

        el = self.driver.find_elements(By.XPATH,
                                      '/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div[2]/div/div/div/div/div/div[1]/div[2]/div/div[2]/div')

        if len(el) == 0:
            return
        else:
            el = el[0]

        # alog.info(el.text)
        make_model = el.find_element(By.CSS_SELECTOR, 'h1').text

        year_re = re.findall("\d{4,}", make_model)
        if len(year_re) > 0:
            listing_data['year'] = int(year_re[0])
        else:
            listing_data['year'] = 0

        space_ix = find_idx(make_model, ' ')
        if len(space_ix) > 1:
            listing_data['make'] = make_model[space_ix[0] + 1:space_ix[1]]
            listing_data['model'] = make_model[space_ix[1] + 1:]
        el = el.find_element(By.XPATH,
                             '/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div[2]/div/div/div/div/div/div[1]/div[2]/div/div[2]/div/div[1]/div[1]/div[1]')
        try:
            price = el.find_element(By.XPATH, './div[2]').text
            alog.info(price)
            price = int(''.join(re.findall("\d", price)))

            if price < 999:
                price = price * 1000
            if price >= 9999999:
                price = 0

            listing_data['price'] = price
        except:
            listing_data['price'] = 0
        listed_str = el.find_element(By.XPATH, './div[3]').text
        # alog.info(el.get_attribute('outerHTML'))
        where_listed_re = re.findall("^Listed .* ago in (.*)", listed_str)

        if len(where_listed_re) > 0:
            listing_data['city'] = where_listed_re[0]
            listed = re.findall("^Listed (.* ago).*", listed_str)[0]
            listing_data['created_at'] = dateparser.parse(listed)
        else:
            listing_data['city'] = ''

        # alog.info(el.find_element(By.XPATH, './div[4]').text)
        el = el.find_elements(By.XPATH,
                              '/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div[2]/div/div/div/div/div/div[1]/div[2]/div/div[2]/div/div[1]/div[1]/div[5]')
        if len(el) > 0:
            el = el[0]

            try:
                listing_data['transmission'] = el.find_element(By.XPATH, './div/div[2]').text
            except:
                pass

            try:
                listing_data['color'] = el.find_element(By.XPATH, './div/div[3]').text
            except:
                pass

            try:
                listing_data['fuel_type'] = el.find_element(By.XPATH, './div/div[4]') \
                    .text.split(':')[-1].strip()
            except:
                pass

            try:
                listing_data['engine_size'] = el.find_element(By.XPATH, './div/div[5]') \
                    .text.split(':')[-1].strip()
            except:
                pass

            self.see_more()

            try:
                el = el.find_element(By.XPATH,
                                     '/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div[2]/div/div/div/div/div/div[1]/div[2]/div/div[2]/div/div[1]/div[1]/div[6]/div[2]/div/div[1]/div/span')

                listing_data['description'] = el.text[:999]
            except:
                listing_data['description'] = 'none'

            try:
                el = el.find_element(By.XPATH,
                                     '/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div[2]/div/div/div/div/div/div[1]/div[2]/div/div[2]/div/div[1]/div[1]/div[7]/div/div[2]/div[1]/div/div/div/div/div[2]/div/div/div/div/span/span/div/div/a')

                profile_url = el.get_attribute('href')

                alog.info(profile_url)

                listing_data['profile_url'] = \
                    re.findall("^(https:\/\/www\.facebook\.com\/marketplace\/profile\/\d+\/).*", profile_url)[0]
            except:
                pass
        el = self.driver.find_elements(By.XPATH,
                                       '/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div[2]/div/div/div/div/div/div[1]/div[2]/div/div[1]/div/div[3]/div/div')
        images = []
        for e in el:
            images.append(dict(url=e.find_element(By.CSS_SELECTOR, 'img').get_attribute('src')))
        data = dict(
            create=dict(**listing_data),
            update=dict(**listing_data)
        )
        self.db.vehicle.upsert(where=dict(id=id), data=data)
        for image in images:
            url = image['url']
            self.db.facebookimage.upsert(
                where=dict(url=url),
                data=dict(
                    create=dict(url=url, vehicles=dict(connect=dict(id=id))),
                    update=dict(url=url, vehicles=dict(connect=dict(id=id))),
                ))

        # time.sleep(2)

    def see_more(self):
        el = self.driver.find_elements(By.XPATH,
                                       '/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div[2]/div/div/div/div/div/div[1]/div[2]/div/div[2]/div/div[1]/div[1]/div[6]/div[2]/div/div[1]/div/span/div/span')
        if len(el) > 0:
            el[0].click()

    def get_preliminary_listing(self):
        last_num_listings = 0

        while True:
            el = self.driver.find_elements(
                By.CSS_SELECTOR,
                'div[aria-label="Collection of Marketplace items"] > div > div > div > div:nth-child(1) > div > div > div > div > span')

            if last_num_listings == len(el):
                break

            last_num_listings = len(el)

            for e in el:
                anchors = e.find_elements(By.CSS_SELECTOR, 'a')
                if len(anchors) > 0:
                    url = anchors[0].get_attribute('href')

                    sanitized_url = re.findall(r"https:\/\/www\.facebook\.com\/marketplace\/item\/\d+\/", url)[0]

                    self.listing_urls.add(sanitized_url)

            self.driver.execute_script("arguments[0].scrollIntoView();", el[-1])

            time.sleep(2)

    def search(self, value, timeout=10):
        driver = self.driver
        # <input dir="ltr" aria-autocomplete="list" aria-expanded="true" aria-label="Search Marketplace" role="combobox" placeholder="Search Marketplace" autocomplete="off" spellcheck="false" aria-invalid="false" class="x1i10hfl xggy1nq x1s07b3s x1kdt53j x1yc453h xhb22t3 xb5gni xcj1dhv x2s2ed0 xq33zhf xjyslct xjbqb8w xnwf7zb x40j3uw x1s7lred x15gyhx8 x972fbf xcfux6l x1qhh985 xm0m39n x9f619 xzsf02u xdl72j9 x1iyjqo2 xs83m0k xjb2p0i x6prxxf xeuugli x1a2a7pz x1n2onr6 x15h3p50 xm7lytj xsyo7zv xdvlbce x16hj40l xc9qbxq xo6swyp x1ad04t7 x1glnyev x1ix68h3 x19gujb8" type="search" value="2017" aria-controls=":r3:">

        el = driver.find_element(By.CSS_SELECTOR, 'input[aria-label="Search Marketplace"]')

        el.send_keys(value)

        el.submit()

    def get_listing(self, listing_url):
        job = self.driver.find_element(By.CLASS_NAME, 'jobs-details__main-content')

        top_card = job.find_element(By.CLASS_NAME, 'job-details-jobs-unified-top-card__content--two-pane')

        title = top_card.find_element(By.CLASS_NAME, 'job-details-jobs-unified-top-card__job-title').text

        company_name = top_card.find_element(By.CLASS_NAME,
                                             'job-details-jobs-unified-top-card__primary-description-without-tagline > a').text

        description = top_card.find_elements(By.CLASS_NAME,
                                             'job-details-jobs-unified-top-card__primary-description-without-tagline > span')

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
            listing, _ = LinkedInJob.objects \
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
