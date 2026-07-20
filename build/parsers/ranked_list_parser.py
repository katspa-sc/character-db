import json
import logging
import time

import requests

from parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)

TOP_N = 300
BATCH_SIZE = 50           # titles= accepts up to 50 per query
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; character-db/1.0)"}


def extract_images(response, requested_names):
    """Map images from a MediaWiki response back to the names we asked for.

    The API rewrites titles (normalisation, then redirects) and returns pages
    under the final title, so each requested name is followed through the
    rewrite chain to find its page. Prefers the full `original` image, falling
    back to the `thumbnail` the same way MediaWikiCategoryParser does.
    """
    query = response.get("query", {})

    rewrites = {}
    for entry in query.get("normalized", []):
        rewrites[entry["from"]] = entry["to"]
    for entry in query.get("redirects", []):
        rewrites[entry["from"]] = entry["to"]

    title_to_image = {}
    for page in query.get("pages", {}).values():
        src = (page.get("original") or page.get("thumbnail") or {}).get("source")
        if src:
            title_to_image[page["title"]] = src

    images = {}
    for name in requested_names:
        title = name
        seen = set()
        while title in rewrites and title not in seen:
            seen.add(title)
            title = rewrites[title]

        if title in title_to_image:
            images[name] = title_to_image[title]
        else:
            logger.warning(f"No image found for '{name}'")

    return images


class RankedListParser(BaseParser):
    """Resolve a pre-ranked list of character names to Fandom images.

    Unlike MediaWikiCategoryParser, which pages an entire wiki category, this
    reads a curated list of names ranked by recognizability and resolves only
    the top N. Marvel/DC wiki categories have 100k+ members, so scraping the
    whole roster is neither useful nor feasible; the ranked list (produced by
    the fandom_parser project's Wikipedia-pageview scorer) is used instead.

    `source` is the path to a JSON array, most-recognizable first, in one of two
    formats: a list of name strings (the name is also the wiki page title, used
    for Marvel/DC), or a list of `[name, title]` pairs (the page is looked up by
    the exact article title but keyed by the display name, used for the
    cross-franchise Popular Media roster whose enwiki titles differ from names).
    `api_url` is the target wiki's api.php endpoint. `top_n` clips the roster.
    """

    def __init__(self, api_url, top_n=TOP_N):
        self.api_url = api_url
        self.top_n = top_n

    def parse_characters(self, source):
        with open(source, encoding="utf-8") as f:
            items = json.load(f)[:self.top_n]

        # Normalise both formats to (display_name, lookup_title) pairs.
        pairs = [(i, i) if isinstance(i, str) else (i[0], i[1]) for i in items]
        title_to_name = {title: name for name, title in pairs}
        titles = [title for _, title in pairs]

        characters = {}
        for start in range(0, len(titles), BATCH_SIZE):
            batch = titles[start:start + BATCH_SIZE]
            try:
                response = self._fetch_batch(batch)
            except (requests.RequestException, ValueError) as exc:
                logger.error(f"Batch starting at {start} failed: {exc}")
                continue
            for title, image in extract_images(response, batch).items():
                characters[title_to_name[title]] = image

        return characters

    def _fetch_batch(self, batch):
        params = {
            "action": "query",
            "format": "json",
            "redirects": 1,
            "prop": "pageimages",
            "piprop": "original|thumbnail",
            "pithumbsize": "800",
            "pilimit": "max",
            # Default pilicense=free drops non-free infobox art, which is the
            # iconic image for most modern characters (Batman, Mario) on
            # en.wikipedia. 'any' includes it; harmless on Fandom wikis.
            "pilicense": "any",
            "titles": "|".join(batch),
        }
        # en.wikipedia rate-limits (429) rapid consecutive batches; back off and
        # retry so tail batches aren't silently dropped from the roster.
        for attempt in range(4):
            response = requests.get(
                self.api_url, params=params, headers=HEADERS, timeout=30
            )
            if response.status_code == 429 and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            break
        response.raise_for_status()
        return response.json()
