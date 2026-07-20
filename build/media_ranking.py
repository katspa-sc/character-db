"""Rank the cross-franchise "Popular Media" roster into cache/popular.json.

Enumerates game/TV/film/anime characters from Wikidata that have an English
Wikipedia article, scores each by trailing pageviews, and writes the top N as
[name, enwiki_title] pairs. RankedListParser then resolves those titles to
images off en.wikipedia.

    python media_ranking.py
"""
import json
import logging
import os
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from pageviews import fetch_views, trailing_window

logger = logging.getLogger(__name__)

USER_AGENT = "character-db/1.0 (wilkojc@gmail.com)"
SPARQL_URL = "https://query.wikidata.org/sparql"
SPARQL_RETRY_BACKOFFS = [5, 15, 30, 60, 120]  # seconds; WDQS is flaky under load (502/truncated JSON) for windows longer than a few short retries, so ride it out

# Character classes for the "Popular Media" bucket: game + anime + comics.
# television character (Q15773317) and film character (Q15773347) are excluded
# as too wide (many unrecognisable movie/TV-only characters).
MEDIA_CLASSES = [
    "Q1569167",   # video game character
    "Q80447738",  # anime character
    "Q1114461",   # comics character
]

# Names already covered by the dedicated Marvel/DC rosters are dropped from this
# bucket so the same character (Batman, Bane, Apocalypse, ...) is not listed
# twice. Matched case-insensitively on the display name.
EXCLUDE_ROSTERS = ["cache/marvel.json", "cache/dc.json"]

# Enumerate characters of one class that have an English Wikipedia article.
# Queried per class (a union over all classes times out).
SPARQL_QUERY = """
SELECT DISTINCT ?itemLabel ?article WHERE {{
  ?item wdt:P31/wdt:P279* wd:{cls} .
  ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""

TOP_N = 1000
MAX_FAILURE_RATIO = 0.05  # abort writing the cache above this unknown-fetch rate
MAX_WORKERS = 4


def parse_candidate_rows(bindings):
    """Map SPARQL result bindings to {name: enwiki_title}, first-wins by name.

    Unlabelled entities surface as their QID (e.g. "Q12379") and are dropped -
    they are not usable names. The article URL carries the real page title,
    which may differ from the label (e.g. "Blue Streak" vs
    "Blue Streak (character)").
    """
    candidates = {}
    for row in bindings:
        name = row["itemLabel"]["value"]
        if re.fullmatch(r"Q\d+", name):
            continue
        title = urllib.parse.unquote(row["article"]["value"].rsplit("/", 1)[-1])
        candidates.setdefault(name, title)
    return candidates


def fetch_candidates(class_qid):
    """Fetch {name: enwiki_title} for one character class.

    WDQS intermittently times out server-side on large classes; retry with
    backoff before giving up, since the same query usually succeeds (and is
    often served from cache) on the next attempt.
    """
    last_exception = None
    for attempt in range(len(SPARQL_RETRY_BACKOFFS) + 1):
        try:
            response = requests.get(
                SPARQL_URL,
                params={"query": SPARQL_QUERY.format(cls=class_qid)},
                headers={"User-Agent": USER_AGENT,
                         "Accept": "application/sparql-results+json"},
                timeout=180,
            )
            response.raise_for_status()
            # Some entity labels contain raw control characters that strict JSON
            # rejects (a deterministic failure retries can't fix); strict=False
            # tolerates them.
            payload = json.loads(response.text, strict=False)
            return parse_candidate_rows(payload["results"]["bindings"])
        except (requests.RequestException, ValueError, KeyError) as e:
            last_exception = e
            if attempt < len(SPARQL_RETRY_BACKOFFS):
                logger.warning(
                    f"Class {class_qid} enumeration failed (attempt "
                    f"{attempt + 1}/{len(SPARQL_RETRY_BACKOFFS) + 1}): {e}"
                )
                time.sleep(SPARQL_RETRY_BACKOFFS[attempt])

    raise last_exception


def gather_candidates():
    """Merge candidates across all MEDIA_CLASSES, de-duplicated by name.

    A class that fails (timeout/error) is logged and skipped so one slow class
    does not abort the whole run.
    """
    merged = {}
    for cls in MEDIA_CLASSES:
        try:
            found = fetch_candidates(cls)
        except (requests.RequestException, ValueError, KeyError) as e:
            logger.error(f"Class {cls} enumeration failed: {e}")
            continue
        logger.info(f"Class {cls}: {len(found)} candidates")
        for name, title in found.items():
            merged.setdefault(name, title)

    excluded = load_excluded_names()
    filtered = {n: t for n, t in merged.items() if n.lower() not in excluded}
    logger.info(
        f"Merged candidates: {len(merged)}; after Marvel/DC exclusion: {len(filtered)}"
    )
    return list(filtered.items())


def load_excluded_names():
    """Lowercased names already in the Marvel/DC rosters, to skip in this bucket."""
    excluded = set()
    for path in EXCLUDE_ROSTERS:
        try:
            with open(path, encoding="utf-8") as f:
                excluded.update(name.lower() for name in json.load(f))
        except FileNotFoundError:
            logger.warning(f"Exclusion roster {path} not found; skipping it")
    return excluded


def select_top(scored, n):
    """Sort (views, item) pairs by views desc and return the first n items."""
    ordered = sorted(scored, key=lambda pair: pair[0], reverse=True)
    return [item for _, item in ordered[:n]]


def over_failure_threshold(failed, total):
    """True when the unknown-fetch ratio exceeds MAX_FAILURE_RATIO."""
    if not total:
        return False
    return failed / total > MAX_FAILURE_RATIO


def build_ranking(start, end):
    candidates = gather_candidates()
    logger.info(f"Scoring {len(candidates)} candidates by pageviews")

    scored = []
    failed = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Keep each name paired with its enwiki title: the title is the exact
        # article, needed downstream to look up the character's image (the label
        # alone is ambiguous - "Rhino" the character vs the animal).
        future_to_pair = {
            executor.submit(fetch_views, title, start, end): [name, title]
            for name, title in candidates
        }
        for future in as_completed(future_to_pair):
            views = future.result()
            if views is None:
                failed += 1
                continue
            scored.append((views, future_to_pair[future]))

    total = len(candidates)
    logger.info(f"{total - failed} succeeded, {failed} failed (unknown), of {total}")

    if over_failure_threshold(failed, total):
        logger.error(
            f"{failed}/{total} pageview fetches failed - exceeds "
            f"{MAX_FAILURE_RATIO:.0%}; refusing to write cache/popular.json"
        )
        return None

    ranked = select_top(scored, TOP_N)  # list of [name, enwiki_title] pairs
    os.makedirs("cache", exist_ok=True)
    with open("cache/popular.json", "w", encoding="utf-8") as handle:
        json.dump(ranked, handle, ensure_ascii=False, indent=1)

    logger.info(f"Wrote cache/popular.json ({len(ranked)} entries)")
    logger.info(f"Top 10 - {', '.join(name for name, _ in ranked[:10])}")
    return ranked


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - %(levelname)s - %(message)s")
    start, end = trailing_window()
    logger.info(f"Scoring pageviews from {start} to {end}")
    build_ranking(start, end)
