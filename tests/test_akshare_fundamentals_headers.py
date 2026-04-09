import unittest
from unittest.mock import patch

import pandas as pd

from tradingagents.dataflows.akshare_a_stock import (
    get_balance_sheet_akshare,
    get_cashflow_akshare,
    get_fundamentals_akshare,
    get_income_statement_akshare,
)


class AkshareFundamentalsHeadersTests(unittest.TestCase):
    @patch("tradingagents.dataflows.akshare_a_stock.to_mainland_stock_code", return_value="300308")
    @patch("tradingagents.dataflows.akshare_a_stock._call_akshare")
    def test_get_fundamentals_includes_source_and_report_period(
        self,
        mock_call,
        _mock_code,
    ):
        abstract_df = pd.DataFrame(
            {
                "选项": ["常用指标"],
                "指标": ["营业总收入"],
                "20251231": [100],
                "20250930": [80],
            }
        )
        ths_df = pd.DataFrame({"报告期": ["2025-12-31"], "净利润": [10]})
        mock_call.side_effect = [abstract_df, ths_df]

        result = get_fundamentals_akshare("300308.SZ", "2026-04-09")

        self.assertIn("# Source: AkShare / 新浪财经 / 同花顺", result)
        self.assertIn("# Latest report period: 20251231", result)
        self.assertIn("# Data retrieved on:", result)

    @patch("tradingagents.dataflows.akshare_a_stock._to_prefixed_symbol", return_value="sz300308")
    @patch("tradingagents.dataflows.akshare_a_stock._call_akshare")
    def test_financial_statements_include_source_headers(
        self,
        mock_call,
        _mock_symbol,
    ):
        df = pd.DataFrame(
            {
                "报告日": ["20251231"],
                "资产总计": [1000],
                "经营活动产生的现金流量净额": [300],
                "净利润": [88],
            }
        )
        mock_call.side_effect = [df, df, df]

        balance = get_balance_sheet_akshare("300308.SZ", curr_date="2026-04-09")
        cashflow = get_cashflow_akshare("300308.SZ", curr_date="2026-04-09")
        income = get_income_statement_akshare("300308.SZ", curr_date="2026-04-09")

        for output in (balance, cashflow, income):
            self.assertIn("# Source: AkShare / 新浪财经", output)
            self.assertIn("# Data retrieved on:", output)
            self.assertIn("# Latest report period: 20251231", output)


if __name__ == "__main__":
    unittest.main()
