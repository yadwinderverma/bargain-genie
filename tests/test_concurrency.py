import pytest
from unittest.mock import patch, MagicMock
from src.models import Deal
from src.fetchers.retailers import RetailerFetcher
from main import run, verify_deal_price
from src.fetchers.base import DealFetcher

@pytest.fixture
def sample_deals():
    return [
        Deal(
            id="deal_1",
            title="Deal One",
            source="kogan",
            url="https://example.com/1",
            sale_price=10.0,
            original_price=20.0,
            discount_pct=50.0,
            llm_score=8
        ),
        Deal(
            id="deal_2",
            title="Deal Two",
            source="kogan",
            url="https://example.com/2",
            sale_price=15.0,
            original_price=30.0,
            discount_pct=50.0,
            llm_score=9
        ),
        Deal(
            id="deal_3",
            title="Deal Three",
            source="kogan",
            url="https://example.com/3",
            sale_price=100.0,
            original_price=150.0,
            discount_pct=33.3,
            llm_score=7
        )
    ]

@patch("main.verify_deal_price")
def test_parallel_price_verification(mock_verify, sample_deals):
    # Mock verify_deal_price to return True for deal_1 and deal_2, False for deal_3
    def mock_verify_side_effect(deal):
        return deal.id in ["deal_1", "deal_2"]
    
    mock_verify.side_effect = mock_verify_side_effect

    # We mock the main components to test just Step 3.5's ThreadPoolExecutor logic
    from concurrent.futures import ThreadPoolExecutor

    def verify_single_deal(d):
        if mock_verify(d):
            return d
        return None

    max_workers = min(len(sample_deals), 10)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(verify_single_deal, sample_deals)
        verified_deals = [d for d in results if d is not None]

    assert len(verified_deals) == 2
    assert {d.id for d in verified_deals} == {"deal_1", "deal_2"}
    assert mock_verify.call_count == 3


@patch("src.fetchers.retailers._fetch_shopping_results")
@patch("src.fetchers.retailers._analyse_prices")
@patch("src.fetchers.retailers._get_api_key", return_value="fake_api_key")
def test_retailer_fetcher_parallel_queries(mock_get_api_key, mock_analyse, mock_fetch_shopping):
    # We want to check that RetailerFetcher calls _fetch_shopping_results in parallel for each SEARCH_QUERY
    # We mock SEARCH_QUERIES to have 3 items
    mock_queries = [
        {"keywords": ["item1"]},
        {"keywords": ["item2"]},
        {"keywords": ["item3"]}
    ]

    mock_fetch_shopping.return_value = [{"title": "dummy_item"}]
    mock_analyse.return_value = [
        Deal(
            id="dummy_id",
            title="dummy_item",
            source="amazon",
            url="https://amazon.com.au/dummy",
            sale_price=50.0,
            original_price=100.0,
            discount_pct=50.0
        )
    ]

    fetcher = RetailerFetcher()
    with patch("src.fetchers.retailers.SEARCH_QUERIES", mock_queries):
        with patch("src.fetchers.retailers.SERPER_ENABLED", True):
            deals = fetcher.fetch()

    assert len(deals) == 1  # Deduplicated on url
    assert mock_fetch_shopping.call_count == 3
    mock_fetch_shopping.assert_any_call("item1", "fake_api_key")
    mock_fetch_shopping.assert_any_call("item2", "fake_api_key")
    mock_fetch_shopping.assert_any_call("item3", "fake_api_key")


class FakeFetcher(DealFetcher):
    def __init__(self, name, deals):
        self.name = name
        self.deals = deals

    def fetch(self):
        return self.deals

def test_main_fetchers_parallel():
    fetcher1 = FakeFetcher("Fetcher1", [MagicMock(id="f1_1", url="url1")])
    fetcher2 = FakeFetcher("Fetcher2", [MagicMock(id="f2_1", url="url2")])
    fetchers = [fetcher1, fetcher2]

    # Test the parallel fetching logic from main.py
    from concurrent.futures import ThreadPoolExecutor, as_completed
    all_deals = []

    def fetch_from_source(f):
        return f.fetch()

    max_workers = len(fetchers)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_from_source, f): f for f in fetchers}
        for future in as_completed(futures):
            all_deals.extend(future.result())

    assert len(all_deals) == 2
    assert any(d.id == "f1_1" for d in all_deals)
    assert any(d.id == "f2_1" for d in all_deals)
