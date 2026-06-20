"""
Bargain Hunter — main entry point.

Fetches deals from OzBargain, Serper (Google Shopping), and Australian retailers,
filters for genuine 50%+ discounts, scores them with Gemini AI,
and sends the best ones to Slack.
"""

import logging
import sys
import traceback
from datetime import datetime, timezone

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

        for fetcher in fetchers:
            fetcher_name = fetcher.__class__.__name__
            try:
                deals = fetcher.fetch()
                logger.info(f"{fetcher_name}: {len(deals)} deals")
                all_deals.extend(deals)
            except Exception as e:
                logger.error(f"Error in {fetcher_name}: {e}")

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
