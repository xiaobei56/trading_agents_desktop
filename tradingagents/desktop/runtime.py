from __future__ import annotations

import datetime as dt
import os
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

from cli.stats_handler import StatsCallbackHandler
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.ticker_utils import infer_market_region

PROVIDER_SPECS = {
    "openai": {
        "label": "OpenAI",
        "env_var": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
    },
    "deepseek": {
        "label": "DeepSeek",
        "env_var": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
    },
    "google": {
        "label": "Google",
        "env_var": "GOOGLE_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1",
    },
    "anthropic": {
        "label": "Anthropic",
        "env_var": "ANTHROPIC_API_KEY",
        "base_url": "https://api.anthropic.com/",
    },
    "xai": {
        "label": "xAI",
        "env_var": "XAI_API_KEY",
        "base_url": "https://api.x.ai/v1",
    },
    "openrouter": {
        "label": "OpenRouter",
        "env_var": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
    },
    "ollama": {
        "label": "Ollama",
        "env_var": None,
        "base_url": "http://localhost:11434/v1",
    },
}

LANGUAGE_DISPLAY_OPTIONS = [
    ("中文", "Chinese"),
    ("English", "English"),
    ("日语", "Japanese"),
    ("韩语", "Korean"),
    ("印地语", "Hindi"),
    ("西班牙语", "Spanish"),
    ("葡萄牙语", "Portuguese"),
    ("法语", "French"),
    ("德语", "German"),
    ("阿拉伯语", "Arabic"),
    ("俄语", "Russian"),
]

LANGUAGE_OPTIONS = [
    "English",
    "Chinese",
    "Japanese",
    "Korean",
    "Hindi",
    "Spanish",
    "Portuguese",
    "French",
    "German",
    "Arabic",
    "Russian",
]

ANALYST_OPTIONS = [
    ("市场分析师", "market"),
    ("社媒分析师", "social"),
    ("新闻分析师", "news"),
    ("基本面分析师", "fundamentals"),
]

RESEARCH_DEPTH_OPTIONS = [
    ("浅度", 1),
    ("中等", 3),
    ("深度", 5),
]

OPENAI_REASONING_OPTIONS = [
    ("中等", "medium"),
    ("高", "high"),
    ("低", "low"),
]

ANTHROPIC_EFFORT_OPTIONS = [
    ("高", "high"),
    ("中等", "medium"),
    ("低", "low"),
]

GOOGLE_THINKING_OPTIONS = [
    ("高", "high"),
    ("轻量", "minimal"),
]

ANALYST_SEQUENCE = ["market", "social", "news", "fundamentals"]
ANALYST_AGENT_NAMES = {
    "market": "Market Analyst",
    "social": "Social Analyst",
    "news": "News Analyst",
    "fundamentals": "Fundamentals Analyst",
}
ANALYST_REPORT_MAP = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
}

STATUS_AGENT_ORDER = [
    "Market Analyst",
    "Social Analyst",
    "News Analyst",
    "Fundamentals Analyst",
    "Bull Researcher",
    "Bear Researcher",
    "Research Manager",
    "Trader",
    "Aggressive Analyst",
    "Neutral Analyst",
    "Conservative Analyst",
    "Portfolio Manager",
]

AGENT_DISPLAY_NAMES = {
    "Market Analyst": "市场分析师",
    "Social Analyst": "社媒分析师",
    "News Analyst": "新闻分析师",
    "Fundamentals Analyst": "基本面分析师",
    "Bull Researcher": "看多研究员",
    "Bear Researcher": "看空研究员",
    "Research Manager": "研究经理",
    "Trader": "交易员",
    "Aggressive Analyst": "激进风控分析师",
    "Neutral Analyst": "中性风控分析师",
    "Conservative Analyst": "保守风控分析师",
    "Portfolio Manager": "组合经理",
}

ANALYST_KEY_DISPLAY_NAMES = {
    "market": "市场分析师",
    "social": "社媒分析师",
    "news": "新闻分析师",
    "fundamentals": "基本面分析师",
}


class ConfigurationError(RuntimeError):
    """Raised when desktop app configuration is incomplete."""


@dataclass
class DesktopSelection:
    ticker: str
    analysis_date: str
    output_language: str
    analysts: list[str]
    research_depth: int
    llm_provider: str
    backend_url: str
    shallow_thinker: str
    deep_thinker: str
    provider_api_key: str = ""
    alpha_vantage_api_key: str = ""
    google_thinking_level: str | None = None
    openai_reasoning_effort: str | None = None
    anthropic_effort: str | None = None


class DesktopMessageBuffer:
    FIXED_AGENTS = {
        "Research Team": ["Bull Researcher", "Bear Researcher", "Research Manager"],
        "Trading Team": ["Trader"],
        "Risk Management": ["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst"],
        "Portfolio Management": ["Portfolio Manager"],
    }

    ANALYST_MAPPING = {
        "market": "Market Analyst",
        "social": "Social Analyst",
        "news": "News Analyst",
        "fundamentals": "Fundamentals Analyst",
    }

    REPORT_SECTIONS = {
        "market_report": ("market", "Market Analyst"),
        "sentiment_report": ("social", "Social Analyst"),
        "news_report": ("news", "News Analyst"),
        "fundamentals_report": ("fundamentals", "Fundamentals Analyst"),
        "investment_plan": (None, "Research Manager"),
        "trader_investment_plan": (None, "Trader"),
        "final_trade_decision": (None, "Portfolio Manager"),
    }

    def __init__(self, max_length: int = 200):
        self.messages = deque(maxlen=max_length)
        self.tool_calls = deque(maxlen=max_length)
        self.current_report: str | None = None
        self.final_report: str | None = None
        self.agent_status: dict[str, str] = {}
        self.current_agent: str | None = None
        self.report_sections: dict[str, str | None] = {}
        self.selected_analysts: list[str] = []
        self._last_message_id = None
        self._latest_section: str | None = None

    def init_for_analysis(self, selected_analysts: list[str]) -> None:
        self.selected_analysts = [a.lower() for a in selected_analysts]
        self.agent_status = {}

        for analyst_key in self.selected_analysts:
            if analyst_key in self.ANALYST_MAPPING:
                self.agent_status[self.ANALYST_MAPPING[analyst_key]] = "pending"

        for team_agents in self.FIXED_AGENTS.values():
            for agent in team_agents:
                self.agent_status[agent] = "pending"

        self.report_sections = {}
        for section, (analyst_key, _) in self.REPORT_SECTIONS.items():
            if analyst_key is None or analyst_key in self.selected_analysts:
                self.report_sections[section] = None

        self.current_report = None
        self.final_report = None
        self.current_agent = None
        self.messages.clear()
        self.tool_calls.clear()
        self._last_message_id = None
        self._latest_section = None

    def add_message(self, message_type: str, content: str) -> tuple[str, str, str]:
        timestamp = dt.datetime.now().strftime("%H:%M:%S")
        entry = (timestamp, message_type, content)
        self.messages.append(entry)
        return entry

    def add_tool_call(self, tool_name: str, args: Any) -> tuple[str, str, Any]:
        timestamp = dt.datetime.now().strftime("%H:%M:%S")
        entry = (timestamp, tool_name, args)
        self.tool_calls.append(entry)
        return entry

    def update_agent_status(self, agent: str, status: str) -> None:
        if agent in self.agent_status:
            self.agent_status[agent] = status
            self.current_agent = agent

    def update_report_section(self, section_name: str, content: str) -> None:
        if section_name in self.report_sections:
            self.report_sections[section_name] = content
            self._latest_section = section_name
            self._update_current_report()

    def _update_current_report(self) -> None:
        latest_section = self._latest_section
        latest_content = (
            self.report_sections.get(latest_section) if latest_section else None
        )

        if latest_section and latest_content:
            section_titles = {
                "market_report": "市场分析",
                "sentiment_report": "社媒情绪",
                "news_report": "新闻分析",
                "fundamentals_report": "基本面分析",
                "investment_plan": "研究团队结论",
                "trader_investment_plan": "交易团队计划",
                "final_trade_decision": "组合管理决策",
            }
            self.current_report = f"### {section_titles[latest_section]}\n{latest_content}"

        self._update_final_report()

    def _update_final_report(self) -> None:
        report_parts = []

        analyst_sections = [
            "market_report",
            "sentiment_report",
            "news_report",
            "fundamentals_report",
        ]
        if any(self.report_sections.get(section) for section in analyst_sections):
            report_parts.append("## 分析师团队报告")
            if self.report_sections.get("market_report"):
                report_parts.append(
                    f"### 市场分析\n{self.report_sections['market_report']}"
                )
            if self.report_sections.get("sentiment_report"):
                report_parts.append(
                    f"### 社媒情绪\n{self.report_sections['sentiment_report']}"
                )
            if self.report_sections.get("news_report"):
                report_parts.append(
                    f"### 新闻分析\n{self.report_sections['news_report']}"
                )
            if self.report_sections.get("fundamentals_report"):
                report_parts.append(
                    f"### 基本面分析\n{self.report_sections['fundamentals_report']}"
                )

        if self.report_sections.get("investment_plan"):
            report_parts.append("## 研究团队结论")
            report_parts.append(f"{self.report_sections['investment_plan']}")

        if self.report_sections.get("trader_investment_plan"):
            report_parts.append("## 交易团队计划")
            report_parts.append(f"{self.report_sections['trader_investment_plan']}")

        if self.report_sections.get("final_trade_decision"):
            report_parts.append("## 组合管理决策")
            report_parts.append(f"{self.report_sections['final_trade_decision']}")

        self.final_report = "\n\n".join(report_parts) if report_parts else None


def extract_content_string(content: Any) -> str | None:
    import ast

    def is_empty(value: Any) -> bool:
        if value is None or value == "":
            return True
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return True
            try:
                return not bool(ast.literal_eval(stripped))
            except (ValueError, SyntaxError):
                return False
        return not bool(value)

    if is_empty(content):
        return None

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, dict):
        text = content.get("text", "")
        return text.strip() if not is_empty(text) else None

    if isinstance(content, list):
        parts = [
            item.get("text", "").strip()
            if isinstance(item, dict) and item.get("type") == "text"
            else (item.strip() if isinstance(item, str) else "")
            for item in content
        ]
        result = " ".join(part for part in parts if part and not is_empty(part))
        return result or None

    return str(content).strip() if not is_empty(content) else None


def classify_message_type(message: Any) -> tuple[str, str | None]:
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    content = extract_content_string(getattr(message, "content", None))

    if isinstance(message, HumanMessage):
        if content and content.strip() == "Continue":
            return ("控制", content)
        return ("用户", content)

    if isinstance(message, ToolMessage):
        return ("数据", content)

    if isinstance(message, AIMessage):
        return ("智能体", content)

    return ("系统", content)


def format_tool_args(args: Any, max_length: int = 120) -> str:
    result = str(args)
    if len(result) > max_length:
        return result[: max_length - 3] + "..."
    return result


def provider_env_var(provider: str) -> str | None:
    spec = PROVIDER_SPECS.get(provider.lower())
    if not spec:
        return None
    return spec["env_var"]


def ordered_analysts(analysts: list[str]) -> list[str]:
    selected = {analyst.lower() for analyst in analysts}
    return [analyst for analyst in ANALYST_SEQUENCE if analyst in selected]


def apply_environment(selection: DesktopSelection) -> None:
    load_dotenv()

    env_var = provider_env_var(selection.llm_provider)
    if env_var and selection.provider_api_key.strip():
        os.environ[env_var] = selection.provider_api_key.strip()

    if selection.alpha_vantage_api_key.strip():
        os.environ["ALPHA_VANTAGE_API_KEY"] = selection.alpha_vantage_api_key.strip()

    if env_var and not os.getenv(env_var):
        raise ConfigurationError(
            f"当前提供商 `{selection.llm_provider}` 缺少必填环境变量 `{env_var}`。"
        )


def desktop_storage_root() -> Path:
    override = os.getenv("TRADINGAGENTS_DESKTOP_HOME", "").strip()
    if override:
        return Path(override).expanduser()

    if os.name == "nt":
        base_dir = Path(
            os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
        )
        return base_dir / "TradingAgentsDesktop"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "TradingAgentsDesktop"

    xdg_home = os.getenv("XDG_DATA_HOME", "").strip()
    if xdg_home:
        return Path(xdg_home).expanduser() / "tradingagents-desktop"

    return Path.home() / ".local" / "share" / "tradingagents-desktop"


def build_config(selection: DesktopSelection) -> dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    storage_root = desktop_storage_root()
    results_root = storage_root / "results"
    cache_root = storage_root / "data_cache"

    storage_root.mkdir(parents=True, exist_ok=True)
    results_root.mkdir(parents=True, exist_ok=True)
    cache_root.mkdir(parents=True, exist_ok=True)

    config["project_dir"] = str(storage_root)
    config["results_dir"] = str(results_root)
    config["data_cache_dir"] = str(cache_root)
    config["max_debate_rounds"] = selection.research_depth
    config["max_risk_discuss_rounds"] = selection.research_depth
    config["quick_think_llm"] = selection.shallow_thinker
    config["deep_think_llm"] = selection.deep_thinker
    config["backend_url"] = selection.backend_url
    config["llm_provider"] = selection.llm_provider.lower()
    config["google_thinking_level"] = selection.google_thinking_level
    config["openai_reasoning_effort"] = selection.openai_reasoning_effort
    config["anthropic_effort"] = selection.anthropic_effort
    config["output_language"] = selection.output_language or "English"
    config["market_region"] = infer_market_region(selection.ticker)
    return config


def update_research_team_status(buffer: DesktopMessageBuffer, status: str) -> None:
    for agent in ["Bull Researcher", "Bear Researcher", "Research Manager"]:
        buffer.update_agent_status(agent, status)


def update_analyst_statuses(buffer: DesktopMessageBuffer, chunk: dict[str, Any]) -> None:
    selected = buffer.selected_analysts
    found_active = False

    for analyst_key in ANALYST_SEQUENCE:
        if analyst_key not in selected:
            continue

        agent_name = ANALYST_AGENT_NAMES[analyst_key]
        report_key = ANALYST_REPORT_MAP[analyst_key]

        if chunk.get(report_key):
            buffer.update_report_section(report_key, chunk[report_key])

        has_report = bool(buffer.report_sections.get(report_key))

        if has_report:
            buffer.update_agent_status(agent_name, "completed")
        elif not found_active:
            buffer.update_agent_status(agent_name, "in_progress")
            found_active = True
        else:
            buffer.update_agent_status(agent_name, "pending")

    if not found_active and selected and buffer.agent_status.get("Bull Researcher") == "pending":
        buffer.update_agent_status("Bull Researcher", "in_progress")


def save_report_to_disk(final_state: dict[str, Any], ticker: str, save_path: Path) -> Path:
    save_path.mkdir(parents=True, exist_ok=True)
    sections: list[str] = []

    analysts_dir = save_path / "1_analysts"
    analyst_parts = []
    if final_state.get("market_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "market.md").write_text(final_state["market_report"], encoding="utf-8")
        analyst_parts.append(("市场分析师", final_state["market_report"]))
    if final_state.get("sentiment_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "sentiment.md").write_text(final_state["sentiment_report"], encoding="utf-8")
        analyst_parts.append(("社媒分析师", final_state["sentiment_report"]))
    if final_state.get("news_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "news.md").write_text(final_state["news_report"], encoding="utf-8")
        analyst_parts.append(("新闻分析师", final_state["news_report"]))
    if final_state.get("fundamentals_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "fundamentals.md").write_text(final_state["fundamentals_report"], encoding="utf-8")
        analyst_parts.append(("基本面分析师", final_state["fundamentals_report"]))
    if analyst_parts:
        content = "\n\n".join(f"### {name}\n{text}" for name, text in analyst_parts)
        sections.append(f"## 一、分析师团队报告\n\n{content}")

    if final_state.get("investment_debate_state"):
        research_dir = save_path / "2_research"
        debate = final_state["investment_debate_state"]
        research_parts = []
        if debate.get("bull_history"):
            research_dir.mkdir(exist_ok=True)
            (research_dir / "bull.md").write_text(debate["bull_history"], encoding="utf-8")
            research_parts.append(("看多研究员", debate["bull_history"]))
        if debate.get("bear_history"):
            research_dir.mkdir(exist_ok=True)
            (research_dir / "bear.md").write_text(debate["bear_history"], encoding="utf-8")
            research_parts.append(("看空研究员", debate["bear_history"]))
        if debate.get("judge_decision"):
            research_dir.mkdir(exist_ok=True)
            (research_dir / "manager.md").write_text(debate["judge_decision"], encoding="utf-8")
            research_parts.append(("研究经理", debate["judge_decision"]))
        if research_parts:
            content = "\n\n".join(f"### {name}\n{text}" for name, text in research_parts)
            sections.append(f"## 二、研究团队结论\n\n{content}")

    if final_state.get("trader_investment_plan"):
        trading_dir = save_path / "3_trading"
        trading_dir.mkdir(exist_ok=True)
        (trading_dir / "trader.md").write_text(final_state["trader_investment_plan"], encoding="utf-8")
        sections.append(
            "## 三、交易团队计划\n\n"
            f"### 交易员\n{final_state['trader_investment_plan']}"
        )

    if final_state.get("risk_debate_state"):
        risk_dir = save_path / "4_risk"
        risk = final_state["risk_debate_state"]
        risk_parts = []
        if risk.get("aggressive_history"):
            risk_dir.mkdir(exist_ok=True)
            (risk_dir / "aggressive.md").write_text(risk["aggressive_history"], encoding="utf-8")
            risk_parts.append(("激进风控分析师", risk["aggressive_history"]))
        if risk.get("conservative_history"):
            risk_dir.mkdir(exist_ok=True)
            (risk_dir / "conservative.md").write_text(risk["conservative_history"], encoding="utf-8")
            risk_parts.append(("保守风控分析师", risk["conservative_history"]))
        if risk.get("neutral_history"):
            risk_dir.mkdir(exist_ok=True)
            (risk_dir / "neutral.md").write_text(risk["neutral_history"], encoding="utf-8")
            risk_parts.append(("中性风控分析师", risk["neutral_history"]))
        if risk_parts:
            content = "\n\n".join(f"### {name}\n{text}" for name, text in risk_parts)
            sections.append(f"## 四、风控团队结论\n\n{content}")

        if risk.get("judge_decision"):
            portfolio_dir = save_path / "5_portfolio"
            portfolio_dir.mkdir(exist_ok=True)
            (portfolio_dir / "decision.md").write_text(risk["judge_decision"], encoding="utf-8")
            sections.append(
                "## 五、组合管理决策\n\n"
                f"### 组合经理\n{risk['judge_decision']}"
            )

    header = (
        f"# 交易分析报告：{ticker}\n\n"
        f"生成时间：{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    report_file = save_path / "complete_report.md"
    report_file.write_text(header + "\n\n".join(sections), encoding="utf-8")
    return report_file


class DesktopAnalysisRunner:
    def __init__(
        self,
        selection: DesktopSelection,
        on_log: Callable[[str], None] | None = None,
        on_status: Callable[[dict[str, str]], None] | None = None,
        on_reports: Callable[[str, str], None] | None = None,
        on_stats: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.selection = selection
        self.on_log = on_log or (lambda *_: None)
        self.on_status = on_status or (lambda *_: None)
        self.on_reports = on_reports or (lambda *_: None)
        self.on_stats = on_stats or (lambda *_: None)
        self._log_file: Path | None = None

    def _emit_log(self, message: str) -> None:
        self.on_log(message)
        if self._log_file is not None:
            with self._log_file.open("a", encoding="utf-8") as handle:
                handle.write(message + "\n")

    def _emit_snapshot(
        self,
        buffer: DesktopMessageBuffer,
        stats_handler: StatsCallbackHandler,
    ) -> None:
        self.on_status(buffer.agent_status.copy())
        self.on_reports(buffer.current_report or "", buffer.final_report or "")
        self.on_stats(stats_handler.get_stats())

    def run(self) -> dict[str, Any]:
        if not self.selection.ticker.strip():
            raise ConfigurationError("请输入要分析的股票代码。")

        selected_analysts = ordered_analysts(self.selection.analysts)
        if not selected_analysts:
            raise ConfigurationError("请至少选择一个分析师。")

        apply_environment(self.selection)
        config = build_config(self.selection)

        stats_handler = StatsCallbackHandler()
        graph = TradingAgentsGraph(
            selected_analysts,
            config=config,
            debug=True,
            callbacks=[stats_handler],
        )

        buffer = DesktopMessageBuffer()
        buffer.init_for_analysis(selected_analysts)

        base_results = Path(config["results_dir"])
        if not base_results.is_absolute():
            base_results = Path.cwd() / base_results
        results_dir = base_results / self.selection.ticker / self.selection.analysis_date
        report_dir = results_dir / "desktop_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = results_dir / "desktop_activity.log"
        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        self._log_file.touch(exist_ok=True)

        self._emit_log(f"系统 · 股票代码：{self.selection.ticker}")
        self._emit_log(f"系统 · 分析日期：{self.selection.analysis_date}")
        self._emit_log(
            "系统 · 已选分析师："
            + "、".join(ANALYST_KEY_DISPLAY_NAMES[a] for a in selected_analysts)
        )

        first_analyst = ANALYST_AGENT_NAMES[selected_analysts[0]]
        buffer.update_agent_status(first_analyst, "in_progress")
        self._emit_snapshot(buffer, stats_handler)

        init_state = graph.propagator.create_initial_state(
            self.selection.ticker,
            self.selection.analysis_date,
        )
        args = graph.propagator.get_graph_args(callbacks=[stats_handler])

        trace = []
        for chunk in graph.graph.stream(init_state, **args):
            if len(chunk["messages"]) > 0:
                last_message = chunk["messages"][-1]
                msg_id = getattr(last_message, "id", None)

                if msg_id != buffer._last_message_id:
                    buffer._last_message_id = msg_id
                    msg_type, content = classify_message_type(last_message)
                    if content and content.strip():
                        timestamp, _, _ = buffer.add_message(msg_type, content)
                        self._emit_log(f"{timestamp} [{msg_type}] {content}")

                    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                        for tool_call in last_message.tool_calls:
                            if isinstance(tool_call, dict):
                                tool_name = tool_call["name"]
                                tool_args = tool_call["args"]
                            else:
                                tool_name = tool_call.name
                                tool_args = tool_call.args
                            timestamp, _, _ = buffer.add_tool_call(tool_name, tool_args)
                            self._emit_log(
                                f"{timestamp} [工具] {tool_name}({format_tool_args(tool_args)})"
                            )

            update_analyst_statuses(buffer, chunk)

            if chunk.get("investment_debate_state"):
                debate_state = chunk["investment_debate_state"]
                bull_hist = debate_state.get("bull_history", "").strip()
                bear_hist = debate_state.get("bear_history", "").strip()
                judge = debate_state.get("judge_decision", "").strip()

                if bull_hist or bear_hist:
                    update_research_team_status(buffer, "in_progress")
                if bull_hist:
                    buffer.update_report_section(
                        "investment_plan",
                        f"### 看多研究员观点\n{bull_hist}",
                    )
                if bear_hist:
                    buffer.update_report_section(
                        "investment_plan",
                        f"### 看空研究员观点\n{bear_hist}",
                    )
                if judge:
                    buffer.update_report_section(
                        "investment_plan",
                        f"### 研究经理结论\n{judge}",
                    )
                    update_research_team_status(buffer, "completed")
                    buffer.update_agent_status("Trader", "in_progress")

            if chunk.get("trader_investment_plan"):
                buffer.update_report_section(
                    "trader_investment_plan",
                    chunk["trader_investment_plan"],
                )
                if buffer.agent_status.get("Trader") != "completed":
                    buffer.update_agent_status("Trader", "completed")
                    buffer.update_agent_status("Aggressive Analyst", "in_progress")

            if chunk.get("risk_debate_state"):
                risk_state = chunk["risk_debate_state"]
                agg_hist = risk_state.get("aggressive_history", "").strip()
                con_hist = risk_state.get("conservative_history", "").strip()
                neu_hist = risk_state.get("neutral_history", "").strip()
                judge = risk_state.get("judge_decision", "").strip()

                if agg_hist:
                    if buffer.agent_status.get("Aggressive Analyst") != "completed":
                        buffer.update_agent_status("Aggressive Analyst", "in_progress")
                    buffer.update_report_section(
                        "final_trade_decision",
                        f"### 激进风控分析师观点\n{agg_hist}",
                    )
                if con_hist:
                    if buffer.agent_status.get("Conservative Analyst") != "completed":
                        buffer.update_agent_status("Conservative Analyst", "in_progress")
                    buffer.update_report_section(
                        "final_trade_decision",
                        f"### 保守风控分析师观点\n{con_hist}",
                    )
                if neu_hist:
                    if buffer.agent_status.get("Neutral Analyst") != "completed":
                        buffer.update_agent_status("Neutral Analyst", "in_progress")
                    buffer.update_report_section(
                        "final_trade_decision",
                        f"### 中性风控分析师观点\n{neu_hist}",
                    )
                if judge and buffer.agent_status.get("Portfolio Manager") != "completed":
                    buffer.update_agent_status("Portfolio Manager", "in_progress")
                    buffer.update_report_section(
                        "final_trade_decision",
                        f"### 组合经理决策\n{judge}",
                    )
                    buffer.update_agent_status("Aggressive Analyst", "completed")
                    buffer.update_agent_status("Conservative Analyst", "completed")
                    buffer.update_agent_status("Neutral Analyst", "completed")
                    buffer.update_agent_status("Portfolio Manager", "completed")

            self._emit_snapshot(buffer, stats_handler)
            trace.append(chunk)

        if not trace:
            raise RuntimeError("分析流程结束了，但没有生成任何输出。")

        final_state = trace[-1]
        decision = graph.process_signal(final_state["final_trade_decision"])

        for agent in list(buffer.agent_status):
            buffer.update_agent_status(agent, "completed")

        timestamp, _, _ = buffer.add_message(
            "系统",
            f"{self.selection.analysis_date} 的分析已完成",
        )
        self._emit_log(f"{timestamp} [系统] {self.selection.analysis_date} 的分析已完成")

        for section in list(buffer.report_sections.keys()):
            if section in final_state:
                buffer.update_report_section(section, final_state[section])

        report_file = save_report_to_disk(final_state, self.selection.ticker, report_dir)
        self._emit_log(f"系统 · 报告已保存到：{report_file}")
        self._emit_snapshot(buffer, stats_handler)

        return {
            "decision": decision,
            "results_dir": str(results_dir.resolve()),
            "report_path": str(report_file.resolve()),
            "final_report": buffer.final_report or "",
            "current_report": buffer.current_report or "",
            "stats": stats_handler.get_stats(),
        }
