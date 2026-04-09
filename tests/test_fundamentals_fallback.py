import unittest
from unittest.mock import patch
from types import SimpleNamespace

from langchain_core.messages import ToolMessage

from tradingagents.agents.analysts.fundamentals_analyst import (
    _build_fallback_report_from_outputs,
    _build_fallback_fundamentals_report,
    _fetch_direct_fundamental_tool_outputs,
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

    @patch(
        "tradingagents.agents.analysts.fundamentals_analyst.get_config",
        return_value={"output_language": "Chinese"},
    )
    def test_direct_tool_fetch_can_build_report(self, _mock_config):
        fake_tools = {
            "get_fundamentals": SimpleNamespace(
                invoke=lambda _payload: "# A-share fundamentals for 300308.SZ\n\n| 指标 | 数值 |\n|---|---|\n| 营收 | 100 |"
            ),
            "get_balance_sheet": SimpleNamespace(
                invoke=lambda _payload: "# Balance Sheet for 300308.SZ\n\n| 报告日 | 资产总计 |\n|---|---|\n| 20251231 | 1000 |"
            ),
            "get_cashflow": SimpleNamespace(
                invoke=lambda _payload: "# Cash Flow for 300308.SZ\n\n| 报告日 | 经营现金流 |\n|---|---|\n| 20251231 | 66 |"
            ),
            "get_income_statement": SimpleNamespace(
                invoke=lambda _payload: "# Income Statement for 300308.SZ\n\n| 报告日 | 净利润 |\n|---|---|\n| 20251231 | 88 |"
            ),
        }

        with patch.multiple(
            "tradingagents.agents.analysts.fundamentals_analyst",
            get_fundamentals=fake_tools["get_fundamentals"],
            get_balance_sheet=fake_tools["get_balance_sheet"],
            get_cashflow=fake_tools["get_cashflow"],
            get_income_statement=fake_tools["get_income_statement"],
        ):
            outputs = _fetch_direct_fundamental_tool_outputs("300308.SZ", "2026-04-09")
            report = _build_fallback_report_from_outputs(outputs, "300308.SZ")

        self.assertEqual(
            set(outputs.keys()),
            {"fundamentals", "balance_sheet", "cashflow", "income_statement"},
        )
        self.assertIsNotNone(report)
        self.assertIn("利润表", report)
        self.assertIn("现金流量表", report)


if __name__ == "__main__":
    unittest.main()
