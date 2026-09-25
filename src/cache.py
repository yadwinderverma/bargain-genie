"""
Deal cache, stored as a JSON file committed to the repo.

A deal is settled only after we alert it, or after we reject it for a real
reason (low score, confirmed bad price). A failed Slack call or a failed
model request leaves the deal unset so the next run can try again.

Rows written by older versions have no "status". Those were saved as soon as
the deal was seen, so they stay settled and are not sent again.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from src.models import Deal

logger = logging.getLogger(__name__)

_SETTLED = {"alerted", "rejected"}
# A later price at least this much cheaper is worth scoring again.
_REOPEN_RATIO = 0.95


class DealCache:
    def __init__(self, cache_file: str | None = None, max_age_days: int | None = None):
        import config

        self.cache_file = cache_file if cache_file is not None else config.CACHE_FILE
        self.max_age_days = max_age_days if max_age_days is not None else config.CACHE_MAX_AGE_DAYS
        self._cache_data = None

    def _load_cache(self) -> dict:
        """Load the cache from disk. Returns an empty dict if it is missing or unreadable."""
        if self._cache_data is not None:
            return self._cache_data

        if not os.path.exists(self.cache_file):
            logger.info("Cache file not found at %s, starting fresh", self.cache_file)
            self._cache_data = {}
            return self._cache_data
        try:
            with open(self.cache_file, "r", encoding="utf-8") as handle:
                self._cache_data = json.load(handle)
                if not isinstance(self._cache_data, dict):
                    raise json.JSONDecodeError("cache root is not an object", "", 0)
                return self._cache_data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read cache file: %s. Starting fresh.", exc)
            self._cache_data = {}
            return self._cache_data

    def _save_cache(self, cache: dict) -> None:
        """Atomically replace the cache file so a crash cannot leave truncated JSON."""
        self._cache_data = cache
        directory = os.path.dirname(self.cache_file) or "."
        os.makedirs(directory, exist_ok=True)
        temporary = self.cache_file + ".tmp"
        try:
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(cache, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            os.replace(temporary, self.cache_file)
            logger.info("Cache saved: %s entries", len(cache))
        except OSError as exc:
            logger.error("Failed to save cache: %s", exc)
            try:
                os.remove(temporary)
            except OSError:
                pass

    def _seen_at(self, entry: dict) -> datetime | None:
        raw = entry.get("seen_at")
        if not isinstance(raw, str):
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            seen = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=timezone.utc)
        return seen

    def _purge_old_entries(self, cache: dict) -> dict:
        """Drop entries older than max_age_days. Unreadable timestamps are kept."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)
        kept = {}
        removed = 0
        for deal_id, entry in cache.items():
            if not isinstance(entry, dict):
                removed += 1
                continue
            seen = self._seen_at(entry)
            if seen is not None and seen <= cutoff:
                removed += 1
                continue
            kept[deal_id] = entry
        if removed:
            logger.info("Purged %s old cache entries", removed)
        return kept

    def _is_settled(self, entry: dict) -> bool:
        status = entry.get("status")
        if status in _SETTLED:
            return True
        # Legacy rows were written for every seen deal, before send succeeded.
        return "status" not in entry

    def _meaningfully_cheaper(self, entry: dict, deal: Deal) -> bool:
        raw = entry.get("sale_price")
        if raw is None or deal.sale_price is None:
            return False
        try:
            previous = float(raw)
        except (TypeError, ValueError):
            return False
        if previous <= 0:
            return False
        return deal.sale_price <= previous * _REOPEN_RATIO

    def filter_new_deals(self, deals: list[Deal]) -> list[Deal]:
        """
        Return deals that still need a decision.

        This does not write the deals into the cache. Call mark_deals_alerted
        or mark_deals_rejected once the outcome is known.
        """
        cache = self._load_cache()
        purged = self._purge_old_entries(cache)
        if len(purged) != len(cache):
            self._save_cache(purged)
        else:
            self._cache_data = purged

        fresh = []
        for deal in deals:
            if not deal.id:
                continue
            entry = purged.get(deal.id)
            if entry and self._is_settled(entry):
                if self._meaningfully_cheaper(entry, deal):
                    logger.info(
                        "Reopening '%s': price fell from %s to %s",
                        deal.title,
                        entry.get("sale_price"),
                        deal.sale_price,
                    )
                else:
                    continue
            fresh.append(deal)

        logger.info("Cache filter: %s deals in, %s still open", len(deals), len(fresh))
        return fresh

    def _record(self, deals: list[Deal], status: str) -> None:
        cache = self._load_cache()
        now = datetime.now(timezone.utc).isoformat()
        changed = False
        for deal in deals:
            if not deal.id:
                continue
            entry = cache.get(deal.id)
            if not isinstance(entry, dict):
                entry = {"seen_at": now}
            entry["seen_at"] = entry.get("seen_at") or now
            entry["title"] = deal.title
            entry["source"] = deal.source
            entry["status"] = status
            if deal.sale_price is not None:
                entry["sale_price"] = deal.sale_price
            if status == "alerted":
                entry["alerted"] = True
            cache[deal.id] = entry
            changed = True
        if changed:
            self._save_cache(cache)

    def mark_deals_alerted(self, deals: list[Deal]) -> None:
        """Record deals that were actually delivered to Slack."""
        self._record(deals, "alerted")

    def mark_deals_rejected(self, deals: list[Deal]) -> None:
        """Record deals we have decided not to alert, so they are not scored again."""
        self._record(deals, "rejected")
