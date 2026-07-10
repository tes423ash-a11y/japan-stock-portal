from __future__ import annotations

import csv
import math
import os
import time
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
WATCHLISTS = [ROOT / "watchlists" / "jp_candidates.csv", ROOT / "watchlists" / "us_candidates.csv"]
UNIVERSE_FILES = sorted((ROOT / "universes").glob("*.csv"))
REPORT_DIR = ROOT / "reports"
GENERIC_THEMES = {"", "TOPIX500", "S&P500", "Uncategorized", "未分類"}
PREFERRED_THEME_WORDS = (
    "hbm", "memory", "dram", "nand", "ai", "data center", "datacenter", "optical",
    "semiconductor", "mlcc", "defense", "重工", "防衛", "power", "電力", "原子力",
    "nuclear", "robot", "ロボット", "physical ai", "cpo",
)


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def clamp(number: float, low: float, high: float) -> float:
    return max(low, min(high, number))


def finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def rounded(value: Any, digits: int = 1) -> float | None:
    number = finite(value)
    return round(number, digits) if number is not None else None


def safe_text(value: Any) -> str:
    return str(value or "").strip()


def market_of(row: dict[str, str]) -> str:
    market = safe_text(row.get("market")).upper()
    if market in {"JP", "US"}:
        return market
    return "JP" if safe_text(row.get("symbol")).endswith(".T") else "US"


def choose_theme(current: str, incoming: str) -> str:
    current = safe_text(current)
    incoming = safe_text(incoming)
    if not current:
        return incoming
    if current in GENERIC_THEMES and incoming not in GENERIC_THEMES:
        return incoming
    return current


def merge_metadata(current: dict[str, str], incoming: dict[str, str]) -> dict[str, str]:
    result = dict(current)
    for key in {"name", "market", "sector", "industry", "note"}:
        if not safe_text(result.get(key)) and safe_text(incoming.get(key)):
            result[key] = safe_text(incoming.get(key))
    result["theme"] = choose_theme(result.get("theme", ""), incoming.get("theme", ""))
    if not safe_text(result.get("sector")):
        result["sector"] = safe_text(incoming.get("sector")) or safe_text(incoming.get("theme"))
    if not safe_text(result.get("industry")):
        result["industry"] = safe_text(incoming.get("industry"))
    notes = [safe_text(result.get("note")), safe_text(incoming.get("note"))]
    result["note"] = " / ".join(dict.fromkeys(item for item in notes if item))
    return result


def read_csv_files(paths: Iterable[Path]) -> list[dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    order: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for raw in csv.DictReader(handle):
                row = {key: safe_text(value) for key, value in raw.items() if key}
                symbol = safe_text(row.get("symbol")).upper()
                if not symbol:
                    continue
                row["symbol"] = symbol
                row["market"] = market_of(row)
                row.setdefault("sector", row.get("theme", ""))
                row.setdefault("industry", "")
                row.setdefault("theme", row.get("sector", "") or "未分類")
                if symbol not in merged:
                    merged[symbol] = row
                    order.append(symbol)
                else:
                    merged[symbol] = merge_metadata(merged[symbol], row)
    return [merged[symbol] for symbol in order]


def read_input_rows() -> tuple[list[dict[str, str]], str]:
    mode = safe_text(os.getenv("SCREENING_MODE", "all_universe")) or "all_universe"
    if mode in {"top_turnover", "top_turnover_today", "all_universe"}:
        rows = read_csv_files(UNIVERSE_FILES)
        if rows:
            return rows, mode
    return read_csv_files(WATCHLISTS), "watchlists"


def split_rows_by_market(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {"JP": [], "US": []}
    for row in rows:
        result.setdefault(market_of(row), []).append(row)
    return result


def chunked(items: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def normalize_download_frame(frame: pd.DataFrame, symbol: str, requested_count: int) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    sub = frame
    if isinstance(frame.columns, pd.MultiIndex):
        level0 = set(map(str, frame.columns.get_level_values(0)))
        level1 = set(map(str, frame.columns.get_level_values(1)))
        if symbol in level0:
            sub = frame[symbol].copy()
        elif symbol in level1:
            sub = frame.xs(symbol, axis=1, level=1).copy()
        elif requested_count == 1:
            sub = frame.copy()
            sub.columns = sub.columns.get_level_values(-1)
        else:
            return pd.DataFrame()
    needed = [column for column in ["Open", "High", "Low", "Close", "Volume"] if column in sub.columns]
    if "Close" not in needed:
        return pd.DataFrame()
    sub = sub[needed].copy().dropna(subset=["Close"])
    if sub.empty:
        return sub
    sub.index = pd.to_datetime(sub.index)
    return sub.sort_index()


def download_history(symbols: list[str]) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    chunk_size = int(clamp(env_int("YF_CHUNK_SIZE", 80), 20, 150))
    retries = int(clamp(env_int("YF_RETRIES", 2), 1, 4))
    pause = env_float("YF_CHUNK_PAUSE_SECONDS", 0.7)
    period = safe_text(os.getenv("YF_PERIOD", "18mo")) or "18mo"
    histories: dict[str, pd.DataFrame] = {}
    failed_chunks: list[dict[str, Any]] = []
    batch_count = 0

    for chunk in chunked(symbols, chunk_size):
        batch_count += 1
        downloaded: pd.DataFrame | None = None
        last_error = ""
        for attempt in range(1, retries + 1):
            try:
                downloaded = yf.download(tickers=chunk, period=period, interval="1d", group_by="ticker", auto_adjust=True, progress=False, threads=True)
                if downloaded is not None and not downloaded.empty:
                    break
            except Exception as error:
                last_error = error.__class__.__name__
            time.sleep(attempt * 1.5)
        if downloaded is None or downloaded.empty:
            failed_chunks.append({"size": len(chunk), "symbols": chunk[:5], "error": last_error or "empty_response"})
        else:
            for symbol in chunk:
                sub = normalize_download_frame(downloaded, symbol, len(chunk))
                if not sub.empty:
                    histories[symbol] = sub
        if pause > 0:
            time.sleep(pause)

    missing = [symbol for symbol in symbols if symbol not in histories]
    fallback_limit = int(clamp(env_int("YF_FALLBACK_LIMIT", 40), 0, 100))
    fallback_used = 0
    for symbol in missing[:fallback_limit]:
        try:
            single = yf.download(tickers=symbol, period=period, interval="1d", auto_adjust=True, progress=False, threads=False)
            sub = normalize_download_frame(single, symbol, 1)
            if not sub.empty:
                histories[symbol] = sub
                fallback_used += 1
        except Exception:
            continue

    diagnostics = {
        "provider": "yfinance_bulk", "requested": len(symbols), "downloaded": len(histories),
        "missing": len(symbols) - len(histories), "batchCount": batch_count, "chunkSize": chunk_size,
        "fallbackUsed": fallback_used, "failedChunks": failed_chunks[:10], "period": period,
    }
    return histories, diagnostics
