import pytest
from src.fetchers.ozbargain import _parse_price_from_description

def test_parse_price_happy_path():
    description = "Normally $100, now on sale for $50!"
    original, sale = _parse_price_from_description(description)
    assert original == 100.0
    assert sale == 50.0

def test_parse_price_single_price():
    description = "Grab it for only $29.99 today."
    original, sale = _parse_price_from_description(description)
    assert original is None
    assert sale == 29.99

def test_parse_price_no_prices():
    description = "Great deal available now!"
    original, sale = _parse_price_from_description(description)
    assert original is None
    assert sale is None

def test_parse_price_with_commas():
    description = "Was $1,299, now just $999!"
    original, sale = _parse_price_from_description(description)
    assert original == 1299.0
    assert sale == 999.0

def test_parse_price_with_cents():
    description = "Reduced from $49.95 to $19.50"
    original, sale = _parse_price_from_description(description)
    assert original == 49.95
    assert sale == 19.50

def test_parse_price_more_than_4_prices():
    # Only the first 4 prices are considered.
    # Prices: 10, 20, 30, 40 (first 4) -> max=40, min=10
    # Next prices: 5, 100 (ignored)
    description = "$10 $20 $30 $40 $5 $100"
    original, sale = _parse_price_from_description(description)
    assert original == 40.0
    assert sale == 10.0

def test_parse_price_identical_prices():
    # If the prices are the same, original > sale is False, so returns (None, None)
    description = "Price is $50, usually $50."
    original, sale = _parse_price_from_description(description)
    assert original is None
    assert sale is None

def test_parse_price_invalid_price_format_ignored():
    description = "Weird price $.99 and actual price $19.99"
    original, sale = _parse_price_from_description(description)
    assert original is None
    assert sale == 19.99
