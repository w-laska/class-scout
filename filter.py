from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


class CourseFilter:
    """
    Filters course records based on selected criteria.
    """

    def filter_expired_listings(
        self, courses: list[dict], cutoff_days: int = 540
    ) -> list[dict]:
        """
        Removes clearly expired courses from a list of course dictionaries using the dates available
        on the course listing cards, before requesting their detail pages, reducing unnecessary HTTP processing

        Courses with valid or ambiguous dates are kept for further processing.

        Args:
            courses (list[dict]): List of course dictionaries containing listing information
                                  such as title, type, raw_date, and URL.
            cutoff_days (int): Number of days before today used to identify outdated single-date listings.

        Returns:
            list[dict]: Course dictionaries that should proceed to detail-page scraping.
        """

        today = datetime.now(ZoneInfo("Europe/Warsaw")).date()
        cutoff_date = today - timedelta(days=cutoff_days)

        candidate_courses = []
        for course in courses:
            raw_date = course["raw_date"]

            try:
                # For a date range, use the end date to determine whether the course has expired.
                if "-" in raw_date:
                    end_date_str = raw_date.split("-")[-1].strip()
                    end_date = (
                        datetime.strptime(end_date_str, "%d.%m.%Y")
                        .replace(tzinfo=ZoneInfo("Europe/Warsaw"))
                        .date()
                    )

                    if end_date < today:
                        continue

                else:
                    # For a single date, use the start date and apply the cutoff period.
                    start_date = (
                        datetime.strptime(raw_date.strip(), "%d.%m.%Y")
                        .replace(tzinfo=ZoneInfo("Europe/Warsaw"))
                        .date()
                    )
                    if start_date < cutoff_date:
                        continue

            except ValueError:
                # Ambiguous or unexpected date format: keep the course for detail-page inspection.
                pass

            candidate_courses.append(course)

        return candidate_courses
