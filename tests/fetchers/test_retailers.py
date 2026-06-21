import pytest
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
