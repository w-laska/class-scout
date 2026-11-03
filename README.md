# ClassScout

ClassScout is an application for discovering and monitoring courses published
on StrefaZajec.pl, a Polish website listing courses run by local cultural
centres.

## Motivation

The idea came from a ceramics class, where one of us kept refreshing the
page and phoning the rest of the group whenever registration opened.

Classes at local cultural centres are often much cheaper than similar offers
from private providers, and popular ones can be fully booked within an hour
of being published. Registration dates are rarely announced publicly: some
centres share them informally with current participants, others not at all,
so new classes often appear without warning. Single places also free up
whenever someone cancels. The only way to catch them today is to keep
checking the website by hand. ClassScout automates that checking and will
notify the user as soon as a new course or a free place appears in whatever
they choose to follow: a single course, a specific cultural centre, or
a whole category such as ceramics or music.

## Status

Work in progress. The current version:

- asks the user for a city,
- collects courses from all result pages for that city,
- rejects courses that are clearly outdated,
- fetches details for the remaining courses,
- prints a summary with the number of courses at each step.

## Planned features

- storing courses and their history in a database,
- running the scraper automatically on a schedule,
- detecting new courses and newly available places,
- sending email alerts for courses, centres or categories the user follows.

## How to run

Requires Python 3.10 or newer.

```bash
git clone https://github.com/w-laska/class-scout.git
cd class-scout
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Legal & data

- This is a non-commercial, educational portfolio project.
- The scraper respects `robots.txt`, which disallows the `/ajax/` path for
  automated clients. City IDs are stored in `cities.json`; they were
  collected manually in a web browser on 2 November 2026. All URLs requested
  by the scraper are allowed by `robots.txt` (checked with Python's
  `urllib.robotparser`).
- Requests are spaced out with a delay, and outdated courses are filtered out
  before detail pages are fetched, to keep the load on the server low. Failed
  requests are retried at most 3 times, with increasing delays, and the
  server's `Retry-After` header is respected.
- The scraper only notifies; it never signs up for courses automatically.
- Personal data (names of instructors and review authors) will not be shown
  in the public demo.
- All course data belongs to StrefaZajec.pl and the course organisers; the app
  will link back to the original listings.