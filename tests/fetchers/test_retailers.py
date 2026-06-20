import pytest
from src.fetchers.retailers import _parse_price

def test_parse_price_valid():
    assert _parse_price("10.50") == 10.5
    assert _parse_price("100") == 100.0
    assert _parse_price("1234.56") == 1234.56

def test_parse_price_with_currency_and_commas():
    assert _parse_price("$10.50") == 10.5
    assert _parse_price("A$ 99.99") == 99.99
    assert _parse_price("$1,234.56") == 1234.56
    assert _parse_price("1,000,000.00") == 1000000.0

def test_parse_price_edge_cases():
    assert _parse_price(None) is None
    assert _parse_price("") is None
    assert _parse_price("0") is None
    # the function strips non-digits and dots so "-5.0" becomes "5.0".
    assert _parse_price("-5.0") == 5.0

def test_parse_price_invalid():
    assert _parse_price("Free") is None
    assert _parse_price("Not a price") is None
    assert _parse_price("NaN") is None

def test_parse_price_multiple_decimal_points():
    assert _parse_price("1.2.3") is None

def test_parse_price_integer_types():
    assert _parse_price(100) == 100.0
    assert _parse_price(10.5) == 10.5
