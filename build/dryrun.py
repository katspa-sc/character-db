"""Preview each fandom's roster without downloading images or writing data.

Runs every parser in FANDOMS and reports how many characters it fetched and how
many are NEW relative to the current characters.json. Handy for sanity-checking a
category before build_data.py downloads hundreds of thumbnails.

    python dryrun.py
"""
import json

from build_data import FANDOMS, DATA_JSON, character_hash

with open(DATA_JSON, encoding="utf-8") as f:
    existing = {c["hash"] for c in json.load(f)}

for source, parser, internal, display in FANDOMS:
    try:
        roster = parser.parse_characters(source)
    except Exception as exc:
        print(f"{display:16} FAILED: {exc}")
        continue
    new = sum(1 for n in roster if character_hash(n, internal) not in existing)
    sample = ", ".join(list(roster)[:4])
    print(f"{display:16} fetched={len(roster):4}  new={new:4}  e.g. {sample}")
