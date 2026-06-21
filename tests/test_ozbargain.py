import pytest
from src.fetchers.ozbargain import _parse_price_from_description

def test_parse_price_from_description_two_prices():
    """Test with two valid prices."""
    description = "Was $199.99, now only $99.99!"
    original, sale = _parse_price_from_description(description)
    assert original == 199.99
    assert sale == 99.99

def test_parse_price_from_description_one_price():
    """Test with one valid price."""
    description = "Available for $49.50"
    original, sale = _parse_price_from_description(description)
    assert original is None
    assert sale == 49.50

def test_parse_price_from_description_no_prices():
    """Test with no prices."""
    description = "Great deal available now!"
    original, sale = _parse_price_from_description(description)
    assert original is None
    assert sale is None

def test_parse_price_from_description_more_than_four_prices():
    """Test with more than four prices to verify it only considers the first four."""
    description = "Prices: $100, $50, $200, $300, $10, $500"
    # Prices extracted: 100, 50, 200, 300, 10, 500
    # First 4: 100, 50, 200, 300
    # Max of first 4: 300 (original)
    # Min of first 4: 50 (sale)
    original, sale = _parse_price_from_description(description)
    assert original == 300.0
    assert sale == 50.0

def test_parse_price_from_description_thousands_separator():
    """Test with prices containing thousands separators."""
    description = "Was $1,299.00, now $999.00!"
    original, sale = _parse_price_from_description(description)
    assert original == 1299.0
    assert sale == 999.0

def test_parse_price_from_description_equal_prices():
    """Test with equal prices, should return None, None since original must be > sale."""
    description = "Price is $50, down from $50"
    original, sale = _parse_price_from_description(description)
    assert original is None
    assert sale is None

def test_parse_price_from_description_original_less_than_sale():
    """Test with original less than sale, should return None, None."""
    # Note: the function uses max and min so it assumes max is original and min is sale
    # Wait, the function takes the max of the first 4 as original and min of the first 4 as sale.
    # original = max(prices_clean[:4])
    # sale = min(prices_clean[:4])
    # if original > sale: return original, sale
    # This implies that if all extracted prices are the same, max == min, so original == sale.
    # Then original > sale is False. It falls through to return None, None.
    # What if there are two prices extracted but they are the same?
    description = "Price is $50, another price is $50"
    original, sale = _parse_price_from_description(description)
    assert original is None
    assert sale is None

def test_parse_price_from_description_invalid_prices():
    """Test with invalid price formats."""
    description = "Price is $abc or $10.00"
    original, sale = _parse_price_from_description(description)
    assert original is None
    assert sale == 10.0

def test_parse_price_from_description_whole_numbers():
    """Test with whole number prices."""
    description = "Was $100, now $50"
    original, sale = _parse_price_from_description(description)
    assert original == 100.0
    assert sale == 50.0
