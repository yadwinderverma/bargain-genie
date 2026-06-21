import pytest
from src.fetchers.retailers import _is_officeworks

@pytest.mark.parametrize(
    "source, expected",
    [
        # Exact match
        ("officeworks", True),
        # Mixed case
        ("Officeworks", True),
        ("OFFICEWORKS", True),
        ("OfFiCeWoRkS", True),
        # Embedded strings
        ("Officeworks AU", True),
        ("Buy from Officeworks", True),
        ("Officeworks Online", True),
        # Non-matches
        ("JB Hi-Fi", False),
        ("Office", False),
        ("Kmart", False),
        ("", False),
        ("officework", False),
        ("office works", False),
    ]
)
def test_is_officeworks(source, expected):
    """Test the _is_officeworks function correctly identifies Officeworks."""
    assert _is_officeworks(source) == expected
