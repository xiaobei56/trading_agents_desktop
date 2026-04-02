import unittest
from unittest.mock import patch

import akshare as ak
import pandas as pd

from tradingagents.dataflows.akshare_a_stock import get_news_akshare
from tradingagents.dataflows.interface import route_to_vendor


class ChinaNewsQueryTests(unittest.TestCase):
    @patch("tradingagents.dataflows.akshare_a_stock.to_mainland_stock_code", return_value=None)
    def test_get_news_akshare_supports_board_keyword_query(self, _mock_code):
        board_df = pd.DataFrame(
            [
                {
                    "板块名称": "黄金概念",
                    "涨跌幅": -2.02,
                    "主力净流入": -492771.99,
                    "板块异动总次数": 81,
                    "板块异动最频繁个股及所属类型-股票名称": "ST萃华",
                    "板块异动最频繁个股及所属类型-买卖方向": "大笔买入",
                }
            ]
        )
        market_news_df = pd.DataFrame(
            [
                {
                    "tag": "市场动态",
                    "summary": "高盛分析师表示，黄金的中期前景依然稳固，金价可能继续走高。",
                    "url": "https://database.caixin.com/2026-04-02/102429435.html?cxapp_link=true",
                }
            ]
        )

        def fake_call(func, *args, **kwargs):
            if func is ak.stock_board_change_em:
                return board_df
            if func is ak.stock_news_main_cx:
                return market_news_df
            raise AssertionError(f"Unexpected AkShare function: {func}")

        with patch("tradingagents.dataflows.akshare_a_stock._call_akshare", side_effect=fake_call):
            result = get_news_akshare("黄金板块", "2026-03-20", "2026-04-03")

        self.assertIn("黄金板块 China-focused targeted news", result)
        self.assertIn("中国板块异动快照", result)
        self.assertIn("黄金概念", result)
        self.assertIn("关键词相关新闻", result)

    def test_route_to_vendor_falls_back_when_akshare_query_is_unsupported(self):
        def unsupported_akshare(*args, **kwargs):
            raise ValueError("Unsupported mainland China ticker or stock name: foo")

        def fallback_vendor(*args, **kwargs):
            return "fallback ok"

        config = {
            "data_vendors": {"news_data": "yfinance"},
            "tool_vendors": {},
            "market_region": "china_mainland",
        }

        with patch("tradingagents.dataflows.interface.get_config", return_value=config):
            with patch.dict(
                "tradingagents.dataflows.interface.VENDOR_METHODS",
                {"get_news": {"akshare": unsupported_akshare, "yfinance": fallback_vendor}},
                clear=False,
            ):
                result = route_to_vendor("get_news", "foo", "2026-04-01", "2026-04-03")

        self.assertEqual(result, "fallback ok")


if __name__ == "__main__":
    unittest.main()
