"""
Fetches deals from OzBargain RSS feed.
No API key required — OzBargain provides a public RSS feed.
"""

import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional

import feedparser

from config import (
    MIN_DISCOUNT_PERCENT, MIN_OZBARGAIN_VOTES, OZBARGAIN_MAX_ITEMS,
    OZBARGAIN_RSS_URL, OZBARGAIN_TRUSTED, OZBARGAIN_MIN_VOTES_TRUSTED,
    SEARCH_QUERIES, OZBARGAIN_FREEBIES_ENABLED, OZBARGAIN_FREEBIES_MIN_VOTES,
)
from src.models import Deal
from src.fetchers.base import DealFetcher

logger = logging.getLogger(__name__)

# Pre-compile regex patterns to avoid repeated compilation overhead in loops
FREEBIE_PATTERN = re.compile(
    r"\bfree\b|\bfreebie\b|\$0\b|free\s+trial|free\s+sub|no\s+cost",
    re.IGNORECASE,
)
LIMITED_DURATION_PATTERN = re.compile(
    r"\d+\s*(day|week|month|year)s?\s*free|free\s*trial|limited\s*time",
    re.IGNORECASE,
)
LIFETIME_DURATION_PATTERN = re.compile(
    r"lifetime|forever|permanent|always\s*free",
    re.IGNORECASE,
)

# Pre-compile search queries for performance
_COMPILED_SEARCH_QUERIES = []
for query_def in SEARCH_QUERIES:
    if isinstance(query_def, str):
        _COMPILED_SEARCH_QUERIES.append({
            "type": "str",
            "keywords": query_def.lower().split()
        })
    elif isinstance(query_def, dict):
        kw_list = [kw.lower() for kw in query_def.get("keywords", [])]
        ex_list = [ex.lower() for ex in query_def.get("exclude", [])]
        if not kw_list:
            continue

        _COMPILED_SEARCH_QUERIES.append({
            "type": "dict",
            "keywords": [re.compile(rf"\b{re.escape(kw)}\b") for kw in kw_list],
            "excludes": [re.compile(rf"\b{re.escape(ex)}\b") for ex in ex_list]
        })



_cached_feed = None
_cached_time = 0

def _get_ozbargain_feed():
    global _cached_feed, _cached_time
    now = time.time()
    if _cached_feed is None or now - _cached_time > 60:
        logger.info(f"Fetching OzBargain RSS feed: {OZBARGAIN_RSS_URL}")
        _cached_feed = feedparser.parse(OZBARGAIN_RSS_URL)
        _cached_time = now
    return _cached_feed


def _parse_discount_from_title(title: str) -> Optional[float]:
    """Try to extract a discount percentage from the deal title."""
    # Match patterns like "50% off", "50%off", "50 % off"
    match = re.search(r"(\d+)\s*%\s*off", title, re.IGNORECASE)
    if match:
        return float(match.group(1))
    # Match patterns like "half price", "half-price"
    if re.search(r"half[\s-]?price", title, re.IGNORECASE):
        return 50.0
    return None


def _parse_price_from_description(description: str) -> tuple[Optional[float], Optional[float]]:
    """
    Try to extract original and sale prices from the deal description HTML.
    Returns (original_price, sale_price).
    """
    # Look for price patterns like $99.99 or $1,299
    prices = re.findall(r"\$[\d,]+(?:\.\d{2})?", description)
    prices_clean = []
    for p in prices:
        try:
            prices_clean.append(float(p.replace("$", "").replace(",", "")))
        except ValueError:
            pass

    if len(prices_clean) >= 2:
        # Assume higher price is original, lower is sale
        original = max(prices_clean[:4])  # Look at first 4 price mentions
        sale = min(prices_clean[:4])
        if original > sale:
            return original, sale
    elif len(prices_clean) == 1:
        return None, prices_clean[0]

    return None, None


def _parse_votes(entry) -> int:
    """Extract vote count from OzBargain RSS entry tags."""
    # OzBargain includes vote info in tags or summary
    # Try to find it in the description
    description = entry.get("summary", "")
    vote_match = re.search(r"(\d+)\s*(?:votes?|clicks?)", description, re.IGNORECASE)
    if vote_match:
        return int(vote_match.group(1))
    # Fallback: check tags
    tags = entry.get("tags", [])
    for tag in tags:
        if "vote" in tag.get("term", "").lower():
            try:
                return int(re.search(r"\d+", tag["term"]).group())
            except (AttributeError, ValueError):
                pass
    return 0


def _matches_search_queries(title: str, description: str) -> bool:
    """
    Check if a deal title/description matches any of the user's search queries.
    All 'keywords' must appear (case-insensitive) and none of 'exclude' must appear.
    """
    text = (title + " " + description).lower()
    for query in _COMPILED_SEARCH_QUERIES:
        if query["type"] == "str":
            if all(kw in text for kw in query["keywords"]):
                return True
        elif query["type"] == "dict":
            has_all_keywords = all(bool(kw_re.search(text)) for kw_re in query["keywords"])
            if not has_all_keywords:
                continue
            has_any_exclude = any(bool(ex_re.search(text)) for ex_re in query["excludes"])
            if not has_any_exclude:
                return True
    return False


class OzBargainFetcher(DealFetcher):
    def fetch(self) -> list[Deal]:
        """
        Fetch and parse deals from OzBargain RSS feed.
        Returns a list of Deal objects.
        """
        deals = []

        try:
            feed = _get_ozbargain_feed()
            if feed.bozo and not feed.entries:
                logger.error(f"Failed to parse OzBargain RSS: {feed.bozo_exception}")
                return deals

            logger.info(f"Found {len(feed.entries)} entries in OzBargain feed")

            for entry in feed.entries[:OZBARGAIN_MAX_ITEMS]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                description = entry.get("summary", "")
                published = entry.get("published", "")

                # Try to extract discount
                discount_pct = _parse_discount_from_title(title)
                original_price, sale_price = _parse_price_from_description(description)

                # Calculate discount from prices if not in title
                if discount_pct is None and original_price and sale_price and original_price > 0:
                    discount_pct = round((1 - sale_price / original_price) * 100, 1)

                votes = _parse_votes(entry)

                # --- Product filter: only keep deals matching your SEARCH_QUERIES ---
                if not _matches_search_queries(title, description):
                    continue

                # Apply filters
                passes_discount = discount_pct is not None and discount_pct >= MIN_DISCOUNT_PERCENT
                passes_votes = votes >= MIN_OZBARGAIN_VOTES

                # OzBargain trust logic:
                if OZBARGAIN_TRUSTED:
                    community_validated = votes >= OZBARGAIN_MIN_VOTES_TRUSTED
                    passes = passes_discount or passes_votes or community_validated
                else:
                    passes = passes_discount or passes_votes

                if not passes:
                    continue

                deal = Deal(
                    id=f"ozb_{entry.get('id', link)}",
                    source="ozbargain",
                    title=title,
                    url=link,
                    description=description[:500],  # Truncate for LLM
                    original_price=original_price,
                    sale_price=sale_price,
                    discount_pct=discount_pct,
                    votes=votes,
                    community_validated=OZBARGAIN_TRUSTED and votes >= OZBARGAIN_MIN_VOTES_TRUSTED,
                    published=published,
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                )
                deals.append(deal)

            logger.info(f"OzBargain: {len(deals)} deals passed initial filters")

        except Exception as e:
            logger.error(f"Error fetching OzBargain deals: {e}", exc_info=True)

        return deals

def fetch_ozbargain_deals() -> list[dict]:
    # Legacy wrapper
    pass


def _is_freebie(title: str, description: str, tags: list) -> bool:
    """
    Detect if an OzBargain deal is a freebie.
    OzBargain doesn't have a separate freebies feed — freebies appear in the main
    feed and are identified by tags, price ($0/free), or title keywords.
    """
    # Check tags first (most reliable)
    tag_terms = [t.get("term", "").lower() for t in tags]
    if "freebie" in tag_terms or "free" in tag_terms:
        return True

    # Check title for free signals
    text = (title + " " + description).lower()
    return bool(FREEBIE_PATTERN.search(text))


class OzBargainFreebieFetcher(DealFetcher):
    def fetch(self) -> list[Deal]:
        """
        Extract freebies from the main OzBargain deals feed.
        OzBargain has no separate freebies RSS — freebies are tagged in the main feed.
        No product filter — all well-upvoted freebies are worth alerting.
        """
        if not OZBARGAIN_FREEBIES_ENABLED:
            return []

        logger.info(f"Scanning OzBargain main feed for freebies")
        freebies = []

        try:
            feed = _get_ozbargain_feed()
            if feed.bozo and not feed.entries:
                logger.error(f"Failed to parse OzBargain RSS: {feed.bozo_exception}")
                return freebies

            for entry in feed.entries[:OZBARGAIN_MAX_ITEMS]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                description = entry.get("summary", "")
                published = entry.get("published", "")
                tags = entry.get("tags", [])
                votes = _parse_votes(entry)

                if not _is_freebie(title, description, tags):
                    continue

                if votes < OZBARGAIN_FREEBIES_MIN_VOTES:
                    logger.debug(f"Freebie skipped ({votes} votes < {OZBARGAIN_FREEBIES_MIN_VOTES}): {title[:60]}")
                    continue

                # Detect duration
                text_to_search = title + " " + description
                is_limited = bool(LIMITED_DURATION_PATTERN.search(text_to_search))
                is_lifetime = bool(LIFETIME_DURATION_PATTERN.search(text_to_search))
                duration_note = "lifetime" if is_lifetime else ("limited time" if is_limited else "")

                deal = Deal(
                    id=f"ozb_free_{entry.get('id', link)}",
                    source="ozbargain_freebie",
                    title=title,
                    url=link,
                    description=description[:500],
                    original_price=None,
                    sale_price=0.0,
                    discount_pct=100.0,
                    votes=votes,
                    community_validated=True,
                    is_freebie=True,
                    duration_note=duration_note,
                    published=published,
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                )
                freebies.append(deal)

            logger.info(f"OzBargain freebies: {len(freebies)} found (>= {OZBARGAIN_FREEBIES_MIN_VOTES} votes)")

        except Exception as e:
            logger.error(f"Error fetching OzBargain freebies: {e}", exc_info=True)

        return freebies

def fetch_ozbargain_freebies() -> list[dict]:
    # Legacy wrapper
    pass
