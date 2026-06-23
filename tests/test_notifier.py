import pytest
import requests
import logging
from unittest.mock import patch, MagicMock

from src.notifier import SlackNotifier
from src.models import Deal

@patch.dict('os.environ', {'SLACK_WEBHOOK_URL': 'https://hooks.slack.com/services/SECRET/TOKEN'})
def test_slack_notifier_redacts_webhook_url_on_alerts(caplog):
    notifier = SlackNotifier()
    deal = Deal(
        id="test_deal_1",
        title="Test Deal",
        source="ozbargain",
        url="https://example.com/deal",
        llm_score=10,
        llm_reason="Great deal",
        is_freebie=False,
        original_price=100.0,
        sale_price=50.0,
        discount_pct=50.0
    )

    with patch('requests.post') as mock_post:
        # Simulate a RequestException with the webhook URL in its message
        mock_post.side_effect = requests.RequestException("Error connecting to https://hooks.slack.com/services/SECRET/TOKEN")

        with caplog.at_level(logging.ERROR):
            success = notifier.send_slack_alerts([deal])

        assert success is False

        # Verify the logged message doesn't contain the secret URL
        assert "https://hooks.slack.com/services/SECRET/TOKEN" not in caplog.text
        # Verify the redacted string is present
        assert "***REDACTED***" in caplog.text
        assert "Failed to send Slack message chunk 1: Error connecting to ***REDACTED***" in caplog.text

@patch.dict('os.environ', {'SLACK_WEBHOOK_URL': 'https://hooks.slack.com/services/SECRET/TOKEN'})
def test_slack_notifier_redacts_webhook_url_on_error(caplog):
    notifier = SlackNotifier()

    with patch('requests.post') as mock_post:
        # Simulate a RequestException with the webhook URL in its message
        mock_post.side_effect = requests.RequestException("Error posting to https://hooks.slack.com/services/SECRET/TOKEN")

        with caplog.at_level(logging.ERROR):
            notifier.send_slack_error_message("Test error")

        # Verify the logged message doesn't contain the secret URL
        assert "https://hooks.slack.com/services/SECRET/TOKEN" not in caplog.text
        # Verify the redacted string is present
        assert "***REDACTED***" in caplog.text
        assert "Failed to send error message to Slack: Error posting to ***REDACTED***" in caplog.text
from src.notifier import SlackNotifier, SOURCE_EMOJI

@pytest.fixture
def notifier(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "http://test-webhook")
    return SlackNotifier()

def test_get_source_emoji_exact_match(notifier):
    """Test that the correct emoji is returned for exact string matches."""
    assert notifier._get_source_emoji("ozbargain") == "🔥"
    assert notifier._get_source_emoji("amazon") == "📦"
    assert notifier._get_source_emoji("jbhifi") == "🎵"

def test_get_source_emoji_case_insensitivity(notifier):
    """Test that case does not matter for matching source strings."""
    assert notifier._get_source_emoji("Ozbargain") == "🔥"
    assert notifier._get_source_emoji("AMAZON") == "📦"
    assert notifier._get_source_emoji("Kogan") == "🛒"

def test_get_source_emoji_partial_match(notifier):
    """Test that the correct emoji is returned even if the source is embedded in a larger string."""
    assert notifier._get_source_emoji("some_amazon_deal") == "📦"
    assert notifier._get_source_emoji("ozbargain_freebie_thread") == "🆓"

def test_get_source_emoji_fallback(notifier):
    """Test that unknown sources return the fallback emoji."""
    assert notifier._get_source_emoji("unknown_source") == "💰"
    assert notifier._get_source_emoji("ebay") == "💰"
    assert notifier._get_source_emoji("") == "💰"
import unittest
from unittest.mock import patch, MagicMock
import requests
import os
from src.notifier import SlackNotifier, send_slack_error_message

def test_send_slack_error_message_request_exception():
    with patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "http://test.webhook"}):
        with patch("requests.post", side_effect=requests.RequestException("Mocked error")) as mock_post:
            with patch("src.notifier.logger.error") as mock_logger:
                send_slack_error_message("Test error message")

                mock_post.assert_called_once()
                mock_logger.assert_called_once_with("Failed to send error message to Slack: Mocked error")

class TestSlackNotifier(unittest.TestCase):
    @patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "http://fake-url.com"})
    def setUp(self):
        self.notifier = SlackNotifier()

    def test_format_price_none(self):
        self.assertEqual(self.notifier._format_price(None), "N/A")

    def test_format_price_zero(self):
        self.assertEqual(self.notifier._format_price(0.0), "$0.00")
        self.assertEqual(self.notifier._format_price(0), "$0.00")

    def test_format_price_regular(self):
        self.assertEqual(self.notifier._format_price(9.99), "$9.99")
        self.assertEqual(self.notifier._format_price(50.5), "$50.50")

    def test_format_price_large(self):
        self.assertEqual(self.notifier._format_price(1234.5), "$1,234.50")
        self.assertEqual(self.notifier._format_price(1234567.89), "$1,234,567.89")

    def test_format_price_rounding(self):
        self.assertEqual(self.notifier._format_price(19.999), "$20.00")
        self.assertEqual(self.notifier._format_price(19.994), "$19.99")

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

