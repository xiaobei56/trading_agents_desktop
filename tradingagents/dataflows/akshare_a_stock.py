from __future__ import annotations

import contextlib
import io
import re
from datetime import datetime, timedelta
from typing import Callable

import akshare as ak
import pandas as pd

from tradingagents.ticker_utils import (
    to_mainland_stock_code,
    normalize_ticker_symbol,
)

_CHINA_TOPIC_SUFFIXES = (
    "板块",
    "概念",
    "概念股",
    "行业",
    "赛道",
    "题材",
    "产业链",
    "指数",
)


def _call_akshare(func: Callable, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return func(*args, **kwargs)


def _format_table(df: pd.DataFrame, max_rows: int = 12) -> str:
    if df.empty:
        return "No data found."

    preview = df.head(max_rows).copy()
    preview = preview.fillna("")
    return preview.to_markdown(index=False)


def _pick_existing_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    existing = [col for col in columns if col in df.columns]
    return df[existing].copy() if existing else df.copy()


def _filter_report_date(df: pd.DataFrame, curr_date: str | None) -> pd.DataFrame:
    if df.empty or not curr_date or "REPORT_DATE" not in df.columns:
        return df

    cutoff = pd.Timestamp(curr_date)
    report_dates = pd.to_datetime(df["REPORT_DATE"], errors="coerce")
    filtered = df.loc[report_dates <= cutoff].copy()
    return filtered if not filtered.empty else df


def _filter_annual_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "REPORT_DATE" not in df.columns:
        return df

    report_dates = pd.to_datetime(df["REPORT_DATE"], errors="coerce")
    annual = df.loc[(report_dates.dt.month == 12) & (report_dates.dt.day == 31)].copy()
    return annual if not annual.empty else df


def _filter_cn_report_day(df: pd.DataFrame, curr_date: str | None, column: str = "报告日") -> pd.DataFrame:
    if df.empty or not curr_date or column not in df.columns:
        return df

    report_dates = pd.to_datetime(df[column], format="%Y%m%d", errors="coerce")
    filtered = df.loc[report_dates <= pd.Timestamp(curr_date)].copy()
    return filtered if not filtered.empty else df


def _filter_cn_annual_rows(df: pd.DataFrame, column: str = "报告日") -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return df

    report_dates = pd.to_datetime(df[column], format="%Y%m%d", errors="coerce")
    annual = df.loc[(report_dates.dt.month == 12) & (report_dates.dt.day == 31)].copy()
    return annual if not annual.empty else df


def _to_prefixed_symbol(ticker: str) -> str:
    normalized = normalize_ticker_symbol(ticker)
    match = re.fullmatch(r"(\d{6})\.(SS|SZ|BJ)", normalized)
    if not match:
        return ""
    code, suffix = match.groups()
    prefix = {"SS": "sh", "SZ": "sz", "BJ": "bj"}[suffix]
    return f"{prefix}{code}"


def _filter_rows_by_keywords(df: pd.DataFrame, keywords: list[str]) -> pd.DataFrame:
    if df.empty or not keywords:
        return df.iloc[0:0].copy()

    pattern = "|".join(re.escape(keyword) for keyword in keywords)
    mask = df.astype(str).apply(
        lambda column: column.str.contains(pattern, na=False, regex=True)
    )
    return df.loc[mask.any(axis=1)].copy()


def _build_china_query_keywords(query: str) -> list[str]:
    compact = re.sub(r"\s+", "", str(query or "")).strip()
    if not compact:
        return []

    variants = [compact]
    trimmed = compact
    changed = True
    while changed and trimmed:
        changed = False
        for suffix in _CHINA_TOPIC_SUFFIXES:
            if trimmed.endswith(suffix) and len(trimmed) > len(suffix):
                trimmed = trimmed[: -len(suffix)]
                variants.append(trimmed)
                changed = True
                break

    if trimmed.endswith("股") and len(trimmed) > 1:
        variants.append(trimmed[:-1])

    seen: set[str] = set()
    keywords: list[str] = []
    for item in variants:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        keywords.append(normalized)

    return keywords


def _looks_like_china_keyword_query(query: str) -> bool:
    compact = re.sub(r"\s+", "", str(query or "")).strip()
    if not compact:
        return False
    if re.search(r"[\u3400-\u4DBF\u4E00-\u9FFF]", compact):
        return True
    return any(compact.endswith(suffix) for suffix in _CHINA_TOPIC_SUFFIXES)


def get_stock_data_akshare(symbol: str, start_date: str, end_date: str) -> str:
    code = to_mainland_stock_code(symbol)
    if not code:
        raise ValueError(f"Unsupported mainland China ticker or stock name: {symbol}")

    start_fmt = datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y%m%d")
    end_fmt = datetime.strptime(end_date, "%Y-%m-%d").strftime("%Y%m%d")
    df = _call_akshare(
        ak.stock_zh_a_hist_tx,
        symbol=_to_prefixed_symbol(symbol),
        start_date=start_fmt,
        end_date=end_fmt,
        adjust="qfq",
    )

    if df.empty:
        return f"No A-share market data found for '{symbol}' between {start_date} and {end_date}"

    df = df.rename(
        columns={
            "date": "Date",
            "open": "Open",
            "close": "Close",
            "high": "High",
            "low": "Low",
            "amount": "Volume",
        }
    )
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    df["Adj Close"] = df["Close"]

    header = f"# A-share stock data for {symbol} from {start_date} to {end_date}\n"
    header += f"# Source: AkShare / Tencent Securities\n"
    header += f"# Total records: {len(df)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    return header + df.to_csv(index=False)


def get_news_akshare(ticker: str, start_date: str, end_date: str) -> str:
    code = to_mainland_stock_code(ticker)
    if code:
        return _get_stock_news_akshare(ticker, code, start_date, end_date)

    if _looks_like_china_keyword_query(ticker):
        return _get_targeted_china_news_akshare(ticker, start_date, end_date)

    raise ValueError(f"Unsupported mainland China ticker or stock name: {ticker}")


def _get_stock_news_akshare(ticker: str, code: str, start_date: str, end_date: str) -> str:
    df = _call_akshare(ak.stock_news_em, symbol=code)
    if df.empty:
        return f"No A-share news found for {ticker}"

    df["发布时间"] = pd.to_datetime(df["发布时间"], errors="coerce")
    start_dt = pd.Timestamp(start_date)
    end_dt = pd.Timestamp(end_date) + pd.Timedelta(days=1)
    df = df.loc[(df["发布时间"] >= start_dt) & (df["发布时间"] < end_dt)].copy()
    if df.empty:
        return f"No A-share news found for {ticker} between {start_date} and {end_date}"

    parts = []
    for _, row in df.head(20).iterrows():
        published = row.get("发布时间")
        published_text = published.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(published) else ""
        parts.append(
            f"### {row.get('新闻标题', 'No title')} (来源: {row.get('文章来源', '东方财富')}, 时间: {published_text})\n"
            f"{row.get('新闻内容', '')}\n"
            f"链接: {row.get('新闻链接', '')}\n"
        )

    return f"## {ticker} A-share news, from {start_date} to {end_date}:\n\n" + "\n".join(parts)


def _get_targeted_china_news_akshare(query: str, start_date: str, end_date: str) -> str:
    keywords = _build_china_query_keywords(query)
    if not keywords:
        return (
            f"No China-focused targeted news found for {query} "
            f"between {start_date} and {end_date}"
        )

    sections: list[str] = []

    board_changes = _call_akshare(ak.stock_board_change_em)
    board_changes = _filter_rows_by_keywords(board_changes, keywords)
    if not board_changes.empty:
        preview = _pick_existing_columns(
            board_changes,
            [
                "板块名称",
                "涨跌幅",
                "主力净流入",
                "板块异动总次数",
                "板块异动最频繁个股及所属类型-股票名称",
                "板块异动最频繁个股及所属类型-买卖方向",
            ],
        )
        sections.append("## 中国板块异动快照\n\n" + _format_table(preview, max_rows=8))

    market_news = _call_akshare(ak.stock_news_main_cx)
    if not market_news.empty:
        market_news = market_news.copy()
        extracted_dates = market_news["url"].astype(str).str.extract(r"/(\d{4}-\d{2}-\d{2})/")
        market_news["date"] = pd.to_datetime(extracted_dates[0], errors="coerce")
        start_dt = pd.Timestamp(start_date)
        end_dt = pd.Timestamp(end_date)
        market_news = market_news.loc[
            (market_news["date"] >= start_dt) & (market_news["date"] <= end_dt)
        ].copy()
        market_news = _filter_rows_by_keywords(market_news, keywords)

    if not market_news.empty:
        rows = []
        for _, row in market_news.head(12).iterrows():
            date_value = row.get("date")
            date_text = date_value.strftime("%Y-%m-%d") if pd.notna(date_value) else "未知日期"
            rows.append(
                f"### {row.get('tag', '市场动态')} · {date_text}\n"
                f"{row.get('summary', '')}\n"
                f"链接: {row.get('url', '')}\n"
            )
        sections.append("## 关键词相关新闻\n\n" + "\n".join(rows))

    if not sections:
        return (
            f"No China-focused targeted news found for {query} "
            f"between {start_date} and {end_date}"
        )

    return (
        f"## {query} China-focused targeted news, from {start_date} to {end_date}:\n\n"
        + "\n\n".join(sections)
    )


def get_global_news_akshare(curr_date: str, look_back_days: int = 7, limit: int = 10) -> str:
    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_dt = curr_dt - timedelta(days=look_back_days)

    market_news = _call_akshare(ak.stock_news_main_cx)
    if not market_news.empty:
        extracted_dates = market_news["url"].astype(str).str.extract(r"/(\d{4}-\d{2}-\d{2})/")
        market_news["date"] = pd.to_datetime(extracted_dates[0], errors="coerce")
        market_news = market_news.loc[
            (market_news["date"] >= pd.Timestamp(start_dt.date()))
            & (market_news["date"] <= pd.Timestamp(curr_dt.date()))
        ].copy()

    macro_frames = []
    for offset in range(min(look_back_days + 1, 5)):
        target = curr_dt - timedelta(days=offset)
        try:
            frame = _call_akshare(ak.news_economic_baidu, date=target.strftime("%Y%m%d"))
        except Exception:
            continue
        if frame.empty:
            continue
        macro_frames.append(frame)

    macro_df = pd.concat(macro_frames, ignore_index=True) if macro_frames else pd.DataFrame()
    macro_section = ""
    if not macro_df.empty:
        macro_df["日期"] = pd.to_datetime(macro_df["日期"], errors="coerce")
        macro_df = macro_df.sort_values(["日期", "时间", "重要性"], ascending=[False, False, False])
        macro_df = macro_df.head(limit)
        macro_section = (
            "## 中国宏观日历与财经事件\n\n"
            + _format_table(macro_df[["日期", "时间", "地区", "事件", "公布", "预期", "前值", "重要性"]], max_rows=limit)
        )

    market_section = ""
    if not market_news.empty:
        rows = []
        for _, row in market_news.head(limit).iterrows():
            date_text = row["date"].strftime("%Y-%m-%d") if pd.notna(row["date"]) else "未知日期"
            rows.append(
                f"### {row.get('tag', '市场动态')} · {date_text}\n"
                f"{row.get('summary', '')}\n"
                f"链接: {row.get('url', '')}\n"
            )
        market_section = "## 中国市场头条\n\n" + "\n".join(rows)

    if not macro_section and not market_section:
        return f"No China-focused macro or market news found for {curr_date}"

    return "\n\n".join([section for section in [market_section, macro_section] if section])


def get_fundamentals_akshare(ticker: str, curr_date: str | None = None) -> str:
    code = to_mainland_stock_code(ticker)
    if not code:
        raise ValueError(f"Unsupported mainland China ticker or stock name: {ticker}")

    abstract_df = _call_akshare(ak.stock_financial_abstract, symbol=code)

    sections = [f"# A-share fundamentals for {ticker}", "## 关键指标（新浪财经）"]
    if not abstract_df.empty:
        report_columns = [col for col in abstract_df.columns if col.isdigit()]
        selected_reports = []
        if curr_date:
            cutoff = pd.Timestamp(curr_date)
            selected_reports = [
                col for col in report_columns
                if pd.to_datetime(col, format="%Y%m%d", errors="coerce") <= cutoff
            ]
        if not selected_reports:
            selected_reports = report_columns
        selected_reports = selected_reports[:4]
        preview_df = abstract_df[["选项", "指标", *selected_reports]].head(14).copy()
        sections.append(_format_table(preview_df, max_rows=14))
    else:
        sections.append("No A-share fundamentals data found.")

    try:
        important_df = _call_akshare(ak.stock_financial_abstract_new_ths, symbol=code, indicator="按报告期")
        if not important_df.empty:
            if curr_date:
                report_dates = pd.to_datetime(important_df["报告期"], errors="coerce")
                filtered = important_df.loc[report_dates <= pd.Timestamp(curr_date)].copy()
                if not filtered.empty:
                    important_df = filtered
            sections.extend(
                [
                    "## 重要指标（同花顺）",
                    _format_table(important_df.head(8), max_rows=8),
                ]
            )
    except Exception:
        pass

    return "\n\n".join(sections)


def get_balance_sheet_akshare(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str:
    prefixed_symbol = _to_prefixed_symbol(ticker)
    if not prefixed_symbol:
        raise ValueError(f"Unsupported mainland China ticker or stock name: {ticker}")

    df = _call_akshare(ak.stock_financial_report_sina, stock=prefixed_symbol, symbol="资产负债表")
    df = _filter_cn_report_day(df, curr_date)
    if freq.lower() == "annual":
        df = _filter_cn_annual_rows(df)
    preview = _pick_existing_columns(
        df,
        [
            "报告日",
            "货币资金",
            "应收票据及应收账款",
            "存货",
            "流动资产合计",
            "固定资产及清理合计",
            "无形资产",
            "非流动资产合计",
            "资产总计",
            "应付票据及应付账款",
            "合同负债",
            "应交税费",
            "流动负债合计",
            "负债合计",
            "归属于母公司股东权益合计",
            "所有者权益(或股东权益)合计",
            "负债和所有者权益(或股东权益)总计",
        ],
    )
    return f"# Balance Sheet for {ticker} ({freq})\n\n" + _format_table(preview, max_rows=8)


def get_cashflow_akshare(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str:
    prefixed_symbol = _to_prefixed_symbol(ticker)
    if not prefixed_symbol:
        raise ValueError(f"Unsupported mainland China ticker or stock name: {ticker}")

    df = _call_akshare(ak.stock_financial_report_sina, stock=prefixed_symbol, symbol="现金流量表")
    df = _filter_cn_report_day(df, curr_date)
    if freq.lower() == "annual":
        df = _filter_cn_annual_rows(df)
    preview = _pick_existing_columns(
        df,
        [
            "报告日",
            "销售商品、提供劳务收到的现金",
            "经营活动现金流入小计",
            "购买商品、接受劳务支付的现金",
            "支付给职工以及为职工支付的现金",
            "支付的各项税费",
            "经营活动现金流出小计",
            "经营活动产生的现金流量净额",
            "投资活动现金流入小计",
            "投资活动现金流出小计",
            "投资活动产生的现金流量净额",
            "筹资活动现金流入小计",
            "筹资活动现金流出小计",
            "筹资活动产生的现金流量净额",
            "现金及现金等价物净增加额",
            "期末现金及现金等价物余额",
        ],
    )
    return f"# Cash Flow for {ticker} ({freq})\n\n" + _format_table(preview, max_rows=8)


def get_income_statement_akshare(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str:
    prefixed_symbol = _to_prefixed_symbol(ticker)
    if not prefixed_symbol:
        raise ValueError(f"Unsupported mainland China ticker or stock name: {ticker}")

    df = _call_akshare(ak.stock_financial_report_sina, stock=prefixed_symbol, symbol="利润表")
    df = _filter_cn_report_day(df, curr_date)
    if freq.lower() == "annual":
        df = _filter_cn_annual_rows(df)
    preview = _pick_existing_columns(
        df,
        [
            "报告日",
            "营业总收入",
            "营业总成本",
            "营业成本",
            "营业税金及附加",
            "销售费用",
            "管理费用",
            "财务费用",
            "营业利润",
            "利润总额",
            "所得税费用",
            "净利润",
            "归属于母公司所有者的净利润",
            "基本每股收益",
            "稀释每股收益",
        ],
    )
    return f"# Income Statement for {ticker} ({freq})\n\n" + _format_table(preview, max_rows=8)


def get_insider_transactions_akshare(ticker: str) -> str:
    code = to_mainland_stock_code(ticker)
    if not code:
        raise ValueError(f"Unsupported mainland China ticker or stock name: {ticker}")

    news_df = _call_akshare(ak.stock_news_em, symbol=code)
    filtered = news_df[
        news_df["新闻标题"].astype(str).str.contains("增持|减持|回购|股东|董监高", regex=True, na=False)
        | news_df["新闻内容"].astype(str).str.contains("增持|减持|回购|股东|董监高", regex=True, na=False)
    ].copy()

    if filtered.empty:
        return (
            f"No recent management/shareholder change items were found for {ticker} from Eastmoney news. "
            "For A-shares, insider-like activity is usually disclosed through shareholder reduction/increase, "
            "repurchase, and exchange announcements rather than a unified US-style insider feed."
        )

    parts = []
    for _, row in filtered.head(10).iterrows():
        parts.append(
            f"### {row.get('新闻标题', 'No title')} (来源: {row.get('文章来源', '东方财富')}, 时间: {row.get('发布时间', '')})\n"
            f"{row.get('新闻内容', '')}\n"
            f"链接: {row.get('新闻链接', '')}\n"
        )
    return "## A-share management/shareholder activity clues\n\n" + "\n".join(parts)
