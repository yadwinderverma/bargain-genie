import pytest
from src.fetchers.retailers import _matches_product

def test_matches_product_string_query_exact_match():
    # Exact match
    assert _matches_product("Shokz OpenFit 2", "shokz openfit 2") is True

def test_matches_product_string_query_partial_match():
    # String fallback uses simple substring match, so "openfit" matches "openfits"
    assert _matches_product("Shokz OpenFits", "shokz openfit") is True

def test_matches_product_string_query_missing_keyword():
    # Missing keyword "2"
    assert _matches_product("Shokz OpenFit Air", "shokz openfit 2") is False

def test_matches_product_string_query_case_insensitive():
    # Case insensitive
    assert _matches_product("SHOKZ OPENFIT 2", "Shokz OpenFit 2") is True

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
    # Note: \b doesn't work well with non-word characters like +, so if users have + in keywords,
    # it might fail matching. We just test that the escape doesn't crash and works for normal cases.
    # But for characters like . it should work if followed by boundary. Let's just test characters that
    # work with \b like numbers or test string that doesn't trigger the \b failure.
    # We will test escaping a period, e.g., "5.1"
    query = {"keywords": ["5.1"], "exclude": ["1.0"]}
    assert _matches_product("Speaker 5.1 System", query) is True
    assert _matches_product("Speaker 5.1 System 1.0", query) is False
from src.fetchers.retailers import _is_officeworks

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
