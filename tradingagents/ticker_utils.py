from __future__ import annotations

import contextlib
import io
import re
import unicodedata
from functools import lru_cache


TICKER_INPUT_EXAMPLES = "600519, 中际旭创, 000001, 159915, SPY, 0700.HK"

_CHINA_NAME_PATTERN = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF]")

try:
    import akshare as ak
except ImportError:  # pragma: no cover - dependency is installed in normal app usage
    ak = None


def normalize_ticker_symbol(ticker: str) -> str:
    """Normalize common ticker inputs across US, HK, JP, and Chinese markets.

    For mainland China instruments, users often enter bare 6-digit codes
    (for example `600519` or `000001`) or broker-style prefixes like
    `sh600519`. Yahoo Finance expects exchange-qualified tickers such as
    `600519.SS` and `000001.SZ`, so we normalize those inputs here.
    """

    compact = _compact_text(ticker)
    cleaned = compact.upper()
    if not cleaned:
        return ""

    if match := re.fullmatch(r"(SH|SZ|BJ)(\d{6})", cleaned):
        prefix, code = match.groups()
        return f"{code}.{_exchange_suffix_from_prefix(prefix)}"

    if match := re.fullmatch(r"(SSE|SZSE|BSE)[:.](\d{6})", cleaned):
        exchange, code = match.groups()
        exchange_map = {"SSE": "SS", "SZSE": "SZ", "BSE": "BJ"}
        return f"{code}.{exchange_map[exchange]}"

    if match := re.fullmatch(r"(\d{6})\.(SH|SS|SZ|BJ)", cleaned):
        code, suffix = match.groups()
        return f"{code}.{_exchange_suffix_from_prefix(suffix)}"

    if re.fullmatch(r"\d{6}", cleaned):
        return _normalize_mainland_six_digit_code(cleaned)

    if _looks_like_china_security_name(compact):
        resolved = resolve_mainland_stock_name(compact)
        if resolved:
            return resolved

    return cleaned


def is_china_mainland_ticker(ticker: str) -> bool:
    normalized = normalize_ticker_symbol(ticker)
    return bool(re.fullmatch(r"\d{6}\.(SS|SZ|BJ)", normalized))


def infer_market_region(ticker: str) -> str:
    return "china_mainland" if is_china_mainland_ticker(ticker) else "global"


def to_mainland_stock_code(ticker: str) -> str | None:
    normalized = normalize_ticker_symbol(ticker)
    match = re.fullmatch(r"(\d{6})\.(SS|SZ|BJ)", normalized)
    if not match:
        return None
    return match.group(1)


def to_eastmoney_symbol(ticker: str) -> str | None:
    normalized = normalize_ticker_symbol(ticker)
    match = re.fullmatch(r"(\d{6})\.(SS|SZ|BJ)", normalized)
    if not match:
        return None

    code, suffix = match.groups()
    exchange = {"SS": "SH", "SZ": "SZ", "BJ": "BJ"}[suffix]
    return f"{exchange}{code}"


def _exchange_suffix_from_prefix(prefix: str) -> str:
    return "SS" if prefix == "SH" else prefix


def _normalize_mainland_six_digit_code(code: str) -> str:
    first_digit = code[0]

    if first_digit in {"5", "6", "9"}:
        return f"{code}.SS"
    if first_digit in {"0", "1", "2", "3"}:
        return f"{code}.SZ"
    if first_digit in {"4", "8"}:
        return f"{code}.BJ"

    return code


def resolve_mainland_stock_name(ticker_or_name: str) -> str | None:
    compact = _compact_text(ticker_or_name)
    if not compact or not _looks_like_china_security_name(compact):
        return None

    return _get_china_mainland_name_map().get(_canonicalize_equity_name(compact))


def _looks_like_china_security_name(value: str) -> bool:
    return bool(_CHINA_NAME_PATTERN.search(value))


def _compact_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    return re.sub(r"\s+", "", normalized).strip()


def _canonicalize_equity_name(name: str) -> str:
    canonical = _compact_text(name).upper()
    if canonical.startswith("*ST"):
        return canonical
    if canonical.startswith("ST"):
        return canonical
    return canonical.lstrip("*")


def _iter_name_aliases(name: str) -> list[str]:
    canonical = _canonicalize_equity_name(name)
    aliases = {canonical}

    if canonical.startswith("*ST"):
        aliases.add(canonical[1:])
    if canonical.startswith("ST"):
        aliases.add(f"*{canonical}")

    return [alias for alias in aliases if alias]


@lru_cache(maxsize=1)
def _get_china_mainland_name_map() -> dict[str, str]:
    if ak is None:
        return {}

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        stock_df = ak.stock_info_a_code_name()

    mapping: dict[str, str] = {}
    for row in stock_df.itertuples(index=False):
        code = str(getattr(row, "code", "") or "").strip().zfill(6)
        name = str(getattr(row, "name", "") or "").strip()
        if not re.fullmatch(r"\d{6}", code) or not name:
            continue

        normalized_code = _normalize_mainland_six_digit_code(code)
        for alias in _iter_name_aliases(name):
            mapping.setdefault(alias, normalized_code)

    return mapping
