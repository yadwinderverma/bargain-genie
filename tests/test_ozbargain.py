import pytest
from src.fetchers.ozbargain import _parse_discount_from_title

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
