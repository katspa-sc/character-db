"""Add a fandom's roster to the static site's data.

For each configured fandom this:
  1. runs its parser to get {name: image_url},
  2. downloads each image and writes a max-400px webp to ../thumbnails/,
  3. appends a row to ../data/characters.json.

Entries whose hash already exists are skipped, so re-running is safe. The hash
(sha256 of "name_fandom-internal", lowercased) matches the one the web app and
the original Tkinter app use, so ignore/used flags stay attached.

    python build_data.py
"""

import hashlib
import io
import json
import os

import requests
from PIL import Image

from parsers import MediaWikiCategoryParser, BulbapediaParser

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_JSON = os.path.join(REPO, "data", "characters.json")
THUMB_DIR = os.path.join(REPO, "thumbnails")

_wiki = MediaWikiCategoryParser()

# (source, parser, fandom_internal, fandom_display)
# DBD Killers ("Offline") is intentionally not wired up: its roster was entered
# offline, and scraping deadbydaylight.fandom.com would create differently-named
# duplicates rather than update the existing entries.
FANDOMS = [
    (
        "https://hollowknight.fandom.com/wiki/Category:NPCs_(Hollow_Knight)",
        _wiki, "hollowknight", "Hollow Knight",
    ),
    (
        "https://leagueoflegends.fandom.com/wiki/Category:Playable_characters",
        _wiki, "leagueoflegends", "League",
    ),
    (
        "https://guiltygear.fandom.com/wiki/Category:Playable_characters",
        _wiki, "guiltygear", "Guilty Gear",
    ),
    (
        "https://tekken.fandom.com/wiki/Category:Characters",
        _wiki, "tekken", "Tekken",
    ),
    (
        "https://streetfighter.fandom.com/wiki/Category:Playable_Characters",
        _wiki, "streetfighter", "Street Fighter",
    ),
    # Broad categories (no "playable" category exists on these wikis): these pull
    # in some non-playable/minor characters beyond the original rosters.
    (
        "https://mortalkombat.fandom.com/wiki/Category:Characters",
        _wiki, "mortalkombat", "Mortal",
    ),
    (
        "https://hades.fandom.com/wiki/Category:Characters",
        _wiki, "hades", "Hades",
    ),
    # Fragile: Bulbapedia is rate-limited and large (~1020 species).
    (
        "https://bulbapedia.bulbagarden.net/wiki/Category:Pokémon",
        BulbapediaParser(), "bulbapedia", "Pokemon",
    ),
]

# Manual image overrides for pages where the wiki's auto-selected image is wrong
# (e.g. a DLC/header banner outranks the character's infobox portrait). Listed
# characters always have their thumbnail (re)downloaded from this URL, even if
# already present, so fixes here also repair bad images baked into the data.
# (name, fandom_internal): image_url
OVERRIDES = {
    ("Divine", "hollowknight"): "https://static.wikia.nocookie.net/hollowknight/images/f/f9/Divine.png/revision/latest?cb=20190112211514",
    ("Brumm", "hollowknight"): "https://static.wikia.nocookie.net/hollowknight/images/5/50/Brumm2.png/revision/latest?cb=20171028232656",
}


def character_hash(name, fandom_internal):
    return hashlib.sha256(f"{name.lower()}_{fandom_internal.lower()}".encode()).hexdigest()


def make_thumbnail(image_bytes):
    """Resize to fit 400x400 (aspect preserved) and encode as webp."""
    with Image.open(io.BytesIO(image_bytes)) as img:
        img.thumbnail((400, 400))
        out = io.BytesIO()
        img.save(out, format="WEBP")
        return out.getvalue()


def save_thumbnail(image_url, h):
    """Download image_url and write its 400px webp thumbnail as {h}.webp."""
    try:
        resp = requests.get(image_url, timeout=30)
        resp.raise_for_status()
        thumb = make_thumbnail(resp.content)
    except Exception as exc:
        print(f"  FAILED {h}: {exc}")
        return False
    with open(os.path.join(THUMB_DIR, f"{h}.webp"), "wb") as tf:
        tf.write(thumb)
    return True


def main():
    with open(DATA_JSON, encoding="utf-8") as f:
        characters = json.load(f)
    existing = {c["hash"] for c in characters}

    added = 0
    overridden = set()
    for source, parser, fandom_internal, fandom_display in FANDOMS:
        roster = parser.parse_characters(source)
        print(f"{fandom_display}: {len(roster)} entries fetched")

        for name, image_url in roster.items():
            h = character_hash(name, fandom_internal)
            override = OVERRIDES.get((name, fandom_internal))
            if h in existing and not override:
                continue  # already have it and no override to apply

            if not save_thumbnail(override or image_url, h):
                continue

            if override:
                overridden.add((name, fandom_internal))
            if h in existing:
                print(f"  override image: {name}")
                continue

            characters.append({
                "hash": h,
                "name": name,
                "fandom_internal": fandom_internal,
                "fandom_display": fandom_display,
                "thumbnail": f"{h}.webp",
            })
            existing.add(h)
            added += 1
            print(f"  added: {name}")

    # Overrides for characters no parser produced this run (e.g. an un-scraped
    # fandom): refresh the existing row's thumbnail in place.
    for (name, fandom_internal), image_url in OVERRIDES.items():
        if (name, fandom_internal) in overridden:
            continue
        h = character_hash(name, fandom_internal)
        if h not in existing:
            print(f"  override skipped (no such character): {name}")
            continue
        if save_thumbnail(image_url, h):
            print(f"  override image: {name}")

    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(characters, f, ensure_ascii=False)

    print(f"Done. Added {added} new characters. Total now {len(characters)}.")


if __name__ == "__main__":
    main()
