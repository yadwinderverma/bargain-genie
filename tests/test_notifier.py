import pytest
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

if __name__ == '__main__':
    unittest.main()
