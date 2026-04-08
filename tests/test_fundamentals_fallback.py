import unittest
from unittest.mock import patch

from langchain_core.messages import ToolMessage

from tradingagents.agents.analysts.fundamentals_analyst import (
    _build_fallback_fundamentals_report,
    _report_indicates_missing_data,
)


class FundamentalsFallbackTests(unittest.TestCase):
    def test_missing_data_markers_are_detected(self):
        report = "基本面数据获取 | ❌ 失败 | 无法从当前数据源获取信息"
        self.assertTrue(_report_indicates_missing_data(report))

    @patch(
        "tradingagents.agents.analysts.fundamentals_analyst.get_config",
        return_value={"output_language": "Chinese"},
    )
    def test_fallback_report_uses_successful_tool_outputs(self, _mock_config):
        messages = [
            ToolMessage(
                content="# A-share fundamentals for 300308.SZ\n\n| 指标 | 数值 |\n|---|---|\n| 营收 | 100 |",
                tool_call_id="1",
                name="get_fundamentals",
            ),
            ToolMessage(
                content="# Balance Sheet for 300308.SZ (quarterly)\n\n| 报告日 | 资产总计 |\n|---|---|\n| 20251231 | 1000 |",
                tool_call_id="2",
                name="get_balance_sheet",
            ),
        ]

        report = _build_fallback_fundamentals_report(messages, "300308.SZ")

        self.assertIsNotNone(report)
        self.assertIn("基本面数据汇总", report)
        self.assertIn("300308.SZ", report)
        self.assertIn("综合指标", report)
        self.assertIn("资产负债表", report)


if __name__ == "__main__":
    unittest.main()
