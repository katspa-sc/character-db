import json
import unittest
from unittest.mock import patch

import requests

import media_ranking

parse_candidate_rows = media_ranking.parse_candidate_rows


def _binding(label, article_title):
    return {
        "itemLabel": {"value": label},
        "article": {"value": f"https://en.wikipedia.org/wiki/{article_title}"},
    }


class TestParseCandidateRows(unittest.TestCase):
    def test_maps_label_to_unquoted_article_title(self):
        rows = [_binding("Blue Streak", "Blue_Streak_%28character%29")]
        self.assertEqual(
            parse_candidate_rows(rows),
            {"Blue Streak": "Blue_Streak_(character)"},
        )

    def test_skips_unlabelled_qid_names(self):
        rows = [_binding("Q12379", "Q12379"), _binding("Mario", "Mario")]
        self.assertEqual(parse_candidate_rows(rows), {"Mario": "Mario"})

    def test_first_title_wins_on_duplicate_name(self):
        rows = [_binding("Mario", "Mario"), _binding("Mario", "Mario_(other)")]
        self.assertEqual(parse_candidate_rows(rows), {"Mario": "Mario"})


class TestSelectTop(unittest.TestCase):
    def test_sorts_by_views_desc_and_clips(self):
        scored = [(10, "Low"), (300, "High"), (50, "Mid")]
        self.assertEqual(
            media_ranking.select_top(scored, 2),
            ["High", "Mid"],
        )

    def test_returns_all_when_fewer_than_n(self):
        scored = [(5, "A"), (9, "B")]
        self.assertEqual(media_ranking.select_top(scored, 500), ["B", "A"])


class TestFailureThreshold(unittest.TestCase):
    def test_over_threshold(self):
        self.assertTrue(media_ranking.over_failure_threshold(10, 100))  # 10% > 5%

    def test_at_or_under_threshold(self):
        self.assertFalse(media_ranking.over_failure_threshold(5, 100))  # 5% == 5%

    def test_zero_total_is_not_over(self):
        self.assertFalse(media_ranking.over_failure_threshold(0, 0))


class TestFetchCandidatesRetry(unittest.TestCase):
    def test_retries_on_transient_error_then_succeeds(self):
        good_response = type("Resp", (), {
            "raise_for_status": lambda self: None,
            "text": json.dumps({
                "results": {"bindings": [
                    {"itemLabel": {"value": "Mario"},
                     "article": {"value": "https://en.wikipedia.org/wiki/Mario"}},
                ]}
            }),
        })()

        with patch("media_ranking.requests.get") as mock_get, \
             patch("media_ranking.time.sleep") as mock_sleep:
            mock_get.side_effect = [requests.RequestException("boom"), good_response]

            result = media_ranking.fetch_candidates("Q1569167")

        self.assertEqual(result, {"Mario": "Mario"})
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()
