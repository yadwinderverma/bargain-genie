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


def test_parse_votes_prefers_feed_metadata():
    entry = {
        "ozb_meta": {"votes-pos": "42", "votes-neg": "3"},
        "summary": "This deal has 1 vote in the blurb.",
    }
    assert _parse_votes(entry) == 42


def test_node_id_uses_the_node_link_not_the_guid():
    from src.fetchers.ozbargain import _node_id

    assert _node_id({
        "link": "https://www.ozbargain.com.au/node/976449",
        "id": "976449 at https://www.ozbargain.com.au",
    }) == "976449"


def test_offer_ignores_zero_dollar_delivery():
    from src.fetchers.ozbargain import _parse_offer_from_title

    sale, original, discount = _parse_offer_from_title(
        "Hugo Boss Bottled 100ml $54.99 (RRP $155) +Delivery ($0 Prime/$59 Spend) @ Amazon AU"
    )
    assert sale == 54.99
    assert original == 155
    assert discount == 64.5


def test_offer_was_price_and_paid_delivery():
    from src.fetchers.ozbargain import _parse_offer_from_title

    sale, original, discount = _parse_offer_from_title(
        "Uniqlo Jacket $59.90 (Was $149.90, 60% off) + $7.95 Delivery ($0 C&C/ $75 Order) @ UNIQLO"
    )
    assert sale == 59.9
    assert original == 149.9
    assert discount == 60.0


def test_click_and_collect_zero_inside_the_rrp_paren_is_not_the_price():
    from src.fetchers.ozbargain import _parse_offer_from_title

    sale, original, discount = _parse_offer_from_title(
        "McLaren Vale Shiraz 12-Bottles $99 Delivered (RRP $264, $0 SA C&C) @ Bec Hardy Wines"
    )
    assert sale == 99
    assert original == 264
    assert discount == 62.5


def test_delivery_zero_is_not_a_freebie():
    from src.fetchers.ozbargain import _is_freebie

    title = "Google Fitbit Air $199 + Delivery ($0 C&C/ In-Store) @ The Good Guys"
    assert _is_freebie(title, "", []) is False


def test_free_shipping_is_not_a_freebie():
    from src.fetchers.ozbargain import _is_freebie

    assert _is_freebie("Coffee Beans $39.95 + Free Shipping @ Manna Beans", "", []) is False


def test_real_freebie_title():
    from src.fetchers.ozbargain import _is_freebie

    assert _is_freebie("[iOS] Free: Castlevania @ Apple App Store", "free returns", []) is True


def test_contract_handset_is_not_a_freebie():
    from src.fetchers.ozbargain import _is_contract, _is_freebie

    title = "Pixel 11 Pro 256GB $0 with Optus $69/M 24-Month SIM Only Plan @ Harvey Norman"
    assert _is_contract(title) is True
    assert _is_freebie(title, "", []) is False


def test_short_number_keyword_must_be_in_the_title():
    from src.fetchers.ozbargain import _matches_search_queries

    assert _matches_search_queries("Shokz OpenFit Air", "includes 2 year warranty") is False
    assert _matches_search_queries("Shokz OpenFit 2", "standard warranty") is True
    assert _matches_search_queries("Shokz OpenFit 2", "refurbished stock") is False
    assert _matches_search_queries("Shokz OpenFit Air 2 year warranty", "") is False
    assert _matches_search_queries("Beats Powerbeats Pro 2, 2 year warranty", "") is True
    assert _matches_search_queries("Leaf blower kit", "") is True
    assert _matches_search_queries("Line trimmer", "") is True
    assert _matches_search_queries("Whipper snipper", "") is True
    assert _matches_search_queries("Snow leaf blower", "") is False


def test_fetcher_reads_votes_price_and_merchant_url(monkeypatch):
    from src.fetchers.ozbargain import OzBargainFetcher

    entry = {
        "title": "Shokz OpenFit 2 $80 (RRP $200) + Delivery ($0 C&C) @ Amazon AU",
        "link": "https://www.ozbargain.com.au/node/42",
        "id": "42 at https://www.ozbargain.com.au",
        "summary": "<p>Open ear headphones.</p>",
        "tags": [],
        "published": "Fri, 25 Sep 2026 20:22:07 +1000",
        "ozb_meta": {
            "votes-pos": "12",
            "votes-neg": "1",
            "url": "https://www.amazon.com.au/dp/SHOZ2",
        },
    }
    feed = type("Feed", (), {"bozo": False, "entries": [entry], "bozo_exception": None})()
    monkeypatch.setattr("src.fetchers.ozbargain._get_ozbargain_feed", lambda: feed)

    deals = OzBargainFetcher().fetch()
    assert len(deals) == 1
    deal = deals[0]
    assert deal.id == "ozb_42"
    assert deal.sale_price == 80
    assert deal.original_price == 200
    assert deal.discount_pct == 60
    assert deal.votes == 12
    assert deal.community_validated is True
    assert deal.merchant_url == "https://www.amazon.com.au/dp/SHOZ2"
    assert "<p>" not in deal.description


def test_zero_delivery_title_is_not_a_freebie_even_with_lots_of_votes(monkeypatch):
    from src.fetchers.ozbargain import OzBargainFreebieFetcher

    entry = {
        "title": "Google Fitbit Air $199 + Delivery ($0 C&C/ In-Store) @ The Good Guys",
        "link": "https://www.ozbargain.com.au/node/973284",
        "id": "973284 at https://www.ozbargain.com.au",
        "summary": "<p>A tracker.</p>",
        "tags": [],
        "published": "",
        "ozb_meta": {"votes-pos": "40", "url": "https://www.thegoodguys.com.au/fitbit"},
    }
    feed = type("Feed", (), {"bozo": False, "entries": [entry]})()
    monkeypatch.setattr("src.fetchers.ozbargain._get_ozbargain_feed", lambda: feed)
    assert OzBargainFreebieFetcher().fetch() == []
