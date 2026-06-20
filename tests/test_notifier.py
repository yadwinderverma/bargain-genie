import unittest
import os
from unittest.mock import patch
from src.notifier import SlackNotifier

class TestSlackNotifierScoreEmoji(unittest.TestCase):
    def setUp(self):
        # Prevent errors about SLACK_WEBHOOK_URL missing during test
        with patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "http://dummy"}):
            self.notifier = SlackNotifier()

    def test_get_score_emoji_top_tier(self):
        # Range (9, 11) -> 9, 10
        self.assertEqual(self.notifier._get_score_emoji(9), "🏆")
        self.assertEqual(self.notifier._get_score_emoji(10), "🏆")

    def test_get_score_emoji_mid_tier(self):
        # Range (7, 9) -> 7, 8
        self.assertEqual(self.notifier._get_score_emoji(7), "⭐")
        self.assertEqual(self.notifier._get_score_emoji(8), "⭐")

    def test_get_score_emoji_low_tier(self):
        # Range (5, 7) -> 5, 6
        self.assertEqual(self.notifier._get_score_emoji(5), "👍")
        self.assertEqual(self.notifier._get_score_emoji(6), "👍")

    def test_get_score_emoji_below_range(self):
        # Below 5 should return "💡"
        self.assertEqual(self.notifier._get_score_emoji(4), "💡")
        self.assertEqual(self.notifier._get_score_emoji(0), "💡")
        self.assertEqual(self.notifier._get_score_emoji(-1), "💡")

    def test_get_score_emoji_above_range(self):
        # 11 or higher should return "💡"
        self.assertEqual(self.notifier._get_score_emoji(11), "💡")
        self.assertEqual(self.notifier._get_score_emoji(100), "💡")

if __name__ == '__main__':
    unittest.main()
