from langchain_core.messages import ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_income_statement,
    get_insider_transactions,
    get_language_instruction,
)
from tradingagents.dataflows.config import get_config


FAILURE_MARKERS = (
    "无法从当前数据源获取信息",
    "无法获取具体的财务数据",
    "数据缺失",
    "手动验证",
    "官方渠道获取财务数据",
    "no fundamentals data found",
    "error retrieving fundamentals",
    "unable to retrieve",
    "failed to retrieve",
)


def _report_indicates_missing_data(report: str) -> bool:
    lowered = (report or "").strip().lower()
    return any(marker in lowered for marker in FAILURE_MARKERS)


def _tool_output_has_substance(content: str) -> bool:
    text = (content or "").strip()
    if not text:
        return False

    lowered = text.lower()
    if lowered.startswith("no ") or lowered.startswith("error retrieving"):
        return False
    if "无法从当前数据源获取信息" in text or "数据缺失" in text:
        return False

    return "|" in text or len(text) > 200


def _extract_fundamental_tool_outputs(messages) -> dict[str, str]:
    outputs: dict[str, str] = {}
    name_map = {
        "get_fundamentals": "fundamentals",
        "get_balance_sheet": "balance_sheet",
        "get_cashflow": "cashflow",
        "get_income_statement": "income_statement",
    }
    header_map = {
        "# a-share fundamentals": "fundamentals",
        "# company fundamentals": "fundamentals",
        "# balance sheet": "balance_sheet",
        "# cash flow": "cashflow",
        "# income statement": "income_statement",
    }

    for message in messages:
        content = getattr(message, "content", "")
        text = content if isinstance(content, str) else str(content)
        if not _tool_output_has_substance(text):
            continue

        tool_name = getattr(message, "name", "") or ""
        normalized_name = name_map.get(tool_name)
        if isinstance(message, ToolMessage) and normalized_name:
            outputs.setdefault(normalized_name, text)
            continue

        lowered = text.lower()
        for header, section_name in header_map.items():
            if header in lowered:
                outputs.setdefault(section_name, text)
                break

    return outputs


def _build_fallback_fundamentals_report(messages, ticker: str) -> str | None:
    tool_outputs = _extract_fundamental_tool_outputs(messages)
    if not tool_outputs:
        return None

    output_language = get_config().get("output_language", "English").strip().lower()
    if output_language == "chinese":
        intro = (
            f"## 基本面数据汇总\n\n"
            f"已从当前数据源获取 `{ticker}` 的原始基本面数据。"
            "下列内容基于工具返回结果整理，可直接作为后续研究与决策参考。\n"
        )
        titles = {
            "fundamentals": "综合指标",
            "balance_sheet": "资产负债表",
            "cashflow": "现金流量表",
            "income_statement": "利润表",
        }
    else:
        intro = (
            f"## Fundamentals Data Summary\n\n"
            f"Raw fundamentals data for `{ticker}` was retrieved successfully from the configured tools. "
            "The sections below are compiled directly from tool outputs for downstream analysis.\n"
        )
        titles = {
            "fundamentals": "Overview Metrics",
            "balance_sheet": "Balance Sheet",
            "cashflow": "Cash Flow",
            "income_statement": "Income Statement",
        }

    ordered_sections = ["fundamentals", "balance_sheet", "cashflow", "income_statement"]
    sections = [intro]
    for section_name in ordered_sections:
        content = tool_outputs.get(section_name)
        if content:
            sections.append(f"### {titles[section_name]}\n\n{content}")

    return "\n\n".join(sections)


def _fetch_direct_fundamental_tool_outputs(ticker: str, curr_date: str) -> dict[str, str]:
    tool_invocations = [
        ("fundamentals", get_fundamentals, {"ticker": ticker, "curr_date": curr_date}),
        (
            "balance_sheet",
            get_balance_sheet,
            {"ticker": ticker, "freq": "quarterly", "curr_date": curr_date},
        ),
        (
            "cashflow",
            get_cashflow,
            {"ticker": ticker, "freq": "quarterly", "curr_date": curr_date},
        ),
        (
            "income_statement",
            get_income_statement,
            {"ticker": ticker, "freq": "quarterly", "curr_date": curr_date},
        ),
    ]

    outputs: dict[str, str] = {}
    for section_name, tool, payload in tool_invocations:
        try:
            content = tool.invoke(payload)
        except Exception:
            continue

        text = content if isinstance(content, str) else str(content)
        if _tool_output_has_substance(text):
            outputs[section_name] = text

    return outputs


def _build_fallback_report_from_outputs(
    tool_outputs: dict[str, str],
    ticker: str,
) -> str | None:
    if not tool_outputs:
        return None

    synthetic_messages = []
    tool_name_map = {
        "fundamentals": "get_fundamentals",
        "balance_sheet": "get_balance_sheet",
        "cashflow": "get_cashflow",
        "income_statement": "get_income_statement",
    }
    for idx, (section_name, content) in enumerate(tool_outputs.items(), start=1):
        synthetic_messages.append(
            ToolMessage(
                content=content,
                tool_call_id=str(idx),
                name=tool_name_map[section_name],
            )
        )
    return _build_fallback_fundamentals_report(synthetic_messages, ticker)


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
        ]

        system_message = (
            "You are a researcher tasked with analyzing fundamental information over the past week about a company. Please write a comprehensive report of the company's fundamental information such as financial documents, company profile, basic company financials, and company financial history to gain a full view of the company's fundamental information to inform traders. Make sure to include as much detail as possible. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
            + " Use the available tools: `get_fundamentals` for comprehensive company analysis, `get_balance_sheet`, `get_cashflow`, and `get_income_statement` for specific financial statements."
            + get_language_instruction(),
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content if isinstance(result.content, str) else str(result.content)

            if not report.strip() or _report_indicates_missing_data(report):
                fallback_report = _build_fallback_fundamentals_report(
                    state["messages"],
                    state["company_of_interest"],
                )
                if fallback_report:
                    report = fallback_report
                else:
                    direct_outputs = _fetch_direct_fundamental_tool_outputs(
                        state["company_of_interest"],
                        current_date,
                    )
                    direct_report = _build_fallback_report_from_outputs(
                        direct_outputs,
                        state["company_of_interest"],
                    )
                    if direct_report:
                        report = direct_report

        return {
            "messages": [result],
            "fundamentals_report": report,
        }

    return fundamentals_analyst_node
