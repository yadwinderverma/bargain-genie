"""
Confirm a deal against the live product page before it is sent.

The page often contains several prices (accessories, shipping, related items).
The confirmed price is the one closest to the deal, not the lowest number on
the page. A cheaper accessory must not replace the product price.
"""

import ipaddress
import json
import logging
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from src.models import Deal

logger = logging.getLogger(__name__)

MAX_BYTES = 2_000_000
MAX_REDIRECTS = 4
# How far a live price may sit above the deal before we treat the deal as stale.
PRICE_TOLERANCE = 1.10
# A structured price this far below the deal is a different product, not confirmation.
PRICE_FLOOR = 0.50

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.8",
}

_REDIRECTS = {301, 302, 303, 307, 308}
_BLOCKED_HOSTS = {"localhost", "metadata.google.internal"}
_PRICE_META = {"product:price:amount", "og:price:amount", "price", "twitter:data1"}
_OOS_TEXT = re.compile(
    r"\b(out of stock|sold out|temporarily unavailable|no longer available|discontinued)\b",
    re.IGNORECASE,
)
_LD_JSON = re.compile(r"ld\+json", re.IGNORECASE)


def _parse_price(price_str) -> Optional[float]:
    if price_str is None or price_str == "":
        return None
    try:
        cleaned = re.sub(r"[^\d.]", "", str(price_str).replace(",", ""))
        value = float(cleaned)
        return value if value > 0 else None
    except ValueError:
        return None


def _is_safe_url(url: str) -> bool:
    """Reject fetches that are not public http(s) pages. No DNS lookup."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or host in _BLOCKED_HOSTS or host.endswith((".local", ".internal")):
        return False
    if host.isdigit():
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def _fetch(url: str):
    """Return a response, 'unsafe', or 'error'. Redirects are checked hop by hop."""
    current = url
    for _ in range(MAX_REDIRECTS):
        if not _is_safe_url(current):
            logger.info("Refusing price check for unsafe URL: %s", current)
            return "unsafe"
        try:
            response = requests.get(
                current,
                headers=HEADERS,
                timeout=12,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            logger.warning("Price check request failed for %s: %s", current, exc)
            return "error"
        if response.status_code in _REDIRECTS:
            location = response.headers.get("Location")
            if not location:
                return response
            current = urljoin(current, location)
            continue
        return response
    logger.warning("Too many redirects checking %s", url)
    return "error"


def _availability_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(_availability_text(item) for item in value).lower()
    return str(value).lower()


def _is_out_of_stock(value) -> bool:
    text = _availability_text(value)
    return any(token in text for token in ("outofstock", "soldout", "discontinued", "out of stock"))


def _is_in_stock(value) -> bool:
    text = _availability_text(value)
    return any(token in text for token in ("instock", "preorder", "limitedavailability", "in stock"))


def _walk_prices(node, inherited_availability=None) -> list[tuple[float, object]]:
    found = []
    if isinstance(node, list):
        for item in node:
            found.extend(_walk_prices(item, inherited_availability))
        return found
    if not isinstance(node, dict):
        return found

    availability = node.get("availability", inherited_availability)
    price = node.get("price")
    specification = node.get("priceSpecification")
    if price in (None, "") and isinstance(specification, dict):
        price = specification.get("price")
    parsed = _parse_price(price)
    if parsed:
        found.append((parsed, availability))

    for key, value in node.items():
        if key in ("price", "availability"):
            continue
        found.extend(_walk_prices(value, availability))
    return found


def _structured_prices(soup: BeautifulSoup) -> list[tuple[float, object]]:
    found: list[tuple[float, object]] = []
    for script in soup.find_all("script", attrs={"type": _LD_JSON}):
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except ValueError:
            continue
        found.extend(_walk_prices(payload))

    for tag in soup.find_all("meta"):
        key = (tag.get("property") or tag.get("itemprop") or tag.get("name") or "").lower()
        if key not in _PRICE_META:
            continue
        parsed = _parse_price(tag.get("content") if tag.get("content") is not None else tag.get("value"))
        if parsed:
            found.append((parsed, None))
    return found


def _visible_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


def _price_in_text(expected: float, text: str) -> bool:
    decimal = f"{expected:.2f}"
    if re.search(rf"(?<!\d){re.escape(decimal)}(?!\d)", text):
        return True
    if abs(expected - round(expected)) < 0.001:
        whole = str(int(round(expected)))
        return re.search(rf"\$\s*{re.escape(whole)}(?!\d)", text) is not None
    return False


def _apply_price(deal: Deal, confirmed: float) -> None:
    deal.sale_price = confirmed
    if deal.original_price and deal.original_price > confirmed:
        deal.discount_pct = ((deal.original_price - confirmed) / deal.original_price) * 100


def _page_confirms_deal(deal: Deal, html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    found = _structured_prices(soup)
    expected = deal.sale_price or 0
    closest = None
    if expected and found:
        closest = min(found, key=lambda item: abs(item[0] - expected))

    if closest and closest[0] <= expected * PRICE_TOLERANCE and closest[0] >= expected * PRICE_FLOOR:
        price, availability = closest
        if _is_out_of_stock(availability):
            logger.info("Out of stock (page data) for '%s'", deal.title)
            return False
        visible = "" if _is_in_stock(availability) else _visible_text(soup)
        if visible and _OOS_TEXT.search(visible):
            logger.info("Out of stock (page text) for '%s'", deal.title)
            return False
        logger.info("Live price for '%s' confirmed at $%.2f", deal.title, price)
        _apply_price(deal, price)
        return True

    if closest and closest[0] > expected * PRICE_TOLERANCE:
        logger.info(
            "Stale price for '%s': expected $%.2f, closest on page $%.2f",
            deal.title,
            expected,
            closest[0],
        )
        return False

    visible = _visible_text(soup)
    if _OOS_TEXT.search(visible):
        logger.info("Out of stock (page text) for '%s'", deal.title)
        return False
    if not expected:
        return True
    if _price_in_text(expected, visible):
        return True
    logger.info("Expected price %.2f not found on page for '%s'", expected, deal.title)
    return False


def verify_deal_price(deal: Deal) -> bool:
    """
    Return True when the deal may be sent.

    Transport failures fail open: a retailer blocking the fetch is not evidence
    the price is wrong. A confirmed higher price, an out-of-stock page, or an
    unsafe URL fails closed.
    """
    import config

    if not config.VERIFY_PRICES_LIVE:
        return True
    if deal.is_freebie:
        return True

    targets = []
    for candidate in ((deal.merchant_url or "").strip(), (deal.url or "").strip()):
        if candidate and candidate not in targets:
            targets.append(candidate)
    if not targets:
        return True

    # A bad merchant link must not block the OzBargain post, and must not be fetched.
    fetched = "unsafe"
    for target in targets:
        fetched = _fetch(target)
        if fetched != "unsafe":
            break
    if fetched == "unsafe":
        return False
    if fetched == "error":
        return True
    if fetched.status_code != 200:
        logger.warning(
            "Price check got HTTP %s for '%s'; letting it pass",
            fetched.status_code,
            deal.title,
        )
        return True
    body = getattr(fetched, "content", b"")
    if isinstance(body, (bytes, bytearray)) and len(body) > MAX_BYTES:
        logger.warning("Price check page too large for '%s'; letting it pass", deal.title)
        return True

    try:
        return _page_confirms_deal(deal, fetched.text)
    except Exception as exc:
        logger.warning("Price check failed for '%s': %s; letting it pass", deal.title, exc)
        return True
