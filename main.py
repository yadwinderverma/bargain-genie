"""
Bargain Hunter — main entry point.

Fetches deals from OzBargain, Serper (Google Shopping), and Australian retailers,
filters for genuine 50%+ discounts, scores them with Gemini AI,
and sends the best ones to Slack.
"""

import logging
import sys
import traceback
import re
import json
import requests
from datetime import datetime, timezone
from typing import Optional

from src.analyser import DealAnalyser
from src.cache import DealCache
from src.fetchers.ozbargain import OzBargainFetcher, OzBargainFreebieFetcher
from src.fetchers.retailers import RetailerFetcher
from src.notifier import SlackNotifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _parse_price(price_str: str) -> Optional[float]:
    if not price_str:
        return None
    try:
        cleaned = re.sub(r"[^\d.]", "", str(price_str).replace(",", ""))
        val = float(cleaned)
        return val if val > 0 else None
    except ValueError:
        return None


def verify_deal_price(deal) -> bool:
    """
    HTTP GETs the deal page, parses price metadata (JSON-LD or OpenGraph/itemprop),
    and verifies that the sale price is still matching and in stock.
    """
    from config import VERIFY_PRICES_LIVE
    if not VERIFY_PRICES_LIVE:
        return True
    if not deal.url:
        return True

    logger.info(f"Verifying price live for '{deal.title}' at {deal.url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        response = requests.get(deal.url, headers=headers, timeout=12, allow_redirects=True)
        if response.status_code != 200:
            logger.warning(f"Failed to verify page (status code {response.status_code}) — letting deal pass")
            return True

        html = response.text
        # Check for out of stock signals
        oos_patterns = [
            r"out of stock", r"sold out", r"temporarily unavailable",
            r"no longer available", r"discontinued"
        ]
        html_lower = html.lower()
        if any(re.search(pat, html_lower) for pat in oos_patterns):
            logger.info(f"Discarding deal '{deal.title}': Out-of-stock indicator found on page")
            return False

        # Try to parse price from JSON-LD
        from typing import Optional
        found_prices = []

        # 1. Parse JSON-LD script blocks
        json_ld_blocks = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
        for block in json_ld_blocks:
            try:
                data = json.loads(block.strip())
                schemas = data if isinstance(data, list) else [data]
                for schema in schemas:
                    if not isinstance(schema, dict):
                        continue

                    def extract_prices(obj):
                        if isinstance(obj, dict):
                            if "price" in obj and obj["price"]:
                                p = _parse_price(str(obj["price"]))
                                if p:
                                    found_prices.append(p)
                            if "offers" in obj:
                                extract_prices(obj["offers"])
                            for k, v in obj.items():
                                if k not in ["offers", "price"]:
                                    extract_prices(v)
                        elif isinstance(obj, list):
                            for item in obj:
                                extract_prices(item)

                    extract_prices(schema)
            except Exception:
                pass

        # 2. Parse OpenGraph and Meta tags
        meta_patterns = [
            r'<meta[^>]*property=["\']product:price:amount["\'][^>]*content=["\']([^"\']+)["\']',
            r'<meta[^>]*property=["\']og:price:amount["\'][^>]*content=["\']([^"\']+)["\']',
            r'<meta[^>]*itemprop=["\']price["\'][^>]*content=["\']([^"\']+)["\']',
            r'<meta[^>]*name=["\']twitter:data1["\'][^>]*value=["\']([^"\']+)["\']',
        ]
        for pat in meta_patterns:
            matches = re.findall(pat, html, re.IGNORECASE)
            for m in matches:
                p = _parse_price(m)
                if p:
                    found_prices.append(p)

        if found_prices:
            detected_price = min(found_prices)
            logger.info(f"Detected price from metadata for '{deal.title}': ${detected_price:.2f}")
            if detected_price > deal.sale_price * 1.10:
                logger.info(f"Discarding deal '{deal.title}': Price discrepancy detected (Expected: ${deal.sale_price:.2f}, Found: ${detected_price:.2f})")
                return False
            else:
                deal.sale_price = detected_price
                if deal.original_price and deal.original_price > deal.sale_price:
                    deal.discount_pct = ((deal.original_price - deal.sale_price) / deal.original_price) * 100
                return True
        else:
            price_int = int(deal.sale_price)
            price_str_simple = f"{price_int}"
            if price_str_simple not in html:
                logger.info(f"Discarding deal '{deal.title}': Expected price '{deal.sale_price:.2f}' not found in page content")
                return False
            return True

    except Exception as e:
        logger.warning(f"Error during live price verification for '{deal.title}': {e} — letting deal pass")
        return True


from typing import Optional

def run() -> int:
    """
    Main pipeline. Returns exit code (0 = success, 1 = error).
    """
    start_time = datetime.now(timezone.utc)
    logger.info("=" * 60)
    logger.info(f"Bargain Hunter starting at {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    logger.info("=" * 60)

    try:
        # Initialise components
        fetchers = [
            OzBargainFetcher(),
            OzBargainFreebieFetcher(),
            RetailerFetcher(),
        ]
        cache = DealCache()
        analyser = DealAnalyser()
        notifier = SlackNotifier()

        # ----------------------------------------------------------------
        # Step 1: Fetch deals from all sources
        # ----------------------------------------------------------------
        logger.info("--- Step 1: Fetching deals ---")
        all_deals = []
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def fetch_from_source(f):
            fetcher_name = f.__class__.__name__
            try:
                deals = f.fetch()
                logger.info(f"{fetcher_name}: {len(deals)} deals")
                return deals
            except Exception as e:
                logger.error(f"Error in {fetcher_name}: {e}", exc_info=True)
                return []

        max_workers = len(fetchers) if fetchers else 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_from_source, f): f for f in fetchers}
            for future in as_completed(futures):
                all_deals.extend(future.result())

        logger.info(f"Total deals fetched: {len(all_deals)}")

        if not all_deals:
            logger.info("No deals found from any source")
            notifier.send_slack_no_deals_message()
            return 0

        # ----------------------------------------------------------------
        # Step 2: Deduplicate against cache (skip already-seen deals)
        # ----------------------------------------------------------------
        logger.info("--- Step 2: Filtering new deals ---")
        new_deals = cache.filter_new_deals(all_deals)
        logger.info(f"New deals (not seen before): {len(new_deals)}")

        if not new_deals:
            logger.info("All deals already seen — nothing new to report")
            notifier.send_slack_no_deals_message()
            return 0

        # ----------------------------------------------------------------
        # Step 3: LLM analysis — score and filter genuine bargains
        # ----------------------------------------------------------------
        logger.info("--- Step 3: LLM analysis ---")
        quality_deals = analyser.analyse_deals(new_deals)
        logger.info(f"Quality deals after LLM filter: {len(quality_deals)}")

        if not quality_deals:
            logger.info("No deals passed LLM quality filter")
            notifier.send_slack_no_deals_message()
            return 0

        # ----------------------------------------------------------------
        # Step 3.5: Live price verification crawler
        # ----------------------------------------------------------------
        logger.info("--- Step 3.5: Live price verification ---")
        from concurrent.futures import ThreadPoolExecutor

        def verify_single_deal(d):
            try:
                if verify_deal_price(d):
                    return d
            except Exception as e:
                logger.error(f"Error verifying price for '{d.title}': {e}")
            return None

        max_workers = min(len(quality_deals), 10) if quality_deals else 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # We map verify_single_deal over quality_deals
            results = executor.map(verify_single_deal, quality_deals)
            verified_deals = [d for d in results if d is not None]

        quality_deals = verified_deals
        logger.info(f"Quality deals after live verification: {len(quality_deals)}")

        if not quality_deals:
            logger.info("No deals passed live price verification")
            notifier.send_slack_no_deals_message()
            return 0

        # Sort by LLM score descending
        quality_deals.sort(key=lambda d: d.llm_score, reverse=True)

        # ----------------------------------------------------------------
        # Step 4: Send to Slack
        # ----------------------------------------------------------------
        logger.info("--- Step 4: Sending Slack alerts ---")
        success = notifier.send_slack_alerts(quality_deals)

        if success:
            cache.mark_deals_alerted(quality_deals)
            logger.info(f"Successfully alerted {len(quality_deals)} deals to Slack")
        else:
            logger.error("Slack notification failed")
            return 1

        # ----------------------------------------------------------------
        # Summary
        # ----------------------------------------------------------------
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info("=" * 60)
        logger.info(f"Run complete in {elapsed:.1f}s")
        logger.info(f"  Fetched:   {len(all_deals)} deals (OzBargain + Shopping)")
        logger.info(f"  New:       {len(new_deals)} deals")
        logger.info(f"  Alerted:   {len(quality_deals)} deals")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        logger.error(f"Unhandled error:\n{error_msg}")
        try:
            SlackNotifier().send_slack_error_message(error_msg)
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(run())
