from filter import CourseFilter
from parser import CourseParser
from scraper import ClassScout

# Initialize the application components.
class_scout = ClassScout()
course_parser = CourseParser()
course_filter = CourseFilter()

# Fetch the mapping between city names and StrefaZajec city IDs.
city_name_to_id = class_scout.fetch_cities()

# Prompt the user for city until a valid city name is provided (validation to prevent KeyError on typos).
while True:
    selected_city = (
        input("In which city are you looking for activities: ").strip().capitalize()
    )

    if selected_city in city_name_to_id:
        city_id = city_name_to_id[selected_city]
        break

    print(f"City '{selected_city}' not found. Please try again.")

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
