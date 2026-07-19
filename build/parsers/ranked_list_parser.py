import json
import logging

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

    `source` is the path to a JSON array of names, most-recognizable first.
    `api_url` is the target wiki's api.php endpoint.
    """

    def __init__(self, api_url):
        self.api_url = api_url

    def parse_characters(self, source):
        with open(source, encoding="utf-8") as f:
            names = json.load(f)[:TOP_N]

        characters = {}
        for start in range(0, len(names), BATCH_SIZE):
            batch = names[start:start + BATCH_SIZE]
            try:
                response = self._fetch_batch(batch)
            except (requests.RequestException, ValueError) as exc:
                logger.error(f"Batch starting at {start} failed: {exc}")
                continue
            characters.update(extract_images(response, batch))

        return characters

    def _fetch_batch(self, batch):
        response = requests.get(
            self.api_url,
            params={
                "action": "query",
                "format": "json",
                "redirects": 1,
                "prop": "pageimages",
                "piprop": "original|thumbnail",
                "pithumbsize": "800",
                "pilimit": "max",
                "titles": "|".join(batch),
            },
            headers=HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
