"""
Slack notifier — sends deal alerts to your Slack channel via Incoming Webhooks.
Uses Slack Block Kit for rich, readable messages.

Set up:
1. Go to https://api.slack.com/apps → Create New App → From scratch
2. Enable Incoming Webhooks
3. Add webhook to your workspace and channel
4. Copy the webhook URL to SLACK_WEBHOOK_URL secret in GitHub
"""

import logging
import os
from datetime import datetime, timezone

import requests

from config import MAX_SLACK_ALERTS_PER_RUN, SLACK_NOTIFY_USER
from src.models import Deal

logger = logging.getLogger(__name__)

SOURCE_EMOJI = {
    "ozbargain_freebie": "🆓",
    "ozbargain":   "🔥",
    "jbhifi":      "🎵",
    "kogan":       "🛒",
    "catch":       "🎣",
    "officeworks": "🖊️",
    "bigw":        "🏪",
    "target":      "🎯",
    "amazon":      "📦",
    "serper_shopping": "🔍",
}

SCORE_EMOJI = {
    range(9, 11): "🏆",
    range(7, 9): "⭐",
    range(5, 7): "👍",
}


class SlackNotifier:
    def __init__(self):
        self.webhook_url = self._get_webhook_url()

    def _get_webhook_url(self) -> str | None:
        url = os.environ.get("SLACK_WEBHOOK_URL")
        if not url:
            logger.error("SLACK_WEBHOOK_URL not set — cannot send Slack notifications")
        return url

    def _get_source_emoji(self, source: str) -> str:
        for key, emoji in SOURCE_EMOJI.items():
            if key in source.lower():
                return emoji
        return "💰"

    def _get_score_emoji(self, score: int) -> str:
        for score_range, emoji in SCORE_EMOJI.items():
            if score in score_range:
                return emoji
        return "💡"


    def _format_price(self, price: float | None) -> str:
        if price is None:
            return "N/A"
        return f"${price:,.2f}"


    def _build_deal_block(self, deal: Deal) -> list[dict]:
        """Build Slack Block Kit blocks for a single deal."""
        source_emoji = self._get_source_emoji(deal.source)
        score_emoji = self._get_score_emoji(deal.llm_score)

        # Build price display
        if deal.is_freebie:
            duration_str = f" · {deal.duration_note}" if deal.duration_note else ""
            price_text = f"🆓 *FREE{duration_str}*"
        else:
            price_parts = []
            if deal.sale_price:
                price_parts.append(f"*{self._format_price(deal.sale_price)}*")
            if deal.original_price and deal.sale_price and deal.original_price != deal.sale_price:
                price_parts.append(f"~{self._format_price(deal.original_price)}~")
            if deal.discount_pct:
                price_parts.append(f"*{deal.discount_pct:.0f}% OFF*")
            price_text = "  ".join(price_parts) if price_parts else "Price not available"

        # Build context line
        context_parts = [f"{source_emoji} {deal.source.replace('_', ' ').title()}"]
        if deal.community_validated:
            context_parts.append("🏅 OzBargain Community Pick")
        if deal.price_beat_retailer:
            context_parts.append("🔖 Price Beat Guarantee")
        if deal.votes > 0:
            context_parts.append(f"👍 {deal.votes} votes")
        context_parts.append(f"{score_emoji} AI Score: {deal.llm_score}/10")
        if deal.llm_category:
            context_parts.append(f"📦 {deal.llm_category}")

        safe_title = deal.title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        title_text = f"<{deal.url}|{safe_title}>" if deal.url else safe_title

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{title_text}\n{price_text}",
                },
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "  |  ".join(context_parts)},
                ],
            },
        ]

        if deal.llm_reason:
            blocks.append({
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"💬 _{deal.llm_reason}_"},
                ],
            })

        blocks.append({"type": "divider"})
        return blocks

    def _build_summary_header(self, deals: list[Deal], run_time: str) -> list[dict]:
        """Build the header block for the Slack message."""
        count = len(deals)
        sources = list({d.source.split("_")[0] for d in deals if d.source})
        sources_text = ", ".join(s.title() for s in sources if s)

        # Mention line — triggers Slack notification
        mention = f"{SLACK_NOTIFY_USER} " if SLACK_NOTIFY_USER else ""

        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🛍️ {count} Bargain{'s' if count != 1 else ''} Found!",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{mention}*{count} deal{'s' if count != 1 else ''}* matching your watchlist",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"📅 {run_time}  |  Sources: {sources_text or 'Various'}",
                    }
                ],
            },
            {"type": "divider"},
        ]

    def send_slack_alerts(self, deals: list[Deal]) -> bool:
        """
        Send deal alerts to Slack.
        Returns True if successful, False otherwise.
        """
        if not self.webhook_url:
            return False

        if not deals:
            logger.info("No deals to send to Slack")
            return True

        # Cap alerts per run
        if len(deals) > MAX_SLACK_ALERTS_PER_RUN:
            logger.info(f"Capping alerts at {MAX_SLACK_ALERTS_PER_RUN} (had {len(deals)})")
            # Sort by score descending, take top N
            deals = sorted(deals, key=lambda d: d.llm_score, reverse=True)
            deals = deals[:MAX_SLACK_ALERTS_PER_RUN]

        run_time = datetime.now(timezone.utc).strftime("%d %b %Y, %I:%M %p UTC")
        blocks = self._build_summary_header(deals, run_time)

        for deal in deals:
            blocks.extend(self._build_deal_block(deal))

        # Slack has a 50-block limit per message — split if needed
        MAX_BLOCKS = 50
        block_chunks = [blocks[i : i + MAX_BLOCKS] for i in range(0, len(blocks), MAX_BLOCKS)]

        success = True
        for chunk_idx, chunk in enumerate(block_chunks):
            payload = {
                "blocks": chunk,
                "text": f"{''+SLACK_NOTIFY_USER+' ' if SLACK_NOTIFY_USER else ''}🛍️ {len(deals)} bargain{'s' if len(deals) != 1 else ''} found on your watchlist!",
            }

            try:
                response = requests.post(self.webhook_url, json=payload, timeout=15)
                response.raise_for_status()
                logger.info(f"Slack message {chunk_idx + 1}/{len(block_chunks)} sent successfully")
            except requests.RequestException as e:
                error_msg = str(e)
                if self.webhook_url:
                    error_msg = error_msg.replace(self.webhook_url, "***REDACTED***")
                error_msg = str(e).replace(self.webhook_url, "***REDACTED***") if self.webhook_url else str(e)
                logger.error(f"Failed to send Slack message chunk {chunk_idx + 1}: {error_msg}")
                success = False

        return success

    def send_slack_no_deals_message(self) -> None:
        """Send a brief 'no deals found' message (optional, can be disabled)."""
        if not self.webhook_url:
            return

        # Only send this if you want to confirm the bot ran — comment out to stay quiet
        # payload = {
        #     "text": "🔍 Bargain Hunter ran — no deals meeting criteria found this time."
        # }
        # requests.post(self.webhook_url, json=payload, timeout=15)
        logger.info("No deals to report — Slack not notified (silent run)")

    def send_slack_error_message(self, error: str) -> None:
        """Send an error alert to Slack so you know the bot failed."""
        if not self.webhook_url:
            return

        payload = {
            "text": f"⚠️ *Bargain Hunter Error*\n```{error[:500]}```\nCheck GitHub Actions logs for details.",
        }
        try:
            requests.post(self.webhook_url, json=payload, timeout=15)
        except requests.RequestException as e:
            error_msg = str(e)
            if self.webhook_url:
                error_msg = error_msg.replace(self.webhook_url, "***REDACTED***")
            error_msg = str(e).replace(self.webhook_url, "***REDACTED***") if self.webhook_url else str(e)
            logger.error(f"Failed to send error message to Slack: {error_msg}")

# Legacy functions
def send_slack_alerts(deals: list[dict]) -> bool:
    pass

def send_slack_no_deals_message() -> None:
    SlackNotifier().send_slack_no_deals_message()

def send_slack_error_message(error: str) -> None:
    SlackNotifier().send_slack_error_message(error)
