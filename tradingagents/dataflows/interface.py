from typing import Annotated

# Import from vendor-specific modules
from .y_finance import (
    get_YFin_data_online,
    get_stock_stats_indicators_window,
    get_fundamentals as get_yfinance_fundamentals,
    get_balance_sheet as get_yfinance_balance_sheet,
    get_cashflow as get_yfinance_cashflow,
    get_income_statement as get_yfinance_income_statement,
    get_insider_transactions as get_yfinance_insider_transactions,
)
from .yfinance_news import get_news_yfinance, get_global_news_yfinance
from .alpha_vantage import (
    get_stock as get_alpha_vantage_stock,
    get_indicator as get_alpha_vantage_indicator,
    get_fundamentals as get_alpha_vantage_fundamentals,
    get_balance_sheet as get_alpha_vantage_balance_sheet,
    get_cashflow as get_alpha_vantage_cashflow,
    get_income_statement as get_alpha_vantage_income_statement,
    get_insider_transactions as get_alpha_vantage_insider_transactions,
    get_news as get_alpha_vantage_news,
    get_global_news as get_alpha_vantage_global_news,
)
from .alpha_vantage_common import AlphaVantageRateLimitError
from yfinance.exceptions import YFRateLimitError
from .akshare_a_stock import (
    get_stock_data_akshare,
    get_news_akshare,
    get_global_news_akshare,
    get_fundamentals_akshare,
    get_balance_sheet_akshare,
    get_cashflow_akshare,
    get_income_statement_akshare,
    get_insider_transactions_akshare,
)
from tradingagents.ticker_utils import is_china_mainland_ticker

# Configuration and routing logic
from .config import get_config

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": [
            "get_stock_data"
        ]
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": [
            "get_indicators"
        ]
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement"
        ]
    },
    "news_data": {
        "description": "News and insider data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
        ]
    }
}

VENDOR_LIST = [
    "akshare",
    "yfinance",
    "alpha_vantage",
]

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "akshare": get_stock_data_akshare,
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
    },
    # technical_indicators
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
    },
    # fundamental_data
    "get_fundamentals": {
        "akshare": get_fundamentals_akshare,
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
    },
    "get_balance_sheet": {
        "akshare": get_balance_sheet_akshare,
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
    },
    "get_cashflow": {
        "akshare": get_cashflow_akshare,
        "alpha_vantage": get_alpha_vantage_cashflow,
        "yfinance": get_yfinance_cashflow,
    },
    "get_income_statement": {
        "akshare": get_income_statement_akshare,
        "alpha_vantage": get_alpha_vantage_income_statement,
        "yfinance": get_yfinance_income_statement,
    },
    # news_data
    "get_news": {
        "akshare": get_news_akshare,
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
    },
    "get_global_news": {
        "akshare": get_global_news_akshare,
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
    },
    "get_insider_transactions": {
        "akshare": get_insider_transactions_akshare,
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
    },
}

def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")

def get_vendor(category: str, method: str = None) -> str:
    """Get the configured vendor for a data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Fall back to category-level configuration
    return config.get("data_vendors", {}).get(category, "default")

def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to appropriate vendor implementation with fallback support."""
    category = get_category_for_method(method)
    vendor_config = get_vendor(category, method)
    primary_vendors = [v.strip() for v in vendor_config.split(',')]
    config = get_config()
    market_region = config.get("market_region", "global")

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    if (
        market_region == "china_mainland"
        and "akshare" in VENDOR_METHODS[method]
        and "akshare" not in primary_vendors
    ):
        primary_vendors = ["akshare"] + primary_vendors

    if (
        market_region != "china_mainland"
        and args
        and isinstance(args[0], str)
        and is_china_mainland_ticker(args[0])
        and "akshare" in VENDOR_METHODS[method]
        and "akshare" not in primary_vendors
    ):
        primary_vendors = ["akshare"] + primary_vendors

    # Build fallback chain: primary vendors first, then remaining available vendors
    all_available_vendors = list(VENDOR_METHODS[method].keys())
    fallback_vendors = primary_vendors.copy()
    for vendor in all_available_vendors:
        if vendor not in fallback_vendors:
            fallback_vendors.append(vendor)

    errors = []

    for vendor in fallback_vendors:
        if vendor not in VENDOR_METHODS[method]:
            continue

        vendor_impl = VENDOR_METHODS[method][vendor]
        impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl

        try:
            return impl_func(*args, **kwargs)
        except (AlphaVantageRateLimitError, YFRateLimitError) as exc:
            errors.append(f"{vendor}: {exc}")
            continue
        except ValueError as exc:
            if vendor == "akshare" and "Unsupported mainland China" in str(exc):
                errors.append(f"{vendor}: {exc}")
                continue
            if vendor == "alpha_vantage" and "ALPHA_VANTAGE_API_KEY" in str(exc):
                errors.append(f"{vendor}: {exc}")
                continue
            raise
        except Exception as exc:
            if vendor == "akshare":
                errors.append(f"{vendor}: {exc}")
                continue
            raise

    if errors:
        china_hint = ""
        if market_region == "china_mainland":
            china_hint = (
                " 当前是 A 股/中国市场模式，程序已优先尝试 AkShare 等中国数据源。"
            )
        raise RuntimeError(
            (
                f"No available vendor for '{method}'. "
                "Yahoo Finance may be rate limiting requests right now. "
                "Wait a bit and retry, or configure Alpha Vantage as a fallback with "
                "`ALPHA_VANTAGE_API_KEY` and set the relevant `data_vendors` entry to "
                "`yfinance,alpha_vantage` or `alpha_vantage,yfinance`."
                f"{china_hint} "
                f"Attempts: {' | '.join(errors)}"
            )
        )

    raise RuntimeError(f"No available vendor for '{method}'")
