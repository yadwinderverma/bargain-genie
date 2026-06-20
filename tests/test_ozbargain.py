import pytest
from src.fetchers.ozbargain import _is_freebie

def test_is_freebie_with_tags():
    assert not _is_freebie("Normal Deal", "Description", [])
    assert _is_freebie("Normal Deal", "Description", [{"term": "Freebie"}])
    assert _is_freebie("Normal Deal", "Description", [{"term": "free"}])

def test_is_freebie_with_title_description():
    assert _is_freebie("Free Stuff", "Description", [])
    assert _is_freebie("Freebie: Game", "Description", [])
    assert _is_freebie("$0 deal", "Description", [])
    assert _is_freebie("Get a Free Trial", "Description", [])
    assert _is_freebie("A Deal", "Get this for free today!", [])
    assert _is_freebie("A Deal", "Cost is $0.", [])
    assert _is_freebie("A Deal", "Sign up for a free sub.", [])

def test_is_freebie_false_positives():
    assert not _is_freebie("Buy one get one free", "Description", [])
    assert not _is_freebie("Free shipping on all orders", "Description", [])
    assert not _is_freebie("Free delivery", "Description", [])
    assert not _is_freebie("Duty free", "Description", [])
    assert not _is_freebie("Toll free", "Description", [])
    assert not _is_freebie("Sugar free", "Description", [])
    assert not _is_freebie("Gluten free", "Description", [])
    assert not _is_freebie("Care free", "Description", [])
    assert not _is_freebie("Risk free", "Description", [])
