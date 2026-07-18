from urllib.parse import urlparse, unquote

import requests

from parsers.base_parser import BaseParser


class MediaWikiCategoryParser(BaseParser):
    """Parse a wiki category through the MediaWiki API.

    Works for any MediaWiki site (Fandom wikis, Bulbapedia, ...). Fandom serves
    its /wiki/ HTML behind a Cloudflare challenge (HTTP 403 to non-browser
    clients), so scraping the rendered category page fails; api.php is not
    challenged and returns the same roster as structured JSON, including each
    page's representative image.

    `source` is the category page URL (".../wiki/Category:Foo"). The API
    endpoint is the site host + `api_path`; the category title is taken from the
    part after "/wiki/". `clean_name` optionally rewrites a page title into the
    stored character name, or returns None to drop the page (e.g. meta pages).
    """

    HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; character-db/1.0)"}

    def __init__(self, api_path="/api.php", clean_name=None):
        self.api_path = api_path
        self.clean_name = clean_name

    def parse_characters(self, source):
        parsed = urlparse(source)
        api_endpoint = f"{parsed.scheme}://{parsed.netloc}{self.api_path}"
        # ".../wiki/Category:NPCs_(Hollow_Knight)" -> "Category:NPCs_(Hollow_Knight)"
        category_title = unquote(source.split("/wiki/", 1)[1])

        titles = self._category_members(api_endpoint, category_title)
        images = self._page_images(api_endpoint, titles)

        characters = {}
        for title in titles:
            image = images.get(title)
            if not image:
                continue
            name = self.clean_name(title) if self.clean_name else title
            if name is None:
                continue
            characters[name] = image
        return characters

    def _query(self, api_endpoint, params):
        """Yield each response page, following MediaWiki's continue token.

        Members and images are paged in separate queries on purpose: combining
        `generator=categorymembers` with `prop=pageimages` makes the API page the
        images (picontinue) over the first batch of members and never advance to
        members past the 500-per-batch limit, silently truncating large
        categories.
        """
        params = dict(params, action="query", format="json")
        while True:
            response = requests.get(api_endpoint, params=params, headers=self.HEADERS)
            response.raise_for_status()
            data = response.json()
            yield data.get("query", {})
            if "continue" in data:
                params.update(data["continue"])
            else:
                break

    def _category_members(self, api_endpoint, category_title):
        params = {
            "list": "categorymembers",
            "cmtitle": category_title,
            "cmtype": "page",           # articles only, skip subcategories/files
            "cmlimit": "500",
        }
        titles = []
        for query in self._query(api_endpoint, params):
            titles += [m["title"] for m in query.get("categorymembers", [])]
        return titles

    def _page_images(self, api_endpoint, titles):
        images = {}
        for i in range(0, len(titles), 50):       # titles= accepts up to 50 per query
            params = {
                "titles": "|".join(titles[i:i + 50]),
                "prop": "pageimages",
                "piprop": "original|thumbnail",
                "pithumbsize": "800",
                "pilimit": "max",
            }
            for query in self._query(api_endpoint, params):
                for page in query.get("pages", {}).values():
                    src = (page.get("original") or page.get("thumbnail") or {}).get("source")
                    if src:
                        images[page["title"]] = src
        return images


def _clean_pokemon_name(title):
    """Bulbapedia species pages are titled "Abra (Pokémon)"; store just "Abra".
    The "Pokémon (species)" index page is not a character -> drop it."""
    if title.endswith("(species)"):
        return None
    return title.removesuffix(" (Pokémon)")


class BulbapediaParser(MediaWikiCategoryParser):
    """Bulbapedia's API lives at /w/api.php (not /api.php), and its species page
    titles carry a " (Pokémon)" suffix that the stored names omit."""

    def __init__(self):
        super().__init__(api_path="/w/api.php", clean_name=_clean_pokemon_name)
