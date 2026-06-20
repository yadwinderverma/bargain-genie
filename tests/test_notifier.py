import pytest
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
