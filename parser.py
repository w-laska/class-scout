from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

# Maps Polish website labels to our internal field names.
SIDEBAR_FIELD_MAP = {
    # Dates & duration
    "Data rozpoczęcia": "start_date",
    "Data zakończenia": "end_date",
    "Czas trwania": "duration",
    # Location & organization
    "Organizator": "organizer",
    "Filia": "branch",
    "Nazwa grupy": "group_name",
    # Class specifications
    "Poziom": "level",
}

# Fields where the website value should be converted to an integer.
NUMERIC_FIELD_MAP = {
    "Wiek od": "age_from",
    "Wiek do": "age_to",
    "Wolnych miejsc": "available_spots",
    "Liczba uczestników": "participants_count",
}


class CourseParser:
    """
    Parses HTML from StrefaZajec.pl and extracts course information.
    """

    def parse_listing_page(self, html: str) -> list[dict]:
        """
        Parse a listing page and return all valid course records found on it.

        Args:
            html (str): HTML content of the listing page.

        Returns:
            list[dict]: Course records containing listing information.
        """
        soup = BeautifulSoup(html, "html.parser")

        course_records = soup.find_all("div", class_="course-record")

        courses = []

        for record in course_records:
            course = self.parse_course_card(record)

            if course is not None:
                courses.append(course)

        return courses

    def parse_course_card(self, record: Tag) -> dict | None:
        """
        Extract basic course information from one listing card.

        Args:
            record (Tag): BeautifulSoup element representing one course card.

        Returns:
            dict | None: Course listing data, or None if required data is missing.
        """

        type_element = record.select_one(".course-type a")

        # Type is optional, so keep the course even when it is not available.
        course_type = type_element.get_text(strip=True) if type_element else None

        icon_calendar = record.select_one(".fa-calendar")

        # Date is required for the first-pass filtering step.
        if not icon_calendar:
            return None

        raw_date = icon_calendar.parent.get_text()
        raw_date = raw_date.replace("Termin:", "").strip()

        # Normalize repeated whitespace in the raw date text.
        raw_date = " ".join(raw_date.split())

        course_link = record.select_one("h3.title a.link-hover")

        if not course_link:
            return None

        course_title = course_link.get_text(strip=True)

        # Keep the URL relative here; ClassScout converts it to an absolute URL.
        relative_url = course_link.get("href")

        # A course without a URL cannot proceed to detail-page scraping.
        if not relative_url:
            return None

        return {
            "title": course_title,
            "type": course_type,
            "raw_date": raw_date,
            "url": relative_url,
        }

    def find_next_page(self, html: str) -> str | None:
        """
        Find the relative URL of the next pagination page.

        Args:
            html (str): HTML content of the current listing page.

        Returns:
            str | None: Relative URL of the next page, or None if there is no next page.
        """
        soup = BeautifulSoup(html, "html.parser")

        pagination = soup.find("div", class_="paginator")

        if not pagination:
            return None

        links = pagination.find_all("a")
        next_anchor = links[-1] if links else None

        if not next_anchor:
            return None

        clean_anchor_text = next_anchor.get_text(strip=True).replace("⟩", "")

        if "Następna" not in clean_anchor_text:
            return None

        return next_anchor.get("href")

    def parse_course_page(self, html: str, base_url: str) -> dict:
        """
        Parse the detail page of one course and extract structured course data.

        Args:
            html (str): HTML content of the course detail page.
            base_url (str): Absolute course URL used to resolve relative links.

        Returns:
            dict: Structured detail information for the course.
        """

        soup = BeautifulSoup(html, "html.parser")

        # Initialize the expected detail structure for every course.
        # Missing information remains None until it is successfully extracted.
        details = {
            "categories": None,
            "start_date": None,
            "end_date": None,
            "duration": None,
            "schedule": None,
            "age_from": None,
            "age_to": None,
            "available_spots": None,
            "participants_count": None,
            "organizer": None,
            "branch": None,
            "group_name": None,
            "level": None,
            "instructor": None,
            "rating_data": None,
            "documents": None,
            "description_raw": None,
        }

        sidebox_content = soup.select_one(".course-sidebox .box_content")

        if sidebox_content:
            metadata_data = self.parse_sidebox_metadata(sidebox_content, base_url)

            if metadata_data is not None:
                details.update(metadata_data)

            rating_data = self.parse_rating(sidebox_content)

            if rating_data is not None:
                details["rating_data"] = rating_data

        # Extract course content sections separately from the sidebar data.
        content_data = self.parse_content_sections(soup)
        details.update(content_data)

        return details

    def parse_sidebox_metadata(
        self, sidebox_content: Tag, base_url: str
    ) -> dict | None:
        """
        Extract course metadata from the sidebar definition list.

        Args:
            sidebox_content (Tag): Sidebar container of the course page.
            base_url (str): Absolute course URL used to resolve relative document links.

        Returns:
            dict | None: Extracted metadata, or None if the metadata container is not present.
        """

        metadata_container = sidebox_content.select_one("dl.horizontal-dl")

        if not metadata_container:
            return None

        extracted_data = {}

        metadata_terms = metadata_container.find_all("dt")

        for term in metadata_terms:
            field_name = term.get_text(strip=True)

            # Each <dt> label is paired with its corresponding <dd> value.
            field_value = term.find_next_sibling("dd")

            if not field_value:
                continue

            if field_name == "Kategoria":
                extracted_data["categories"] = self.parse_categories(field_value)

            elif field_name == "Dokumenty":
                extracted_data["documents"] = self.parse_documents(
                    field_value, base_url
                )

            elif field_name in NUMERIC_FIELD_MAP:
                raw_value = field_value.get_text(strip=True)

                # Extract digits because values may contain text such as "12 lat".
                digits_only = "".join(
                    character for character in raw_value if character.isdigit()
                )

                target_field = NUMERIC_FIELD_MAP[field_name]

                extracted_data[target_field] = int(digits_only) if digits_only else None

            elif field_name in SIDEBAR_FIELD_MAP:
                target_field = SIDEBAR_FIELD_MAP[field_name]

                extracted_data[target_field] = field_value.get_text(strip=True)

        return extracted_data

    def parse_categories(self, field_value: Tag) -> dict:
        """
        Extract main and subcategory names and IDs.

        Args:
            field_value (Tag): HTML element containing category links.

        Returns:
            dict: Structured category information.
        """
        categories = {
            "main_category": None,
            "main_category_id": None,
            "sub_category": None,
            "sub_category_id": None,
        }

        category_links = field_value.select("a.link-hover")

        # The first link represents the main category.
        if len(category_links) >= 1:
            main_category_link = category_links[0]

            categories["main_category"] = main_category_link.get_text(strip=True)

            category_url = main_category_link.get("href")

            if category_url:
                parsed_url = urlparse(category_url)
                # category_id is stored as a query parameter in the URL.
                category_ids = parse_qs(parsed_url.query).get("category_id")

                if category_ids:
                    categories["main_category_id"] = int(category_ids[0])

        # The second link represents the subcategory, when present.
        if len(category_links) >= 2:
            sub_category_link = category_links[1]

            categories["sub_category"] = sub_category_link.get_text(strip=True)

            category_url = sub_category_link.get("href")

            if category_url:
                parsed_url = urlparse(category_url)

                category_ids = parse_qs(parsed_url.query).get("category_id")

                if category_ids:
                    categories["sub_category_id"] = int(category_ids[0])

        return categories

    def parse_documents(self, field_value: Tag, base_url: str) -> dict | None:
        """
        Extract document label and convert its relative URL to an absolute URL.

        Args:
            field_value (Tag): HTML element containing document information.
            base_url (str): Absolute course URL used to resolve the document link.

        Returns:
            dict | None: Document information, or None if no document link exists.
        """
        document_link = field_value.select_one("a.link-hover")

        if not document_link:
            return None

        relative_url = document_link.get("href")

        document_url = urljoin(base_url, relative_url) if relative_url else None

        return {
            "label": document_link.get_text(" ", strip=True),
            "url": document_url,
        }

    def parse_rating(self, sidebox_content: Tag) -> dict | None:
        """
        Extract the course rating and number of reviews.

        Args:
            sidebox_content (Tag): Sidebar container of the course page.

        Returns:
            dict | None: Rating information, or None if the rating section is not present.
        """
        rating_section = sidebox_content.select_one("div.review-stars")

        if not rating_section:
            return None

        rating_data = {}

        rating_tag = rating_section.find("strong")

        if rating_tag:
            # The website uses a comma as the decimal separator, e.g. "4,7".
            raw_rating = rating_tag.get_text(strip=True).replace(",", ".")

            try:
                rating_data["score"] = float(raw_rating)
            except ValueError:
                pass

        reviews_link = rating_section.find("a")

        if reviews_link:
            raw_count_text = reviews_link.get_text(strip=True)

            # Extract the numeric review count from text such as "(23 ocen)".
            digits_only = "".join(
                character for character in raw_count_text if character.isdigit()
            )

            if digits_only:
                rating_data["reviews_count"] = int(digits_only)

        return rating_data

    def parse_content_sections(self, soup: BeautifulSoup) -> dict:
        """
        Extract selected content sections from the course detail page.

        Args:
            soup (BeautifulSoup): Parsed HTML of the course detail page.

        Returns:
            dict: Extracted description and instructor information.
        """
        content_data = {}

        content_sections = soup.select("div.section-box")

        for section in content_sections:
            title_element = section.select_one(".box_title")

            if not title_element:
                continue

            section_title = title_element.get_text(strip=True)
            section_content = section.select_one(".box_content")

            if not section_content:
                continue

            if section_title == "Opis":
                # Preserve line breaks so paragraphs remain separated.
                content_data["description_raw"] = section_content.get_text(
                    separator="\n", strip=True
                )

            elif section_title == "Instruktor":
                content_data["instructor"] = section_content.get_text(" ", strip=True)

        return content_data
