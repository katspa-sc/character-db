import json
import os
import tempfile
import unittest
from unittest.mock import patch

from parsers.ranked_list_parser import RankedListParser


def _source(items):
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(items, f)
    return path


def _response(title_to_source):
    return {"query": {"pages": {
        str(i): {"title": t, "original": {"source": s}}
        for i, (t, s) in enumerate(title_to_source.items())
    }}}


class TestParseCharacters(unittest.TestCase):
    def test_pair_format_keys_result_by_display_name(self):
        # Popular Media: page looked up by enwiki title, keyed by display name.
        path = _source([["Batman", "Batman"], ["Sherlock", "Sherlock_Holmes"]])
        parser = RankedListParser("http://x")
        resp = _response({"Batman": "b.png", "Sherlock_Holmes": "s.png"})
        try:
            with patch.object(parser, "_fetch_batch", return_value=resp):
                result = parser.parse_characters(path)
        finally:
            os.remove(path)
        self.assertEqual(result, {"Batman": "b.png", "Sherlock": "s.png"})

    def test_flat_name_list_uses_name_as_title(self):
        path = _source(["Spider-Man"])
        parser = RankedListParser("http://x")
        resp = _response({"Spider-Man": "sm.png"})
        try:
            with patch.object(parser, "_fetch_batch", return_value=resp):
                result = parser.parse_characters(path)
        finally:
            os.remove(path)
        self.assertEqual(result, {"Spider-Man": "sm.png"})

    def test_top_n_clips_before_fetching(self):
        path = _source(["A", "B", "C"])
        parser = RankedListParser("http://x", top_n=2)
        try:
            with patch.object(parser, "_fetch_batch", return_value=_response({})) as m:
                parser.parse_characters(path)
        finally:
            os.remove(path)
        # Only the top 2 titles should reach the API.
        self.assertEqual(m.call_args.args[0], ["A", "B"])


class TestFetchBatch(unittest.TestCase):
    def test_sends_pilicense_any(self):
        parser = RankedListParser("http://x")
        fake = type("R", (), {"status_code": 200,
                              "raise_for_status": lambda self: None,
                              "json": lambda self: {}})()
        with patch("parsers.ranked_list_parser.requests.get", return_value=fake) as m:
            parser._fetch_batch(["Batman"])
        self.assertEqual(m.call_args.kwargs["params"]["pilicense"], "any")


if __name__ == "__main__":
    unittest.main()
