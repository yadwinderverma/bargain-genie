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

def _mrkdwn(text: str) -> str:
    """Escape text that would break a Slack mrkdwn link or mention."""
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("|", "/")
    )


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
        if 9 <= score <= 10:
            return "🏆"
        if 7 <= score <= 8:
            return "⭐"
        if 5 <= score <= 6:
            return "👍"
        return "💡"

    def _redact(self, message: str) -> str:
        if self.webhook_url and self.webhook_url in message:
            return message.replace(self.webhook_url, "***REDACTED***")
        return message

    def _link(self, url: str, label: str) -> str:
        safe_label = _mrkdwn(label) or "link"
        if (
            url
            and url.startswith(("http://", "https://"))
            and ">" not in url
            and "|" not in url
            and " " not in url
        ):
            return f"<{url}|{safe_label}>"
        return safe_label


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

        title_text = self._link(deal.url, deal.title)
        if deal.merchant_url and deal.merchant_url.rstrip("/") != (deal.url or "").rstrip("/"):
            context_parts.append(self._link(deal.merchant_url, "Retailer page"))

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
            reason = _mrkdwn(" ".join(deal.llm_reason.split()))
            blocks.append({
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"💬 _{reason[:240]}_"},
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
        messages = self._pack_messages(deals, run_time)
        mention = f"{SLACK_NOTIFY_USER} " if SLACK_NOTIFY_USER else ""
        fallback = f"{mention}🛍️ {len(deals)} bargain{'s' if len(deals) != 1 else ''} found on your watchlist!"

        success = True
        for chunk_idx, chunk in enumerate(messages):
            payload = {"blocks": chunk, "text": fallback}
            try:
                response = requests.post(self.webhook_url, json=payload, timeout=15)
                response.raise_for_status()
                logger.info("Slack message %s/%s sent successfully", chunk_idx + 1, len(messages))
            except requests.RequestException as exc:
                logger.error(
                    f"Failed to send Slack message chunk {chunk_idx + 1}: {self._redact(str(exc))}"
                )
                success = False

        return success

    def _pack_messages(self, deals: list[Deal], run_time: str) -> list[list[dict]]:
        """Pack blocks without splitting a deal across Slack's 50-block limit."""
        header = self._build_summary_header(deals, run_time)
        messages: list[list[dict]] = []
        current = list(header)
        for deal in deals:
            blocks = self._build_deal_block(deal)
            if len(current) + len(blocks) > 50 and len(current) > 1:
                messages.append(current)
                current = [{
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "More deals from this run:"},
                }]
            current.extend(blocks)
        if current:
            messages.append(current)
        return messages

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
        except requests.RequestException as exc:
            logger.error(f"Failed to send error message to Slack: {self._redact(str(exc))}")


def send_slack_error_message(error: str) -> None:
    SlackNotifier().send_slack_error_message(error)
