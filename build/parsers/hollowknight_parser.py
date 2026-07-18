import requests
from urllib.parse import urlparse, unquote

from parsers.base_parser import BaseParser


class HollowKnightParser(BaseParser):
    """Parse a Fandom category through the MediaWiki API instead of the rendered
    category page.

    hollowknight.fandom.com serves its /wiki/ HTML behind a Cloudflare challenge
    (HTTP 403 to non-browser clients), so scraping that HTML does not work. The
    api.php endpoint is not challenged and returns the same roster as structured
    JSON, including each page's representative image.

    `source` is the category page URL; the API endpoint and category title are
    derived from it.
    """

    HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; character-db/1.0)"}

    def parse_characters(self, source):
        parsed = urlparse(source)
        api_endpoint = f"{parsed.scheme}://{parsed.netloc}/api.php"
        # ".../wiki/Category:NPCs_(Hollow_Knight)" -> "Category:NPCs_(Hollow_Knight)"
        category_title = unquote(source.split("/wiki/", 1)[1])

        params = {
            "action": "query",
            "format": "json",
            "generator": "categorymembers",
            "gcmtitle": category_title,
            "gcmtype": "page",          # articles only, skip subcategories/files
            "gcmlimit": "500",
            "prop": "pageimages",
            "piprop": "original|thumbnail",
            "pithumbsize": "800",
        }

        characters = {}
        while True:
            response = requests.get(api_endpoint, params=params, headers=self.HEADERS)
            response.raise_for_status()
            data = response.json()

            for page in data.get("query", {}).get("pages", {}).values():
                image = (page.get("original") or page.get("thumbnail") or {}).get("source")
                if image:
                    characters[page["title"]] = image

            # generator + prop queries can span several batches; follow continue
            if "continue" in data:
                params.update(data["continue"])
            else:
                break

        return characters
