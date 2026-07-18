# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A static, client-side character browser. `index.html` + `style.css` + `script.js` render a
searchable/filterable grid of characters loaded from `data/characters.json`, with thumbnails in
`thumbnails/`. A separate Python pipeline in `build/` generates that data. There is no framework,
bundler, or server-side code.

## Running

The site uses `fetch('data/characters.json')`, so it must be served over HTTP — opening
`index.html` via `file://` fails CORS. Serve the repo root with any static server:

```bash
python -m http.server 8000   # then open http://localhost:8000
```

Deployment target is GitHub Pages / any static host (serve the repo root as-is).

## Rebuilding the data (`build/`)

`build/build_data.py` fetches rosters, downloads images, writes 400px WEBP thumbnails to
`thumbnails/`, and appends rows to `data/characters.json`.

```bash
cd build
python -m venv .buildvenv && source .buildvenv/bin/activate
pip install -r requirements.txt   # requests, Pillow
python build_data.py
```

Re-running is idempotent: rows whose hash already exists are skipped, so it only adds new
characters. It rewrites `data/characters.json` (minified, `ensure_ascii=False`) each run.

## Key architectural facts

- **Character identity is a hash.** `hash = sha256("{name}_{fandom_internal}".lower())`. This is
  computed identically in `build/build_data.py:character_hash` and used as the thumbnail filename
  (`{hash}.webp`) and the localStorage key suffix. It also matches the hash used by an original
  Tkinter app this project descends from — do not change the hashing scheme or existing ignore/used
  flags detach from their characters.

- **Per-character state lives in the browser's localStorage**, not in the data files. Flags are
  stored as `ignored_{hash}` and `used_{hash}` (`script.js` `stateManager`). Nothing is persisted
  server-side.

- **Adding a fandom** = write a parser + register it. Subclass `BaseParser`
  (`build/parsers/base_parser.py`), implementing `parse_characters(source) -> {name: image_url}`,
  export it from `build/parsers/__init__.py`, then add a
  `(source, parser(), fandom_internal, fandom_display)` tuple to `FANDOMS` in `build_data.py`.
  Fandom wikis on Cloudflare block plain HTML scraping (403); `HollowKnightParser` shows the pattern
  of going through the MediaWiki `api.php` instead.

- **Search does Polish-phonetic transliteration** (`script.js` `performSearch`). The query is
  treated as regex after substitutions: space→`.*`, `h`→`(ch\|h)`, `w`→`(v\|w)`, `sz`→`(sz\|sh)`,
  `cz`→`(cz\|ch)`; a 2-char query gets a space inserted when "Add Delimiter" is on. "Disregard
  Prefix" toggles between anchored (`^pattern`) and unanchored matching.

- **Fandom sidebar ordering** is a manual priority list, `FANDOM_SORT_ORDER` at the top of
  `script.js` (matched against `fandom_display`); unlisted fandoms fall back to alphabetical.

## Notes

- The working branch is `characters` (not `main`/`master`).
