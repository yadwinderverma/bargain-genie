import unittest
from unittest.mock import patch, mock_open
import json
import os

from src.cache import DealCache

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

if __name__ == "__main__":
    unittest.main()
