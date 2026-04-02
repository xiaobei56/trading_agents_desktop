import unittest
from unittest.mock import patch

from cli.utils import normalize_ticker_symbol
from tradingagents.agents.utils.agent_utils import build_instrument_context
from tradingagents.ticker_utils import infer_market_region


class TickerSymbolHandlingTests(unittest.TestCase):
    def test_normalize_ticker_symbol_preserves_exchange_suffix(self):
        self.assertEqual(normalize_ticker_symbol(" cnc.to "), "CNC.TO")

    @patch(
        "tradingagents.ticker_utils._get_china_mainland_name_map",
        return_value={"中际旭创": "300308.SZ"},
    )
    def test_normalize_ticker_symbol_resolves_chinese_stock_name(self, _mock_name_map):
        self.assertEqual(normalize_ticker_symbol(" 中际旭创 "), "300308.SZ")
        self.assertEqual(infer_market_region("中际旭创"), "china_mainland")

    def test_build_instrument_context_mentions_exact_symbol(self):
        context = build_instrument_context("7203.T")
        self.assertIn("7203.T", context)
        self.assertIn("exchange suffix", context)


if __name__ == "__main__":
    unittest.main()
