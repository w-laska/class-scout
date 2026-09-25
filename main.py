import time
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

# Base endpoint for querying paginated course listings
COURSES_URL = "https://www.strefazajec.pl/course"

# Emulate a standard desktop browser to avoid anti-bot fingerprinting and default urllib blocking
HEADERS = {"User-Agent" : "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/151.0.0.0 Safari/537.36"}

# Unofficial internal AJAX endpoint discovered via DevTools:
# returns JSON mapping of major Polish cities to internal platform IDs
CITIES_API_URL = "https://www.strefazajec.pl/ajax/biggestcities/filename/cities.json"

# Maps Polish website labels to our database column names
SIDEBAR_FIELD_MAP = {
    # Dates & duration
    "Data rozpoczęcia": "start_date",
    "Data zakończenia": "end_date",
    "Czas trwania": "duration",

    # Location & organization
    "Organizator": "organizer",
    "Filia": "branch",
    "Nazwa grupy": "group_name",

    # Class specs & documents
    "Poziom": "level",
}

# Fields where we only want numbers (e.g., age, spots)
NUMERIC_FIELD_MAP = {
    "Wiek od": "age_from",
    "Wiek do": "age_to",
    "Wolnych miejsc": "available_spots",
    "Liczba uczestników": "participants_count",
}

# Initialize session for connection pooling and shared headers
session = requests.Session()
session.headers.update(HEADERS)

# Pre-fetch lookup table for city IDs required by search query parameters
cities_response = session.get(CITIES_API_URL, timeout=10)
cities_data = cities_response.json()

# Extract the list of cities
cities_list = cities_data["cities"]

# Build a dictionary to easily find city ID by name: {"Warszawa": 1, ...}
city_name_to_id = {}
for city in cities_list:
    city_name_to_id[city["value"]] = city["id"]

# Prompt user for city with validation to prevent KeyError on typos
while True:
    selected_city = input("In which city are you looking for activities: ").strip().capitalize()
    if selected_city in city_name_to_id:
        city_id = city_name_to_id[selected_city]
        break
    print(f"City '{selected_city}' not found. Please try again.")

# Parameters for the first search page
search_params = {
    "city_name": selected_city,
    "city_id": city_id,
}

# Initialize starting url and create a list of links to visit
current_url = COURSES_URL
courses_to_visit = []

# Collect all unique label names across all pages to see what fields exist
unique_keys = set()

# =============================================================================
# 1. Browse pages and collect course links
# =============================================================================
while True:
    # Get page content (we only need search_params on page 1, later pages have it in the URL)
    response = session.get(url=current_url, params=search_params, timeout=10)
    search_params = None

    # Pause between requests to mimic human behavior and avoid rate limits
    time.sleep(random.uniform(0.8, 2.0))

    # Extract HTML content as text and feed it to the parser
    # Get response text and parse it with BeautfiulSoup
    html_content = response.text
    soup = BeautifulSoup(html_content, "html.parser")

    # Extract all course cards on the page/ extract all course record elements
    course_record = soup.find_all("div", class_= "course-record")

    # Define cutoff date to filter out outdated courses (older than 540 days (~1.5 years))
    # Calculate threshold date for filtering expired records
    today = datetime.today().date()
    cutoff_date = today - timedelta(days=540)

    # Iterate over each course card and extract basic information
    for card in course_record:
        # Extract the course category, providing a default value ("No type"), to prevent crashes if information is
        # missing
        type_element = card.select_one(".course-type a")
        course_type = type_element.text.strip() if type_element else "No type"

        # Check if the calendar icon exists to find the date text; if missing, skip the current iteration.
        icon_calendar = card.select_one(".fa-calendar")
        if not icon_calendar:
            # print(f"[ODRZUCONY - BRAK IKONY KALENDARZA] {course_type}")
            continue

        # Clean the raw date string by removing the prefix "Termin:" and extra white spaces
        p_elem = icon_calendar.parent.get_text()
        raw_date = p_elem.replace("Termin:", "").strip()
        raw_date = " ".join(raw_date.split())

        # Try to parse the date and filter out expired courses
        try:
            # Handle the date ranges: extract the last date and set is as the end date for comparison
            if "-" in raw_date:
                # If date range (e.g. 01.09.2025 - 30.06.2026), check if end date is in the past
                end_date_str = raw_date.split("-")[-1].strip()
                # Parse the extracted string into a date object
                end_date = datetime.strptime(end_date_str, "%d.%m.%Y").date()

                # Skip the course if the end date has already passed
                if end_date < today:
                    continue

            # Handle single dates: parse as the start date
            else:
                # Parse the extracted string into a date object
                start_date = datetime.strptime(raw_date.strip(), "%d.%m.%Y").date()

                # Skip the course if the start date is too old
                if start_date < cutoff_date:
                    continue

        # # Skip if the date format is unusual or text-based
        except ValueError:
            continue

        link_to_course_details = card.select_one("h3.title a.link-hover")
        if link_to_course_details:
            # Extract the course title
            course_title = link_to_course_details.get_text(strip=True)

            # Extract the relative URL and construct the full link to course details
            relative_url_course_detail = link_to_course_details.get("href")
            full_course_url_detail = urljoin(current_url, relative_url_course_detail)

            # Save basic course info and prepare empty fields for details
            courses_to_visit.append({
                # Basic course info
                "title": course_title,
                "type": course_type,
                "raw_date": raw_date,
                "url": full_course_url_detail,

                # Ratings & reviews
                "rating": None,
                "reviews_count": None,

                # Taxonomy & categories
                "main_category": None,
                "main_category_id": None,
                "sub_category": None,
                "sub_category_id": None,

                # Dates & schedule
                "start_date": None,
                "end_date": None,
                "duration": None,

                # Target age group
                "age_from": None,
                "age_to": None,

                # Location & provider
                "organizer": None,
                "branch": None,
                "group_name": None,

                # Capacity & enrollment status
                "level": None,
                "available_spots": None,
                "participants_count": None,
                "documents": None,

                # Details in description
                "description_raw": None,

                # Instructor
                "instructor_raw": None,
            })

    # Find the main pagination container on the page
    pagination = soup.find("div", class_="paginator")
    if not pagination:
        break

    # Extract all <a> links within the paginator
    links = pagination.find_all("a")

    # Take the last element from the list (corresponding to the "Następna" button")
    next_anchor = links[-1] if links else None
    if not next_anchor:
        break

    # If the last link is not 'Następna', we reached the final page
    clean_anchor_text = next_anchor.text.replace("⟩", "").strip()
    if "Następna" not in clean_anchor_text:
        break

    # Get the URL for the next page
    next_page_relative_url = next_anchor.get("href")
    current_url = urljoin(current_url, next_page_relative_url)

# =============================================================================
# 2. Visit each course page and extract full details
# =============================================================================
for course_item in courses_to_visit:
    course_url = course_item["url"]
    # print(f"Downloading details for: {course_url}")

    # Fetch HTML for the course details page with rate-limiting pause to mimic human behaviour
    response = session.get(url=course_url, timeout=10)
    time.sleep(random.uniform(1, 2.5))


    # Parse the HTML content of the course details page into a navigable DOM tree
    html_content = response.text
    soup = BeautifulSoup(html_content, "html.parser")


    # Loop over all content boxes on the page to find Description and Instructor
    content_sections = soup.select("div.section-box")
    for section in content_sections:

        # Guard clause: skip sections without a title (e.g. image banners) to prevent Attribute Error
        title_element = section.select_one(".box_title")
        if not title_element:
            continue

        # Identify section by heading title
        section_title = title_element.get_text(strip=True)

        if section_title == "Opis":
            desc_content = section.select_one(".box_content")
            if desc_content:
                # Keep newlines (\n) so paragraphs and line breaks don't get merged together
                course_item["description_raw"] = desc_content.get_text(separator= "\n", strip=True)

        elif section_title == "Instruktor":
            inst_content = section.select_one(".box_content")
            if inst_content:
                # Capture instructor details
                course_item["instructor_raw"] = inst_content.get_text(strip=True)


    # Extract the primary sidebox container holding metadata and summary widgets
    sidebox_content = soup.select_one(".course-sidebox .box_content")

    # Guard clause: only attempt extraction if the container exists
    if sidebox_content:
        # 1. Rating and reviews count
        reviews = sidebox_content.select_one("div.review-stars")
        if reviews:
            # Extract and parse numeric rating value
            rating_tag = reviews.find("strong")
            if rating_tag:
                # Convert Polish decimal comma format ("0,0") into a Python float standard ("0.0")
                raw_rating = rating_tag.get_text(strip=True).replace(",", ".")
                course_item["rating"] = float(raw_rating)

            # Extract and parse total reviews counter
            reviews_link = reviews.find("a")
            if reviews_link:
                # Strip all non-digit characters (e.g., "(0 ocen)" -> "0") to isolate the integer count
                raw_count_text = reviews_link.get_text(strip=True)
                digits_only = "".join(char for char in raw_count_text if char.isdigit())

                # Convert to integer only if at least one digit was found
                if digits_only:
                    course_item["reviews_count"] = int(digits_only)


        # Locate the definition list (<dl>) inside the sidebar holding course specifications as label value pairs
        metadata_list= sidebox_content.select_one("dl.horizontal-dl")

        # Verify the container exists before processing to avoid errors on pages with missing sidebars
        if metadata_list:

            # Find all label tags (<dt>) representing individual property names (e.g. "Wiek od", "Organizator")
            all_dt = metadata_list.find_all("dt")

            # Iterate through each label tag sequentially to process its corresponding value
            for dt in all_dt:
                key = dt.get_text(strip=True)

                # Collect every encountered key across all parsed courses to identify potential new or unmapped fields
                unique_keys.add(key)

                # Pair the term (<dt>) with its corresponding description tag (<dd>)
                dd = dt.find_next_sibling("dd")
                if not dd:
                    continue

                if key == "Kategoria":
                    # Extract hierarchical category links (Breadcrumbs: Main category -> Subcategory)
                    category_links = dd.select("a.link-hover")

                    main_category = None
                    main_category_id = None
                    sub_category = None
                    sub_category_id = None

                    # Safe indexing to extract main category and its relational ID from the URL query
                    if len(category_links) >= 1:
                        main_cat_link = category_links[0]
                        main_category = main_cat_link.get_text(strip=True)

                        # Extract the numeric category_id from the link URL query (?category_id=...)
                        parsed = urlparse(main_cat_link.get("href"))
                        cat_ids = parse_qs(parsed.query).get("category_id")
                        main_category_id = int(cat_ids[0]) if cat_ids else None

                    # Second link is the subcategory (if it exists)
                    if len(category_links) >= 2:
                        sub_cat_link = category_links[1]
                        sub_category = sub_cat_link.get_text(strip=True)

                        parsed = urlparse(sub_cat_link.get("href"))
                        sub_cat_ids = parse_qs(parsed.query).get("category_id")
                        sub_category_id = int(sub_cat_ids[0]) if sub_cat_ids else None

                    course_item["main_category"] = main_category
                    course_item["main_category_id"] = main_category_id
                    course_item["sub_category"] = sub_category
                    course_item["sub_category_id"] = sub_category_id

                elif key == "Dokumenty":
                    # Build full document link if there is a link, otherwise keep the label text
                    doc_label = dd.get_text(strip=True)
                    doc_anchor = dd.select_one("a.link-hover")
                    doc_relative_url = doc_anchor.get("href") if doc_anchor else None
                    full_document_url = urljoin(course_url, doc_relative_url)
                    document_info = f"{doc_label}: {full_document_url}" if doc_anchor else doc_label
                    course_item["documents"] = document_info

                elif key in NUMERIC_FIELD_MAP:
                    # Keep only numbers (e.g. "12 lat" -> 12)
                    raw_value = dd.get_text(strip=True)
                    digits_only = "".join(char for char in raw_value if char.isdigit())
                    numeric_value = int(digits_only) if digits_only else None
                    target_field = NUMERIC_FIELD_MAP[key]
                    course_item[target_field] = numeric_value

                elif key in SIDEBAR_FIELD_MAP:
                    # Save regular text fields (organizer, branch, etc.)
                    raw_text = dd.get_text(strip=True)
                    target_field = SIDEBAR_FIELD_MAP[key]
                    course_item[target_field] = raw_text

print(f"Extraction complete. Successfully processed {len(courses_to_visit)} courses.")



