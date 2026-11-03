import random
import time
from urllib.parse import urljoin

from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


class ClassScout:
    """
    Scraper for "StrefaZajec.pl"

    Reuses one HTTP (connection pooling) for all requests and
    downloads course listing and detail pages.
    """

    def __init__(self):
        # Base URL for the paginated course search results.
        self.courses_url = "https://www.strefazajec.pl/course"

        # Use a browser-like User-Agent for standard HTTP requests.
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/151.0.0.0 Safari/537.36"
        }

        # Create one persistent session and attach the headers to every request.
        self.session = Session()
        self.session.headers.update(self.headers)

        # Retry connection errors, timeouts, temporary server errors (429, 5xx) up to 3 times with increasing,
        # randomized delays between attempts.
        retry = Retry(
            total=3,
            backoff_factor=1,
            backoff_jitter=1,
            status_forcelist=(429, 500, 502, 503, 504),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)

    def fetch_page(self, url: str, params: dict | None = None) -> str:
        """
        Pause briefly to avoid overloading the server, then download the HTML of a page.

        Args:
            url (str): The web address to download.
            params (dict, optional): Dictionary of query parameters to attach to the URL.
                                     Defaults to None.

        Returns:
            str: The raw HTML text of the requested page.

        Raises:
            requests.exceptions.HTTPError: If the server responds with 4xx or 5xx status code
                (after retries for 429 and 5xx).
            requests.exceptions.RequestException: For other network problems,
                such as connection errors or timeouts.
        """
        time.sleep(random.uniform(0.8, 2.0))
        # (connect, read) timeouts: connecting normally takes well under a second,
        # so 5 s is plenty; the server usually starts sending the page within
        # about 1 s, so 15 s leaves a wide margin.
        response = self.session.get(url=url, params=params, timeout=(5, 15))
        response.raise_for_status()
        return response.text

    def scrape_listings(self, city_name: str, city_id: int, parser) -> list[dict]:
        """
        Scrapes all listing pages for a selected city and collects course data.

        Args:
            city_name (str): Name of the selected city.
            city_id (int): Internal StrefaZajec city ID.
            parser (CourseParser): Parser used to extract courses and pagination.

        Returns:
            list[dict]: Course records collected from all listing pages.
        """
        current_url = self.courses_url

        search_params = {
            "city_name": city_name,
            "city_id": city_id,
        }

        courses = []

        while True:
            html = self.fetch_page(current_url, params=search_params)

            page_courses = parser.parse_listing_page(html)
            courses.extend(page_courses)

            # The parser only identifies the relative next-page URL.
            next_page = parser.find_next_page(html)

            if next_page is None:
                break

            current_url = urljoin(current_url, next_page)

            search_params = None

        return courses

    def scrape_course_details(self, courses: list[dict], parser) -> list[dict]:
        """
        Fetch and parse the detail page for each course.

        Args:
            courses (list[dict]): Course records from the listing pages.
            parser (CourseParser): Parser used to extract detail information.

        Returns:
                list[dict]: Courses enriched with detail-page information.
        """

        for course in courses:
            # Convert the relative course URL into the canonical absolute URL.
            course_url = urljoin(self.courses_url, course["url"])

            # Update the course record with the absolute URL.
            course["url"] = course_url
            course_html = self.fetch_page(url=course_url)

            # Pass the course URL as context so the parser can resolve relative links found inside the detail page.
            course_details = parser.parse_course_page(
                html=course_html, base_url=course_url
            )

            # Add the detail-page fields to the existing listing record.
            course.update(course_details)

        return courses
