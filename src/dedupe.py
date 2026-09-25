"""Collapse the same listing when it arrives from more than one source."""

import re
from urllib.parse import urlparse

from src.models import Deal


def _normalise_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return ""
    host = parsed.hostname.lower()
    if host.startswith("www."):
        host = host[4:]
    return f"{host}{parsed.path.rstrip('/')}"


def _keys(deal: Deal) -> set[str]:
    keys = set()
    merchant = _normalise_url(deal.merchant_url)
    if merchant:
        keys.add(f"url:{merchant}")
    page = _normalise_url(deal.url)
    if page and not page.startswith("ozbargain.com.au/node/"):
        keys.add(f"url:{page}")
    node = re.search(r"/node/(\d+)", deal.url or "")
    if node:
        keys.add(f"node:{node.group(1)}")
    if not keys:
        keys.add(f"id:{deal.id}")
    return keys


def _rank(deal: Deal) -> tuple[int, int]:
    """Lower is better. Prefer a real OzBargain post over a shopping hit."""
    if deal.is_freebie:
        source_rank = 0
    elif deal.source == "ozbargain":
        source_rank = 1
    else:
        source_rank = 2
    return (source_rank, -deal.votes)


def dedupe_deals(deals: list[Deal]) -> list[Deal]:
    """Keep one deal per product listing. Order follows the first time we saw it."""
    if not deals:
        return []

    parent = list(range(len(deals)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    first_seen: dict[str, int] = {}
    for index, deal in enumerate(deals):
        for key in _keys(deal):
            if key in first_seen:
                union(index, first_seen[key])
            else:
                first_seen[key] = index

    groups: dict[int, list[Deal]] = {}
    order: list[int] = []
    for index, deal in enumerate(deals):
        root = find(index)
        if root not in groups:
            groups[root] = []
            order.append(root)
        groups[root].append(deal)

    return [min(groups[root], key=_rank) for root in order]
