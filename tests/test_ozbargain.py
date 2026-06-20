import pytest
from src.fetchers.ozbargain import _parse_votes

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
