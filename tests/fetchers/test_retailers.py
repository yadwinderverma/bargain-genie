import pytest
from src.fetchers.retailers import (
    _matches_product, _is_officeworks, _parse_price, _match_trusted_retailer
)

# ==========================================
# _matches_product Tests
# ==========================================

def test_matches_product_string_query_exact_match():
    # Exact match
    assert _matches_product("Shokz OpenFit 2", "shokz openfit 2") is True

def test_matches_product_string_query_out_of_order_match():
    # Out of order
    assert _matches_product("OpenFit 2 Shokz", "shokz openfit 2") is True

def test_matches_product_string_query_partial_match():
    # String fallback uses simple substring match, so "openfit" matches "openfits"
    assert _matches_product("Shokz OpenFits", "shokz openfit") is True

def test_matches_product_string_query_partial_word_match():
    # Substring of keywords
    assert _matches_product("Shokz OpenFit 2", "shokz fit") is True

def test_matches_product_string_query_missing_keyword():
    # Missing keyword "2"
    assert _matches_product("Shokz OpenFit Air", "shokz openfit 2") is False

def test_matches_product_string_query_case_insensitive():
    # Case insensitive
    assert _matches_product("SHOKZ OPENFIT 2", "Shokz OpenFit 2") is True

def test_matches_product_string_query_empty_query():
    assert _matches_product("Shokz OpenFit", "") is True

def test_matches_product_dict_query_exact_match():
    query = {"keywords": ["shokz", "openfit", "2"], "exclude": ["case"]}
    assert _matches_product("Shokz OpenFit 2", query) is True

def test_matches_product_dict_query_word_boundaries():
    query = {"keywords": ["shokz", "openfit", "2"]}
    # "openfit2" doesn't have word boundary between openfit and 2
    # So "openfit" won't match "openfit2" because of the trailing 2
    assert _matches_product("Shokz OpenFit2", query) is False

def test_matches_product_dict_query_case_insensitive():
    query = {"keywords": ["Shokz", "OPENFIT", "2"]}
    assert _matches_product("shokz openfit 2", query) is True

def test_matches_product_dict_query_missing_keyword():
    query = {"keywords": ["shokz", "openfit", "2"]}
    assert _matches_product("Shokz OpenFit Air", query) is False

def test_matches_product_dict_query_empty_keywords():
    query = {"keywords": [], "exclude": ["case"]}
    assert _matches_product("Shokz OpenFit", query) is False

def test_matches_product_dict_query_exclude_word():
    query = {"keywords": ["shokz", "openfit"], "exclude": ["case", "cover"]}
    assert _matches_product("Shokz OpenFit Case", query) is False
    assert _matches_product("Shokz OpenFit cover", query) is False

def test_matches_product_dict_query_exclude_word_boundary():
    query = {"keywords": ["shokz", "openfit"], "exclude": ["case"]}
    # "cases" shouldn't trigger "case" exclusion due to word boundaries
    assert _matches_product("Shokz OpenFit Cases", query) is True

def test_matches_product_dict_query_regex_escape():
    # Ensures regex special characters in keywords and excludes are correctly escaped.
    query = {"keywords": ["5.1"], "exclude": ["1.0"]}
    assert _matches_product("Speaker 5.1 System", query) is True
    assert _matches_product("Speaker 5.1 System 1.0", query) is False


# ==========================================
# _is_officeworks Tests
# ==========================================

def test_is_officeworks_exact_match():
    assert _is_officeworks("officeworks") is True

def test_is_officeworks_domain():
    assert _is_officeworks("officeworks.com.au") is True

def test_is_officeworks_case_insensitivity():
    assert _is_officeworks("Officeworks") is True
    assert _is_officeworks("OFFICEWORKS") is True
    assert _is_officeworks("OfFiCeWoRkS") is True

def test_is_officeworks_substring():
    assert _is_officeworks("https://www.officeworks.com.au/product/123") is True
    assert _is_officeworks("some text officeworks some more text") is True

def test_is_officeworks_negative_cases():
    assert _is_officeworks("amazon.com.au") is False
    assert _is_officeworks("jbhifi.com.au") is False
    assert _is_officeworks("harvey norman") is False
    assert _is_officeworks("") is False

def test_is_officeworks_with_spaces():
    assert _is_officeworks(" office works ") is False
    assert _is_officeworks(" officeworks ") is True


# ==========================================
# _parse_price Tests
# ==========================================

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


# ==========================================
# _match_trusted_retailer Tests
# ==========================================

def test_match_trusted_retailer_exact_match():
    assert _match_trusted_retailer("amazon.com.au") == "Amazon AU"
    assert _match_trusted_retailer("jbhifi.com.au") == "JB Hi-Fi"
    assert _match_trusted_retailer("costco.com.au") == "Costco AU"

def test_match_trusted_retailer_case_insensitive():
    assert _match_trusted_retailer("OFFICEWORKS.COM.AU") == "Officeworks"
    assert _match_trusted_retailer("Kogan.com") == "Kogan"
    assert _match_trusted_retailer("HarVeyNorMan.cOm.aU") == "Harvey Norman"

def test_match_trusted_retailer_substring():
    assert _match_trusted_retailer("https://www.bigw.com.au/product/123") == "Big W"
    assert _match_trusted_retailer("catch.com.au/store/deals") == "Catch"
    assert _match_trusted_retailer("www.amazon.com.au") == "Amazon AU"

def test_match_trusted_retailer_untrusted():
    assert _match_trusted_retailer("ebay.com.au") is None
    assert _match_trusted_retailer("cashconverters.com.au") is None
    assert _match_trusted_retailer("amazon.com") is None
    assert _match_trusted_retailer("randomsite.com") is None

def test_match_trusted_retailer_edge_cases():
    assert _match_trusted_retailer("") is None
    assert _match_trusted_retailer(" ") is None
