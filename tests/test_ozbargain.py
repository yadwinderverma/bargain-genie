import pytest
from src.fetchers.ozbargain import (
    _parse_price_from_description, _parse_discount_from_title, _parse_votes
)

# ==========================================
# _parse_price_from_description Tests
# ==========================================

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
    description = "$10 $20 $30 $40 $5 $100"
    original, sale = _parse_price_from_description(description)
    assert original == 40.0
    assert sale == 10.0

def test_parse_price_identical_prices():
    description = "Price is $50, usually $50."
    original, sale = _parse_price_from_description(description)
    assert original is None
    assert sale is None

def test_parse_price_invalid_price_format_ignored():
    description = "Weird price $.99 and actual price $19.99"
    original, sale = _parse_price_from_description(description)
    assert original is None
    assert sale == 19.99


# ==========================================
# _parse_discount_from_title Tests
# ==========================================

@pytest.mark.parametrize(
    "title, expected",
    [
        # Happy paths: "X% off"
        ("50% off", 50.0),
        ("25% off", 25.0),
        ("100% off", 100.0),
        ("0% off", 0.0),
        ("50%OFF", 50.0),
        ("25 % off", 25.0),
        ("Save big! 30%  OFF today", 30.0),

        # Happy paths: "half price"
        ("half price", 50.0),
        ("Half Price", 50.0),
        ("Half-Price", 50.0),
        ("HalfPrice", 50.0),
        ("Get it for half price!", 50.0),

        # Error conditions / no matches
        ("50%", None),
        ("off", None),
        ("Save $50", None),
        ("Discounted price", None),
        ("", None),
        ("50 percent off", None), # Current regex doesn't handle "percent"
    ],
)
def test_parse_discount_from_title(title: str, expected: float | None):
    assert _parse_discount_from_title(title) == expected


# ==========================================
# _parse_votes Tests
# ==========================================

def test_parse_votes_from_summary_votes():
    """Test extracting vote count from 'N votes' pattern in summary."""
    entry = {"summary": "This deal has 15 votes from the community."}
    assert _parse_votes(entry) == 15

def test_parse_votes_from_summary_clicks():
    """Test extracting vote count from 'N clicks' pattern in summary."""
    entry = {"summary": "Check this out! 42 clicks so far."}
    assert _parse_votes(entry) == 42

def test_parse_votes_from_summary_singular():
    """Test extracting vote count from singular 'vote' pattern."""
    entry = {"summary": "Only 1 vote for this."}
    assert _parse_votes(entry) == 1

def test_parse_votes_from_tags():
    """Test extracting vote count from tags as fallback when not in summary."""
    entry = {
        "summary": "A great deal!",
        "tags": [
            {"term": "computers"},
            {"term": "120 votes"}
        ]
    }
    assert _parse_votes(entry) == 120

def test_parse_votes_from_tags_no_space():
    """Test extracting vote count from tags with no space between number and vote."""
    entry = {
        "summary": "Another deal",
        "tags": [{"term": "25vote"}]
    }
    assert _parse_votes(entry) == 25

def test_parse_votes_not_found():
    """Test that function returns 0 when no vote info is present."""
    entry = {
        "summary": "No votes mentioned here.",
        "tags": [{"term": "random"}]
    }
    assert _parse_votes(entry) == 0

def test_parse_votes_empty_entry():
    """Test with an empty entry dictionary."""
    entry = {}
    assert _parse_votes(entry) == 0

def test_parse_votes_invalid_tag():
    """Test handling of a tag that contains 'vote' but no numbers."""
    entry = {
        "summary": "Just a normal deal.",
        "tags": [{"term": "vote please"}]
    }
    assert _parse_votes(entry) == 0
