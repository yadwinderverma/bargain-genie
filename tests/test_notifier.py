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
