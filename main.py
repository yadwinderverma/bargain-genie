"""
Bargain Hunter.

Fetch OzBargain and Google Shopping, keep the watchlist matches, score them,
confirm the live price, and send the ones worth buying to Slack.
"""

import logging
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import config
from src.analyser import DealAnalyser
from src.cache import DealCache
from src.dedupe import dedupe_deals
from src.fetchers.ozbargain import OzBargainFetcher, OzBargainFreebieFetcher
from src.fetchers.retailers import RetailerFetcher
from src.models import Deal
from src.notifier import SlackNotifier
from src.price_check import verify_deal_price

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _fetch_all() -> list[Deal]:
    fetchers = [OzBargainFetcher(), OzBargainFreebieFetcher(), RetailerFetcher()]

    def fetch_from_source(fetcher):
        name = fetcher.__class__.__name__
        try:
            deals = fetcher.fetch()
            logger.info("%s: %s deals", name, len(deals))
            return deals
        except Exception as exc:
            logger.error("Error in %s: %s", name, exc, exc_info=True)
            return []

    deals: list[Deal] = []
    with ThreadPoolExecutor(max_workers=len(fetchers)) as executor:
        futures = [executor.submit(fetch_from_source, fetcher) for fetcher in fetchers]
        for future in as_completed(futures):
            deals.extend(future.result())
    return dedupe_deals(deals)


def _verify_one(deal: Deal) -> tuple[str, Deal]:
    """Return ('pass', 'reject', or 'retry') and the deal."""
    try:
        return ("pass" if verify_deal_price(deal) else "reject", deal)
    except Exception:
        logger.exception("Price check crashed for '%s'", deal.title)
        return "retry", deal


def run() -> int:
    """Run one hunt. Returns 0 on success, including a quiet run with nothing to send."""
    started = datetime.now(timezone.utc)
    logger.info("Bargain Hunter starting at %s", started.strftime("%Y-%m-%d %H:%M:%S UTC"))

    try:
        cache = DealCache()
        analyser = DealAnalyser()
        notifier = SlackNotifier()

        logger.info("--- Step 1: Fetching deals ---")
        all_deals = _fetch_all()
        logger.info("Total deals fetched: %s", len(all_deals))
        if not all_deals:
            logger.info("No deals found from any source")
            notifier.send_slack_no_deals_message()
            return 0

        logger.info("--- Step 2: Filtering open deals ---")
        new_deals = cache.filter_new_deals(all_deals)
        logger.info("Open deals: %s", len(new_deals))
        if not new_deals:
            logger.info("Nothing new to report")
            notifier.send_slack_no_deals_message()
            return 0

        logger.info("--- Step 3: LLM analysis ---")
        quality_deals = analyser.analyse_deals(new_deals)
        cache.mark_deals_rejected([
            deal for deal in new_deals
            if not deal.analysis_error and deal.llm_score < config.LLM_MIN_SCORE
        ])
        logger.info("Deals after LLM filter: %s", len(quality_deals))
        if not quality_deals:
            logger.info("No deals passed the LLM filter")
            notifier.send_slack_no_deals_message()
            return 0

        logger.info("--- Step 3.5: Live price verification ---")
        workers = min(len(quality_deals), 10)
        verified: list[Deal] = []
        rejected: list[Deal] = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for status, deal in executor.map(_verify_one, quality_deals):
                if status == "pass":
                    verified.append(deal)
                elif status == "reject":
                    rejected.append(deal)
        cache.mark_deals_rejected(rejected)
        logger.info("Deals after live verification: %s", len(verified))
        if not verified:
            logger.info("No deals passed live price verification")
            notifier.send_slack_no_deals_message()
            return 0

        verified.sort(key=lambda deal: (deal.llm_score, deal.discount_pct or 0), reverse=True)
        to_send = verified[:config.MAX_SLACK_ALERTS_PER_RUN]
        if len(verified) > len(to_send):
            logger.info(
                "Holding %s lower-scored deals for the next run",
                len(verified) - len(to_send),
            )

        logger.info("--- Step 4: Sending Slack alerts ---")
        if not notifier.send_slack_alerts(to_send):
            logger.error("Slack notification failed; these deals will be retried next run")
            return 1

        cache.mark_deals_alerted(to_send)
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.info(
            "Run complete in %.1fs. Fetched %s, open %s, alerted %s",
            elapsed,
            len(all_deals),
            len(new_deals),
            len(to_send),
        )
        return 0

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        logger.error("Unhandled error:\n%s", error_msg)
        try:
            SlackNotifier().send_slack_error_message(error_msg)
        except Exception:
            logger.exception("Could not report the failure to Slack")
        return 1


if __name__ == "__main__":
    sys.exit(run())
