import pytest
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
