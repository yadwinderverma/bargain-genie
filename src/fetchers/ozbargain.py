"""
Fetches deals from the OzBargain RSS feed.

OzBargain publishes votes and the merchant URL on each item (`ozb_meta`),
and puts the price in the title. The summary HTML does not contain the vote
count. A browser user agent is challenged by Cloudflare; the feedparser
user agent is the one that gets the feed.
"""

import html
import logging
import re
import threading
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import feedparser
import requests

from config import (
    MIN_DISCOUNT_PERCENT,
    MIN_OZBARGAIN_VOTES,
    OZBARGAIN_FREEBIES_ENABLED,
    OZBARGAIN_FREEBIES_MATCH_WATCHLIST,
    OZBARGAIN_FREEBIES_MIN_VOTES,
    OZBARGAIN_MAX_ITEMS,
    OZBARGAIN_MIN_VOTES_TRUSTED,
    OZBARGAIN_RSS_URL,
    OZBARGAIN_TRUSTED,
)
from src.fetchers.base import DealFetcher
from src.models import Deal
from src.watchlist import matches_any

logger = logging.getLogger(__name__)

# Cloudflare serves the feed to this agent and challenges a browser UA.
_FEED_HEADERS = {"User-Agent": "UniversalFeedParser/6.0.11"}
_FEED_LOCK = threading.Lock()
_cached_feed = None
_cached_time = 0.0

# Delivery clauses sit after the product price and are full of $0.
_DELIVERY_RE = re.compile(
    r"(?:"
    r"\+\s*(?:[A-Z]{0,2}\$\s*\d[\d,]*(?:\.\d{2})?\s*)?delivery\b.*$"
    r"|\+\s*free\s+(?:shipping|delivery|postage)\b.*$"
    r"|\+\s*shipping\b.*$"
    r")",
    re.IGNORECASE,
)
_MONEY_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:A\$|AU\$|\$)\s*(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{2}))?"
)
_REFERENCE_PRICE_RE = re.compile(
    r"\b(?:RRP|Was|were)\b[^$\n]{0,20}((?:A\$|AU\$|\$)\s*\d[\d,]*(?:\.\d{2})?)",
    re.IGNORECASE,
)
_SHIPPING_NEAR_RE = re.compile(
    r"(delivery|postage|shipping|freight|c&c|click\s*&?\s*collect|prime|in[-\s]?store|pick[\s-]?up)",
    re.IGNORECASE,
)
_CONTRACT_RE = re.compile(
    r"(\d+\s*[- ]?months?\b.{0,40}\b(?:plan|sim)|sim[\s-]?only|/m\b|per\s+month)",
    re.IGNORECASE,
)
_FREE_SHIPPING_RE = re.compile(r"\bfree\s+(?:shipping|delivery|postage|freight)\b", re.IGNORECASE)
_FREEBIE_RE = re.compile(r"\bfreebie\b|\bfree\s*:|\bfree\b", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
LIMITED_DURATION_PATTERN = re.compile(
    r"\d+\s*(day|week|month|year)s?\s*free|free\s*trial|limited\s*time",
    re.IGNORECASE,
)
LIFETIME_DURATION_PATTERN = re.compile(
    r"lifetime|forever|permanent|always\s*free",
    re.IGNORECASE,
)


def _strip_html(text: str) -> str:
    plain = _TAG_RE.sub(" ", text or "")
    plain = html.unescape(plain)
    return _WHITESPACE_RE.sub(" ", plain).strip()


def _get_ozbargain_feed():
    """Fetch the feed once per minute. Concurrent fetchers share one download."""
    global _cached_feed, _cached_time
    with _FEED_LOCK:
        now = time.time()
        if _cached_feed is not None and now - _cached_time < 60:
            return _cached_feed

        logger.info("Fetching OzBargain RSS feed: %s", OZBARGAIN_RSS_URL)
        feed = None
        try:
            response = requests.get(OZBARGAIN_RSS_URL, headers=_FEED_HEADERS, timeout=15)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
        except Exception as exc:
            logger.warning("OzBargain feed request failed (%s); trying feedparser directly", exc)
            feed = feedparser.parse(OZBARGAIN_RSS_URL)

        if feed is not None and (feed.entries or not feed.bozo):
            _cached_feed = feed
            _cached_time = now
        return feed


def _parse_discount_from_title(title: str) -> Optional[float]:
    """Try to extract a discount percentage from the deal title."""
    match = re.search(r"(\d+)\s*%\s*off", title, re.IGNORECASE)
    if match:
        return float(match.group(1))
    if re.search(r"half[\s-]?price", title, re.IGNORECASE):
        return 50.0
    return None


def _parse_price_from_description(description: str) -> tuple[Optional[float], Optional[float]]:
    """
    Try to extract original and sale prices from the deal description HTML.
    Returns (original_price, sale_price).
    """
    prices = re.findall(r"\$[\d,]+(?:\.\d{2})?", description)
    prices_clean = []
    for price in prices:
        try:
            prices_clean.append(float(price.replace("$", "").replace(",", "")))
        except ValueError:
            pass

    if len(prices_clean) >= 2:
        original = max(prices_clean[:4])
        sale = min(prices_clean[:4])
        if original > sale:
            return original, sale
    elif len(prices_clean) == 1:
        return None, prices_clean[0]

    return None, None


def _parse_votes(entry) -> int:
    """Positive OzBargain votes. The feed puts these on ozb_meta, not in the summary."""
    meta = entry.get("ozb_meta") or {}
    if isinstance(meta, dict) and "votes-pos" in meta:
        try:
            return max(0, int(str(meta.get("votes-pos") or "0").strip()))
        except ValueError:
            pass

    description = entry.get("summary", "")
    vote_match = re.search(r"(\d+)\s*(?:votes?|clicks?)", description, re.IGNORECASE)
    if vote_match:
        return int(vote_match.group(1))
    tags = entry.get("tags", [])
    for tag in tags:
        if "vote" in tag.get("term", "").lower():
            try:
                return int(re.search(r"\d+", tag["term"]).group())
            except (AttributeError, ValueError):
                pass
    return 0


def _node_id(entry) -> str:
    """Stable numeric id. The RSS guid looks like '976449 at https://www.ozbargain.com.au'."""
    link = entry.get("link") or ""
    match = re.search(r"/node/(\d+)", link)
    if match:
        return match.group(1)
    raw_id = str(entry.get("id") or "")
    match = re.match(r"(\d+)\b", raw_id)
    if match:
        return match.group(1)
    return raw_id or link or "unknown"


def _merchant_url(entry) -> str:
    meta = entry.get("ozb_meta") or {}
    if not isinstance(meta, dict):
        return ""
    candidate = (meta.get("url") or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return candidate
    return ""


def _product_clause(title: str) -> str:
    """Title text that describes the product, with the delivery tail removed."""
    clause = (title or "").split("@", 1)[0]
    return _DELIVERY_RE.sub("", clause).strip()


def _money_value(amount: str, cents: Optional[str]) -> float:
    whole = amount.replace(",", "")
    if cents:
        return float(f"{whole}.{cents}")
    return float(whole)


def _is_incidental_zero(clause: str, start: int, amount: float) -> bool:
    """$0 next to delivery or click-and-collect is not the product price."""
    if amount != 0:
        return False
    window = clause[max(0, start - 30):start + 40]
    if _SHIPPING_NEAR_RE.search(window):
        return True
    prefix = clause[:start]
    if prefix.count("(") > prefix.count(")"):
        open_at = prefix.rfind("(")
        close_at = clause.find(")", start)
        paren = clause[open_at:close_at + 1 if close_at != -1 else len(clause)]
        if _SHIPPING_NEAR_RE.search(paren):
            return True
    return False


def _is_contract(title: str) -> bool:
    """Handset-for-$0 deals that only exist with a paid plan."""
    return bool(_CONTRACT_RE.search(title or ""))


def _parse_offer_from_title(title: str) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Return (sale_price, original_price, discount_pct) from an OzBargain title.

    The first real product price is the sale price. RRP/Was is the original.
    Dollar amounts inside the delivery clause are ignored, so '($0 C&C)' cannot
    become the price.
    """
    clause = _product_clause(title)
    reference = None
    reference_match = _REFERENCE_PRICE_RE.search(clause)
    if reference_match:
        reference_text = reference_match.group(1)
        reference_amount = _MONEY_RE.search(reference_text)
        if reference_amount:
            reference = _money_value(reference_amount.group(1), reference_amount.group(2))

    sale = None
    for match in _MONEY_RE.finditer(clause):
        amount = _money_value(match.group(1), match.group(2))
        if _is_incidental_zero(clause, match.start(), amount):
            continue
        if reference is not None and abs(amount - reference) < 0.001:
            continue
        sale = amount
        break

    stated = _parse_discount_from_title(clause)
    computed = None
    if reference is not None and sale is not None and reference > sale:
        computed = round((1 - sale / reference) * 100, 1)
    return sale, reference, computed if computed is not None else stated


def _matches_search_queries(title: str, description: str) -> bool:
    """True when the title and summary match a watchlist query."""
    return matches_any(title, description)


def _is_freebie(title: str, _description: str, tags: list) -> bool:
    """
    A freebie is free to take home. '$0 C&C' and 'free shipping' are not freebies.

    The word 'free' is only trusted in the title or a freebie tag. Deal blurbs
    say 'free returns' often enough to make the summary useless here.
    """
    terms = {tag.get("term", "").lower() for tag in tags}
    if "freebie" in terms or "freebies" in terms:
        return True
    if _is_contract(title):
        return False

    clause = _FREE_SHIPPING_RE.sub(" ", _product_clause(title))
    if _FREEBIE_RE.search(clause):
        return True

    sale, _, _ = _parse_offer_from_title(title)
    return sale == 0


class OzBargainFetcher(DealFetcher):
    def fetch(self) -> list[Deal]:
        """Fetch watchlist deals from the OzBargain RSS feed."""
        deals = []
        try:
            feed = _get_ozbargain_feed()
            if feed is None or (feed.bozo and not feed.entries):
                logger.error("Failed to parse OzBargain RSS: %s", getattr(feed, "bozo_exception", "no feed"))
                return deals

            logger.info("Found %s entries in OzBargain feed", len(feed.entries))
            for entry in feed.entries[:OZBARGAIN_MAX_ITEMS]:
                deal = _deal_from_entry(entry)
                if deal is not None:
                    deals.append(deal)
            logger.info("OzBargain: %s deals passed initial filters", len(deals))
        except Exception as exc:
            logger.error("Error fetching OzBargain deals: %s", exc, exc_info=True)
        return deals


def _deal_from_entry(entry) -> Optional[Deal]:
    title = entry.get("title", "")
    link = entry.get("link", "")
    description = _strip_html(entry.get("summary", ""))
    published = entry.get("published", "")

    if _is_contract(title):
        logger.debug("Skipping contract deal: %s", title[:80])
        return None
    if _is_freebie(title, entry.get("summary", ""), entry.get("tags") or []):
        return None
    if not _matches_search_queries(title, description):
        return None

    sale_price, original_price, discount_pct = _parse_offer_from_title(title)
    if sale_price is None or original_price is None:
        described_original, described_sale = _parse_price_from_description(description)
        sale_price = sale_price if sale_price is not None else described_sale
        original_price = original_price if original_price is not None else described_original
        if discount_pct is None and original_price and sale_price and original_price > 0:
            discount_pct = round((1 - sale_price / original_price) * 100, 1)

    votes = _parse_votes(entry)
    passes_discount = discount_pct is not None and discount_pct >= MIN_DISCOUNT_PERCENT
    passes_votes = votes >= MIN_OZBARGAIN_VOTES
    community_validated = OZBARGAIN_TRUSTED and votes >= OZBARGAIN_MIN_VOTES_TRUSTED
    if OZBARGAIN_TRUSTED:
        passes = passes_discount or passes_votes or community_validated
    else:
        passes = passes_discount or passes_votes
    if not passes:
        return None

    return Deal(
        id=f"ozb_{_node_id(entry)}",
        source="ozbargain",
        title=title,
        url=link,
        merchant_url=_merchant_url(entry),
        description=description[:500],
        original_price=original_price,
        sale_price=sale_price,
        discount_pct=discount_pct,
        votes=votes,
        community_validated=community_validated,
        published=published,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


class OzBargainFreebieFetcher(DealFetcher):
    def fetch(self) -> list[Deal]:
        """
        Freebies are tagged in the main feed. There is no separate freebie feed.
        '$0 delivery' is not a freebie. With the watchlist flag on, a freebie
        still has to match SEARCH_QUERIES.
        """
        if not OZBARGAIN_FREEBIES_ENABLED:
            return []

        logger.info("Scanning OzBargain main feed for freebies")
        freebies = []
        try:
            feed = _get_ozbargain_feed()
            if feed is None or (feed.bozo and not feed.entries):
                logger.error("Failed to parse OzBargain RSS: %s", getattr(feed, "bozo_exception", "no feed"))
                return freebies

            for entry in feed.entries[:OZBARGAIN_MAX_ITEMS]:
                title = entry.get("title", "")
                description = entry.get("summary", "")
                tags = entry.get("tags", [])
                votes = _parse_votes(entry)
                if not _is_freebie(title, description, tags):
                    continue
                if votes < OZBARGAIN_FREEBIES_MIN_VOTES:
                    logger.debug(
                        "Freebie skipped (%s votes < %s): %s",
                        votes,
                        OZBARGAIN_FREEBIES_MIN_VOTES,
                        title[:60],
                    )
                    continue
                plain = _strip_html(description)
                if OZBARGAIN_FREEBIES_MATCH_WATCHLIST and not _matches_search_queries(title, plain):
                    continue

                text = f"{title} {plain}"
                if LIFETIME_DURATION_PATTERN.search(text):
                    duration_note = "lifetime"
                elif LIMITED_DURATION_PATTERN.search(text):
                    duration_note = "limited time"
                else:
                    duration_note = ""

                freebies.append(Deal(
                    id=f"ozb_free_{_node_id(entry)}",
                    source="ozbargain_freebie",
                    title=title,
                    url=entry.get("link", ""),
                    merchant_url=_merchant_url(entry),
                    description=plain[:500],
                    original_price=None,
                    sale_price=0.0,
                    discount_pct=100.0,
                    votes=votes,
                    community_validated=True,
                    is_freebie=True,
                    duration_note=duration_note,
                    published=entry.get("published", ""),
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                ))
            logger.info(
                "OzBargain freebies: %s found (>= %s votes)",
                len(freebies),
                OZBARGAIN_FREEBIES_MIN_VOTES,
            )
        except Exception as exc:
            logger.error("Error fetching OzBargain freebies: %s", exc, exc_info=True)
        return freebies
