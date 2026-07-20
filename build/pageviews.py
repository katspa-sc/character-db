"""Wikipedia pageview helpers shared by the ranked-list generators.

`trailing_window` defines the scoring period; `fetch_views` totals an article's
pageviews over it. Used by media_ranking.py to rank the Popular Media roster.
"""
import logging
import time
import urllib.parse
from datetime import date, timedelta

import requests

logger = logging.getLogger(__name__)

USER_AGENT = "character-db/1.0 (wilkojc@gmail.com)"
PAGEVIEWS_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
    "/en.wikipedia/all-access/user/{title}/monthly/{start}/{end}"
)

RETRY_BACKOFFS = [1, 2, 4, 8, 16]  # seconds, used on 429/5xx before giving up
MAX_RETRY_WAIT = 300  # cap on a server-supplied Retry-After, seconds
WINDOW_MONTHS = 60  # rank by durable recognizability, not a single year's trends


def trailing_window():
    """Return (start, end) stamps covering the last WINDOW_MONTHS complete months."""
    first_of_month = date.today().replace(day=1)
    end = first_of_month - timedelta(days=1)
    total = first_of_month.year * 12 + (first_of_month.month - 1) - WINDOW_MONTHS
    start = date(total // 12, total % 12 + 1, 1)
    return start.strftime("%Y%m%d00"), end.strftime("%Y%m%d00")


def fetch_views(title, start, end):
    """Total pageviews for an article over the window.

    Returns 0 only when Wikimedia confirms the article has no pageview
    record (HTTP 404). Returns None if the request could not be completed
    (rate-limited, server error, network failure) even after retries -
    None means "unknown", and must never be treated as a real zero score.
    """
    url = PAGEVIEWS_URL.format(
        title=urllib.parse.quote(title, safe=""), start=start, end=end
    )
    wait_seconds = 0
    total_attempts = len(RETRY_BACKOFFS) + 1
    for attempt in range(total_attempts):
        if wait_seconds:
            time.sleep(wait_seconds)

        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        except requests.RequestException as e:
            logger.warning(f"Pageviews request error for '{title}': {e}")
            wait_seconds = RETRY_BACKOFFS[attempt] if attempt < len(RETRY_BACKOFFS) else 0
            continue

        if response.status_code == 404:
            return 0

        if response.status_code == 429 or response.status_code >= 500:
            logger.warning(
                f"Pageviews failed for '{title}': HTTP {response.status_code} "
                f"(attempt {attempt + 1}/{total_attempts})"
            )
            if attempt < len(RETRY_BACKOFFS):
                retry_after = response.headers.get("Retry-After")
                try:
                    wait_seconds = float(retry_after) if retry_after else RETRY_BACKOFFS[attempt]
                except ValueError:
                    wait_seconds = RETRY_BACKOFFS[attempt]
                wait_seconds = min(wait_seconds, MAX_RETRY_WAIT)  # cap a pathological Retry-After
            continue

        try:
            response.raise_for_status()
            return sum(item["views"] for item in response.json()["items"])
        except (requests.RequestException, ValueError, KeyError) as e:
            logger.warning(f"Pageviews failed for '{title}': {e}")
            return None

    logger.warning(f"Pageviews exhausted retries for '{title}'; marking unknown")
    return None
