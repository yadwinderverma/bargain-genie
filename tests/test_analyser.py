import unittest
from unittest.mock import patch, MagicMock
from src.analyser import DealAnalyser
from src.models import Deal

class TestDealAnalyserPrompt(unittest.TestCase):
    def setUp(self):
        # We don't need a real Gemini client to test prompt building
        with patch.object(DealAnalyser, '_get_client', return_value=None):
            self.analyser = DealAnalyser()

    def test_build_prompt_basic_fields(self):
        deal = Deal(
            id="1",
            source="test_source",
            title="Test Product Title",
            url="http://example.com/deal",
            description="A great product description.",
            original_price=100.0,
            sale_price=50.0,
            discount_pct=50.0,
            votes=15
        )
        prompt = self.analyser._build_prompt([deal])

        self.assertIn("Test Product Title", prompt)
        self.assertIn("test_source", prompt)
        self.assertIn("$100.0", prompt)
        self.assertIn("$50.0", prompt)
        self.assertIn("50.0%", prompt)
        self.assertIn("15", prompt)
        self.assertIn("A great product description.", prompt)

    def test_build_prompt_freebie_without_duration(self):
        deal = Deal(
            id="2",
            source="ozbargain",
            title="Free Game",
            url="http://example.com/freebie",
            description="Get this game for free.",
            is_freebie=True,
            votes=42
        )
        prompt = self.analyser._build_prompt([deal])
        self.assertIn("[FREEBIE — 42 OzBargain upvotes]", prompt)

    def test_build_prompt_freebie_with_duration(self):
        deal = Deal(
            id="3",
            source="ozbargain",
            title="Free Game Weekend",
            url="http://example.com/freebie-weekend",
            description="Play free this weekend.",
            is_freebie=True,
            duration_note="ends Monday",
            votes=99
        )
        prompt = self.analyser._build_prompt([deal])
        self.assertIn("[FREEBIE (ends Monday) — 99 OzBargain upvotes]", prompt)

    def test_build_prompt_ozbargain_community_validated(self):
        deal = Deal(
            id="4",
            source="ozbargain",
            title="Popular Deal",
            url="http://example.com/popular",
            description="Highly upvoted.",
            community_validated=True,
            votes=200
        )
        prompt = self.analyser._build_prompt([deal])
        self.assertIn("[COMMUNITY VALIDATED — 200 OzBargain upvotes]", prompt)

    def test_build_prompt_officeworks_price_beat(self):
        deal = Deal(
            id="5",
            source="officeworks",
            title="Cheap Printer",
            url="http://example.com/printer",
            description="Price beat matching.",
            price_beat_retailer=True
        )
        prompt = self.analyser._build_prompt([deal])
        self.assertIn("[OFFICEWORKS — 5% Price Beat Guarantee, likely lowest AU price]", prompt)

    def test_build_prompt_multiple_deals(self):
        deal1 = Deal(id="1", source="src1", title="Product 1", url="url1", description="desc1")
        deal2 = Deal(id="2", source="src2", title="Product 2", url="url2", description="desc2")
        deal3 = Deal(id="3", source="src3", title="Product 3", url="url3", description="desc3")

        prompt = self.analyser._build_prompt([deal1, deal2, deal3])

        self.assertIn("Deal 1:", prompt)
        self.assertIn("Product 1", prompt)
        self.assertIn("Deal 2:", prompt)
        self.assertIn("Product 2", prompt)
        self.assertIn("Deal 3:", prompt)
        self.assertIn("Product 3", prompt)

class TestDealAnalyserFixes(unittest.TestCase):
    @patch.dict('os.environ', {}, clear=True)
    def test_get_client_raises_value_error_without_api_key(self):
        with self.assertRaises(ValueError) as ctx:
            DealAnalyser()
        self.assertIn("GEMINI_API_KEY environment variable is not set", str(ctx.exception))

    def test_sanitize_text(self):
        with patch.object(DealAnalyser, '_get_client', return_value=None):
            analyser = DealAnalyser()
        self.assertEqual(analyser._sanitize_text("Normal Title"), "Normal Title")
        self.assertEqual(analyser._sanitize_text("Title <with> tags"), "Title &lt;with&gt; tags")
        self.assertEqual(analyser._sanitize_text(""), "")
        self.assertEqual(analyser._sanitize_text(None), "")

    def test_attach_scores_fail_closed_on_missing_index(self):
        with patch.object(DealAnalyser, '_get_client', return_value=None):
            analyser = DealAnalyser()

        from src.analyser import DealScore
        deal1 = Deal(id="1", source="test", title="Deal 1", url="url")
        deal2 = Deal(id="2", source="test", title="Deal 2", url="url")
        
        # Only return score for deal 1
        results = [
            DealScore(deal_index=1, score=8, genuine_discount=True, reason="Great", category="Tech")
        ]
        
        analyser._attach_scores([deal1, deal2], results)
        
        # Deal 1 should have correct score
        self.assertEqual(deal1.llm_score, 8)
        self.assertEqual(deal1.llm_reason, "Great")
        self.assertTrue(deal1.llm_genuine)
        
        # Deal 2 (missing index) should fail-closed (score 1)
        self.assertEqual(deal2.llm_score, 1)
        self.assertEqual(deal2.llm_reason, "Error: No LLM score returned")
        self.assertFalse(deal2.llm_genuine)

    @patch('src.analyser.DealAnalyser')
    def test_legacy_wrapper_singleton(self, mock_analyser_class):
        mock_instance = MagicMock()
        mock_analyser_class.return_value = mock_instance
        
        from src.analyser import analyse_deals, _analyser_instance
        
        # Reset the global singleton instance if any
        import src.analyser
        src.analyser._analyser_instance = None
        
        deals = [Deal(id="1", source="test", title="Deal 1", url="url")]
        analyse_deals(deals)
        analyse_deals(deals)
        
        # Ensure DealAnalyser was instantiated only once
        mock_analyser_class.assert_called_once()

if __name__ == '__main__':
    unittest.main()
