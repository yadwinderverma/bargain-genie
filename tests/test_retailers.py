import unittest
from src.fetchers.retailers import _matches_product

class TestMatchesProduct(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(_matches_product("Shokz OpenFit 2 Black", "shokz openfit 2"))

    def test_out_of_order_match(self):
        self.assertTrue(_matches_product("OpenFit 2 Shokz", "shokz openfit 2"))

    def test_missing_keyword(self):
        self.assertFalse(_matches_product("Shokz OpenComm 2", "shokz openfit 2"))

    def test_case_insensitive(self):
        self.assertTrue(_matches_product("SHOKZ OPENFIT", "shokz openfit"))

    def test_partial_word_match(self):
        # The current implementation uses `kw in title_lower`, so partial words match.
        self.assertTrue(_matches_product("Shokz OpenFit 2", "shokz fit"))

    def test_empty_query(self):
        self.assertTrue(_matches_product("Shokz OpenFit", ""))

    def test_no_match(self):
        self.assertFalse(_matches_product("Sony Headphones", "shokz openfit"))

if __name__ == '__main__':
    unittest.main()
