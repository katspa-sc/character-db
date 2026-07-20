"""Remove Popular Media characters no longer in cache/popular.json.

build_data.py is add-only, so re-ranking the Popular Media roster (media_ranking.py)
leaves stale rows behind. This drops any `popular` character whose name is not in
the current roster and deletes its thumbnail. Other fandoms are untouched.

Run after media_ranking.py + build_data.py:

    python prune_popular.py
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_JSON = os.path.join(REPO, "data", "characters.json")
THUMB_DIR = os.path.join(REPO, "thumbnails")
ROSTER = "cache/popular.json"


def main():
    roster = {name.lower() for name, _title in json.load(open(ROSTER, encoding="utf-8"))}
    with open(DATA_JSON, encoding="utf-8") as f:
        characters = json.load(f)

    kept, removed = [], []
    for c in characters:
        if c["fandom_internal"] == "popular" and c["name"].lower() not in roster:
            removed.append(c)
        else:
            kept.append(c)

    for c in removed:
        path = os.path.join(THUMB_DIR, c["thumbnail"])
        if os.path.exists(path):
            os.remove(path)

    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False)

    print(f"Removed {len(removed)} stale Popular Media characters. Total now {len(kept)}.")


if __name__ == "__main__":
    main()
