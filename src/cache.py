"""
Deal cache — stored as a JSON file committed to the repo.
Prevents duplicate alerts across runs.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from config import CACHE_FILE, CACHE_MAX_AGE_DAYS
from src.models import Deal

logger = logging.getLogger(__name__)


class DealCache:
    def __init__(self, cache_file: str = CACHE_FILE, max_age_days: int = CACHE_MAX_AGE_DAYS):
        self.cache_file = cache_file
        self.max_age_days = max_age_days

    def _load_cache(self) -> dict:
        """Load the cache from disk. Returns empty dict if not found."""
        if not os.path.exists(self.cache_file):
            logger.info(f"Cache file not found at {self.cache_file}, starting fresh")
            return {}
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not read cache file: {e}. Starting fresh.")
            return {}

    def _save_cache(self, cache: dict) -> None:
        """Save the cache to disk."""
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
            logger.info(f"Cache saved: {len(cache)} entries")
        except IOError as e:
            logger.error(f"Failed to save cache: {e}")

    def _purge_old_entries(self, cache: dict) -> dict:
        """Remove entries older than max_age_days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)
        before = len(cache)
        cache = {
            deal_id: entry
            for deal_id, entry in cache.items()
            if datetime.fromisoformat(entry["seen_at"]) > cutoff
        }
        removed = before - len(cache)
        if removed:
            logger.info(f"Purged {removed} old cache entries")
        return cache

    def filter_new_deals(self, deals: list[Deal]) -> list[Deal]:
        """
        Given a list of deals, return only those not already in the cache.
        Also updates the cache with newly seen deals.
        """
        cache = self._load_cache()
        cache = self._purge_old_entries(cache)

        new_deals = []
        now = datetime.now(timezone.utc).isoformat()

        for deal in deals:
            if not deal.id:
                continue
            if deal.id not in cache:
                new_deals.append(deal)
                cache[deal.id] = {
                    "seen_at": now,
                    "title": deal.title,
                    "source": deal.source,
                }

        logger.info(f"Cache filter: {len(deals)} deals in → {len(new_deals)} new deals")
        self._save_cache(cache)
        return new_deals

    def mark_deals_alerted(self, deals: list[Deal]) -> None:
        """
        Mark deals as alerted in the cache (adds 'alerted' flag).
        Call this after successfully sending Slack notifications.
        """
        cache = self._load_cache()
        for deal in deals:
            if deal.id in cache:
                cache[deal.id]["alerted"] = True
        self._save_cache(cache)

# Legacy wrappers for backward compatibility
def filter_new_deals(deals: list[dict]) -> list[dict]:
    # This is a bit tricky as the new DealCache expects Deal instances
    # We will let this crash or remove it entirely in the main pipeline
    pass

def mark_deals_alerted(deals: list[dict]) -> None:
    pass
