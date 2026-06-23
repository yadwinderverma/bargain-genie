import pytest
from datetime import datetime, timedelta, timezone
from freezegun import freeze_time
from src.cache import DealCache

def test_purge_old_entries():
    # Arrange
    cache_mgr = DealCache(max_age_days=30)

    # We will pretend "now" is Jan 31, 2024
    with freeze_time("2024-01-31T12:00:00Z"):
        # Create some cache entries with different timestamps

        # 1 day ago (should be kept)
        recent_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

        # Exactly 30 days ago (should be removed, as the check is > cutoff)
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

        # 40 days ago (should be removed)
        old_date = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()

        cache = {
            "recent_deal": {"seen_at": recent_date, "title": "Recent Deal", "source": "test"},
            "cutoff_deal": {"seen_at": cutoff_date, "title": "Cutoff Deal", "source": "test"},
            "old_deal": {"seen_at": old_date, "title": "Old Deal", "source": "test"},
        }

        # Act
        purged_cache = cache_mgr._purge_old_entries(cache)

        # Assert
        assert len(purged_cache) == 1
        assert "recent_deal" in purged_cache
        assert "old_deal" not in purged_cache
        assert "cutoff_deal" not in purged_cache

def test_purge_old_entries_empty():
    # Arrange
    cache_mgr = DealCache(max_age_days=30)

    # Act
    purged_cache = cache_mgr._purge_old_entries({})

    # Assert
    assert len(purged_cache) == 0

def test_purge_old_entries_all_recent():
    # Arrange
    cache_mgr = DealCache(max_age_days=30)

    with freeze_time("2024-01-31T12:00:00Z"):
        recent_date_1 = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        recent_date_2 = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()

        cache = {
            "deal_1": {"seen_at": recent_date_1, "title": "Deal 1", "source": "test"},
            "deal_2": {"seen_at": recent_date_2, "title": "Deal 2", "source": "test"},
        }

        # Act
        purged_cache = cache_mgr._purge_old_entries(cache)

        # Assert
        assert len(purged_cache) == 2
        assert "deal_1" in purged_cache
        assert "deal_2" in purged_cache

def test_purge_old_entries_all_old():
    # Arrange
    cache_mgr = DealCache(max_age_days=30)

    with freeze_time("2024-01-31T12:00:00Z"):
        old_date_1 = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        old_date_2 = (datetime.now(timezone.utc) - timedelta(days=50)).isoformat()

        cache = {
            "deal_1": {"seen_at": old_date_1, "title": "Deal 1", "source": "test"},
            "deal_2": {"seen_at": old_date_2, "title": "Deal 2", "source": "test"},
        }

        # Act
        purged_cache = cache_mgr._purge_old_entries(cache)

        # Assert
        assert len(purged_cache) == 0


import unittest
from unittest.mock import patch, mock_open

class TestDealCache(unittest.TestCase):

    @patch("os.path.exists", return_value=False)
    def test_load_cache_file_not_found(self, mock_exists):
        cache = DealCache(cache_file="dummy_cache.json")
        result = cache._load_cache()
        self.assertEqual(result, {})

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data="{ invalid json: ")
    def test_load_cache_invalid_json(self, mock_file, mock_exists):
        cache = DealCache(cache_file="dummy_cache.json")
        result = cache._load_cache()
        self.assertEqual(result, {})

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open")
    def test_load_cache_io_error(self, mock_file, mock_exists):
        mock_file.side_effect = IOError("Mocked IO Error")
        cache = DealCache(cache_file="dummy_cache.json")
        result = cache._load_cache()
        self.assertEqual(result, {})

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data='{"deal_1": {"seen_at": "2023-01-01T00:00:00Z"}}')
    def test_load_cache_valid_json(self, mock_file, mock_exists):
        cache = DealCache(cache_file="dummy_cache.json")
        result = cache._load_cache()
        self.assertEqual(result, {"deal_1": {"seen_at": "2023-01-01T00:00:00Z"}})

