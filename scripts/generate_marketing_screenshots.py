from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication

from tradingagents.desktop.app import MainWindow


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "assets" / "screenshots"


def configure_base_state(window: MainWindow) -> None:
    window.resize(1600, 1020)
    window.ticker_input.setText("中际旭创")
    window.date_input.setDate(QDate(2026, 4, 3))
    window.language_combo.setCurrentIndex(window.language_combo.findData("Chinese"))
    provider_index = window.provider_combo.findData("deepseek")
    if provider_index >= 0:
        window.provider_combo.setCurrentIndex(provider_index)
    depth_index = window.depth_combo.findData(3)
    if depth_index >= 0:
        window.depth_combo.setCurrentIndex(depth_index)
    window.quick_model_combo.setCurrentIndex(0)
    window.deep_model_combo.setCurrentIndex(0)
    window.provider_key_input.clear()
    window.alpha_vantage_input.clear()
    window.open_results_button.setEnabled(True)


def render_config_shot(window: MainWindow) -> Path:
    configure_base_state(window)
    window.run_state_value.setText("待开始")
    window.progress_bar.setValue(0)
    window.llm_calls_value.setText("0")
    window.tool_calls_value.setText("0")
    window.tokens_in_value.setText("0")
    window.tokens_out_value.setText("0")
    window.report_path_value.setText("支持 A股代码、中文股名、板块词")
    window.current_report_view.setMarkdown(
        "## 桌面端亮点\n\n"
        "- 输入 `600519`、`中际旭创`、`黄金板块`\n"
        "- 优先使用中国网络友好的数据链路\n"
        "- 默认推荐 `DeepSeek` 做中文分析"
    )
    window.final_report_view.setMarkdown(
        "## 使用方式\n\n"
        "左侧完成配置，右侧查看实时片段、完整报告、Agent 状态与日志。"
    )
    window.log_view.setPlainText(
        "系统 · 桌面版已启动\n"
        "系统 · 已载入 DeepSeek 模型选项\n"
        "系统 · 当前示例输入：中际旭创"
    )
    window._refresh_agent_table({})
    return save_window(window, "desktop-config-overview.png")


def render_progress_shot(window: MainWindow) -> Path:
    configure_base_state(window)
    window.ticker_input.setText("黄金板块")
    window.run_state_value.setText("运行中")
    window.progress_bar.setValue(58)
    window.llm_calls_value.setText("14")
    window.tool_calls_value.setText("9")
    window.tokens_in_value.setText("48291")
    window.tokens_out_value.setText("7164")
    window.report_path_value.setText("results/黄金板块/2026-04-03/desktop_reports/")
    window.current_report_view.setMarkdown(
        "### 新闻分析\n\n"
        "黄金板块进入高波动阶段，程序已自动切换到中国主题词新闻链路。\n\n"
        "| 维度 | 结论 |\n"
        "| --- | --- |\n"
        "| 板块异动 | 黄金概念、黄金连续出现在板块异动列表 |\n"
        "| 关键词新闻 | 财新头条持续提到金价、央行购金与避险需求 |"
    )
    window.final_report_view.setMarkdown(
        "## 完整报告生成中\n\n"
        "- 市场分析师：已完成\n"
        "- 新闻分析师：进行中\n"
        "- 基本面分析师：等待中"
    )
    window.log_view.setPlainText(
        "09:41:12 系统 · 开始分析黄金板块\n"
        "09:41:18 数据 · route_to_vendor(get_news, 黄金板块)\n"
        "09:41:19 数据 · 已匹配中国板块异动快照\n"
        "09:41:22 数据 · 已匹配财新关键词相关新闻\n"
        "09:41:27 智能体 · News Analyst 正在汇总主题新闻"
    )
    window._refresh_agent_table(
        {
            "Market Analyst": "completed",
            "News Analyst": "in_progress",
            "Social Analyst": "completed",
            "Fundamentals Analyst": "pending",
            "Bull Researcher": "pending",
            "Bear Researcher": "pending",
            "Research Manager": "pending",
            "Trader": "pending",
            "Aggressive Analyst": "pending",
            "Neutral Analyst": "pending",
            "Conservative Analyst": "pending",
            "Portfolio Manager": "pending",
        }
    )
    return save_window(window, "desktop-live-progress.png")


def render_result_shot(window: MainWindow) -> Path:
    configure_base_state(window)
    window.run_state_value.setText("已完成")
    window.progress_bar.setValue(100)
    window.llm_calls_value.setText("31")
    window.tool_calls_value.setText("18")
    window.tokens_in_value.setText("126420")
    window.tokens_out_value.setText("18276")
    window.report_path_value.setText(
        "results/300308.SZ/2026-04-03/desktop_reports/complete_report.md"
    )
    window.current_report_view.setMarkdown(
        "### 组合管理决策\n\n"
        "维持关注，等待更优回撤位置，若放量重回趋势线可考虑分批布局。"
    )
    window.final_report_view.setMarkdown(
        "## 最终结论\n\n"
        "### 标的\n\n"
        "`中际旭创 (300308.SZ)`\n\n"
        "### 综合判断\n\n"
        "- 基本面延续高增长\n"
        "- 光模块与 AI 基建主线仍强\n"
        "- 短线情绪较热，追高性价比一般\n\n"
        "### 执行建议\n\n"
        "1. 观察回撤后的量价承接\n"
        "2. 若重新站稳趋势位，考虑小仓位试探\n"
        "3. 严格设置风险控制位\n\n"
        "| 模块 | 结论 |\n"
        "| --- | --- |\n"
        "| 新闻 | 偏多 |\n"
        "| 基本面 | 偏多 |\n"
        "| 情绪 | 偏热 |\n"
        "| 风险 | 需控制仓位 |"
    )
    window.log_view.setPlainText(
        "09:46:11 系统 · 所有分析师已完成\n"
        "09:46:35 系统 · 研究团队讨论结束\n"
        "09:46:52 系统 · 风控评估完成\n"
        "09:47:03 系统 · 桌面端分析已成功完成"
    )
    window._refresh_agent_table(
        {
            "Market Analyst": "completed",
            "News Analyst": "completed",
            "Social Analyst": "completed",
            "Fundamentals Analyst": "completed",
            "Bull Researcher": "completed",
            "Bear Researcher": "completed",
            "Research Manager": "completed",
            "Trader": "completed",
            "Aggressive Analyst": "completed",
            "Neutral Analyst": "completed",
            "Conservative Analyst": "completed",
            "Portfolio Manager": "completed",
        }
    )
    return save_window(window, "desktop-final-report.png")


def save_window(window: MainWindow, filename: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    window.show()
    QApplication.processEvents()
    output_path = OUTPUT_DIR / filename
    window.grab().save(str(output_path))
    return output_path


def main() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication([])
    window = MainWindow(show_compliance_notice=False)
    outputs = [
        render_config_shot(window),
        render_progress_shot(window),
        render_result_shot(window),
    ]
    for output in outputs:
        print(output)
    window.hide()
    app.quit()


if __name__ == "__main__":
    main()
