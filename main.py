import json
from pathlib import Path

from filter import CourseFilter
from parser import CourseParser
from scraper import ClassScout

CITIES_FILE = Path(__file__).parent / "cities.json"


def load_city_ids() -> dict[str, int]:
    """
    Load the mapping of city names to StrefaZajec city IDs.

    The IDs were collected manually, because the website endpoint that
    provides them is disallowed in robots.txt.

    Returns:
        dict[str, int]: City names mapped to their internal IDs, e.g. {"Warszawa": 42}.
    """
    with open(CITIES_FILE, encoding="utf-8") as f:
        return json.load(f)


def main():
    """
    Fetch details of up-to-date courses available in the city chosen by the user.

    The program asks the user for a city, collects all courses listed on
    StrefaZajec.pl, rejects courses that are clearly outdated and fetches
    details for the remaining ones.
    """

    # Initialize the application components.
    class_scout = ClassScout()
    course_parser = CourseParser()
    course_filter = CourseFilter()

    # Load the mapping between city names and StrefaZajec city IDs.
    city_name_to_id = load_city_ids()

    # Prompt the user for city until a supported city name is provided.
    while True:
        selected_city = (
            input("In which city are you looking for activities: ").strip().title()
        )

        if selected_city in city_name_to_id:
            city_id = city_name_to_id[selected_city]
            break

        available_cities = ", ".join(sorted(city_name_to_id))
        print(
            f"City '{selected_city}' is not supported. Available cities: {available_cities}"
        )

    # Scrape all listing pages for the selected city and collect basic course data.
    courses = class_scout.scrape_listings(
        city_name=selected_city, city_id=city_id, parser=course_parser
    )
    print(f"Found {len(courses)} courses")

    # Remove clearly outdated courses before requesting detail pages.
    candidate_courses = course_filter.filter_expired_listings(courses)
    print(f"Candidates after filtering: {len(candidate_courses)}")

    # Fetch and parse the detail page for each remaining course.
    courses_with_details = class_scout.scrape_course_details(
        courses=candidate_courses, parser=course_parser
    )

    print(f"Courses with details: {len(courses_with_details)}")


if __name__ == "__main__":
    main()
