import pytest
from unittest.mock import patch, MagicMock
import requests

from src.models import Deal
from main import verify_deal_price

@pytest.fixture
def base_deal():
    return Deal(
        id="test_deal_1",
        title="Apple AirPods Pro",
        source="kogan",
        url="https://www.kogan.com/au/buy/apple-airpods-pro",
        sale_price=170.0,
        original_price=329.0,
        discount_pct=48.0,
        llm_score=8,
        llm_reason="Good deal",
        is_freebie=False
    )

def test_verify_deal_price_disabled(base_deal):
    with patch("config.VERIFY_PRICES_LIVE", False):
        assert verify_deal_price(base_deal) is True

def test_verify_deal_price_no_url(base_deal):
    base_deal.url = ""
    assert verify_deal_price(base_deal) is True

@patch("requests.get")
def test_verify_deal_price_non_200(mock_get, base_deal):
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response
    
    assert verify_deal_price(base_deal) is True

@patch("requests.get")
def test_verify_deal_price_out_of_stock(mock_get, base_deal):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body>Sorry, this item is out of stock!</body></html>"
    mock_get.return_value = mock_response
    
    assert verify_deal_price(base_deal) is False

@patch("requests.get")
def test_verify_deal_price_json_ld_discrepancy(mock_get, base_deal):
    mock_response = MagicMock()
    mock_response.status_code = 200
    # JSON-LD shows price is $313.00, but deal expected $170.00
    mock_response.text = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org/",
          "@type": "Product",
          "name": "Apple AirPods Pro",
          "offers": {
            "@type": "Offer",
            "price": "313.00",
            "priceCurrency": "AUD"
          }
        }
        </script>
      </head>
      <body>Price is $313</body>
    </html>
    """
    mock_get.return_value = mock_response
    
    assert verify_deal_price(base_deal) is False

@patch("requests.get")
def test_verify_deal_price_meta_matching(mock_get, base_deal):
    mock_response = MagicMock()
    mock_response.status_code = 200
    # OpenGraph meta tag matches price (or close enough)
    mock_response.text = """
    <html>
      <head>
        <meta property="og:price:amount" content="170.00">
      </head>
      <body>Price is $170.00</body>
    </html>
    """
    mock_get.return_value = mock_response
    
    assert verify_deal_price(base_deal) is True
    assert base_deal.sale_price == 170.0

@patch("requests.get")
def test_verify_deal_price_fallback_absent(mock_get, base_deal):
    mock_response = MagicMock()
    mock_response.status_code = 200
    # No price metadata and the number "170" is absent from the body (which has $313)
    mock_response.text = "<html><body>The price today is $313.00!</body></html>"
    mock_get.return_value = mock_response
    
    assert verify_deal_price(base_deal) is False

@patch("requests.get")
def test_verify_deal_price_fallback_present(mock_get, base_deal):
    mock_response = MagicMock()
    mock_response.status_code = 200
    # No price metadata but the number "170" is present in the body
    mock_response.text = "<html><body>Special Kogan price: $170 right now!</body></html>"
    mock_get.return_value = mock_response
    
    assert verify_deal_price(base_deal) is True
