import pytest

from src.fetchers.retailers import _match_trusted_retailer

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
    assert _match_trusted_retailer("amazon.com") is None # We trust amazon.com.au
    assert _match_trusted_retailer("randomsite.com") is None

def test_match_trusted_retailer_edge_cases():
    assert _match_trusted_retailer("") is None
    assert _match_trusted_retailer(" ") is None
