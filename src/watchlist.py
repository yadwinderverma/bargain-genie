"""
Watchlist matching shared by OzBargain and Google Shopping.

A query matches when every keyword is present and none of its excludes are.
A one or two digit keyword, such as the "2" in "OpenFit 2", has to sit within
a few words of another keyword in the title. "2 year warranty" and "pack of 2"
do not count.
"""

import re

from config import GLOBAL_EXCLUDES, SEARCH_QUERIES

# How far a model number may sit from another keyword, in words.
_NUMBER_WINDOW = 4
_FOLLOWING_QUANTITY = {
    "year", "yr", "years",
    "day", "days",
    "month", "months",
    "pack", "pk", "packs",
    "pair", "pairs",
    "set", "sets",
}
_LEADING_QUANTITY = {"pack", "pk", "set", "pair", "x"}

_TAG_RE = re.compile(r"<[^>]+>")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_GLOBAL_EXCLUDES = [re.compile(rf"\b{re.escape(term.lower())}\b") for term in GLOBAL_EXCLUDES]


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", text or "")).strip().lower()


def _is_model_number(keyword: str) -> bool:
    return keyword.isdigit() and len(keyword) <= 2


def _pattern(keyword: str) -> re.Pattern:
    return re.compile(rf"\b{re.escape(keyword.lower())}\b")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _is_quantity(tokens: list[str], index: int) -> bool:
    """True when this number is a pack size or a warranty length."""
    previous = tokens[index - 1] if index else ""
    previous_two = tokens[index - 2] if index >= 2 else ""
    following = tokens[index + 1] if index + 1 < len(tokens) else ""
    if following in _FOLLOWING_QUANTITY:
        return True
    if previous == "x":
        return True
    return previous == "of" and previous_two in _LEADING_QUANTITY


def _excluded(text: str, patterns: list[re.Pattern]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _number_near_keywords(title: str, number: str, keywords: list[str]) -> bool:
    tokens = _tokens(title)
    anchors = [
        index
        for index, token in enumerate(tokens)
        if any(_pattern(keyword).fullmatch(token) for keyword in keywords)
    ]
    if not anchors:
        return False
    for index, token in enumerate(tokens):
        if token != number or _is_quantity(tokens, index):
            continue
        if any(abs(index - anchor) <= _NUMBER_WINDOW for anchor in anchors):
            return True
    return False


def matches_query(title: str, body: str, query: dict) -> bool:
    """True when this one query matches. `body` is extra text, such as an RSS summary."""
    if not isinstance(query, dict):
        return False
    keywords = [str(word).lower() for word in query.get("keywords") or []]
    if not keywords:
        return False

    title_text = _plain(title)
    combined = f"{title_text} {_plain(body)}".strip()
    if _excluded(combined, _GLOBAL_EXCLUDES):
        return False

    excludes = [_pattern(word) for word in query.get("exclude") or []]
    if _excluded(combined, excludes):
        return False

    words = [keyword for keyword in keywords if not _is_model_number(keyword)]
    numbers = [keyword for keyword in keywords if _is_model_number(keyword)]
    for keyword in words:
        if not _pattern(keyword).search(combined):
            return False
    for number in numbers:
        if not _number_near_keywords(title_text, number, words):
            return False
    return True


def matches_any(title: str, body: str = "", queries=None) -> bool:
    """True when any configured watchlist query matches."""
    chosen = SEARCH_QUERIES if queries is None else queries
    for query in chosen:
        if isinstance(query, str):
            if matches_query(title, body, {"keywords": query.split()}):
                return True
        elif isinstance(query, dict) and matches_query(title, body, query):
            return True
    return False
