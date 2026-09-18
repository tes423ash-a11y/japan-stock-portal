from __future__ import annotations

import csv
import json
import math
import os
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yfinance as yf
from market_sessions import expected_session, completed_history, merge_fresh_history

ROOT = Path(__file__).resolve().parents[1]
WATCHLISTS = [ROOT / "watchlists" / "jp_candidates.csv", ROOT / "watchlists" / "us_candidates.csv"]


def universe_file_priority(path: Path) -> tuple[int, str]:
    name = path.name.lower()
    if any(label in name for label in ("liquid", "theme", "extra")):
        return 0, name
    if any(label in name for label in ("topix500", "sp500")):
        return 1, name
    return 2, name


UNIVERSE_FILES = sorted((ROOT / "universes").glob("*.csv"), key=universe_file_priority)
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


def is_placeholder_name(value: str, symbol: str) -> bool:
    name = safe_text(value).upper()
    code = safe_text(symbol).upper()
    return not name or name in {code, code.replace(".T", "")}


def merge_metadata(current: dict[str, str], incoming: dict[str, str]) -> dict[str, str]:
    result = dict(current)
    symbol = safe_text(result.get("symbol") or incoming.get("symbol"))
    if is_placeholder_name(result.get("name", ""), symbol) and not is_placeholder_name(incoming.get("name", ""), symbol):
        result["name"] = safe_text(incoming.get("name"))
    for key in {"market", "sector", "industry", "note"}:
        if not safe_text(result.get(key)) and safe_text(incoming.get(key)):
            result[key] = safe_text(incoming.get(key))
    result["theme"] = choose_theme(result.get("theme", ""), incoming.get("theme", ""))
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
                row["sector"] = safe_text(row.get("sector"))
                row["industry"] = safe_text(row.get("industry"))
                row["theme"] = safe_text(row.get("theme"))
                if symbol not in merged:
                    merged[symbol] = row
                    order.append(symbol)
                else:
                    merged[symbol] = merge_metadata(merged[symbol], row)
    rows: list[dict[str, str]] = []
    for symbol in order:
        row = merged[symbol]
        row["theme"] = safe_text(row.get("theme")) or safe_text(row.get("sector")) or "未分類"
        row["sector"] = safe_text(row.get("sector")) or row["theme"]
        row["industry"] = safe_text(row.get("industry"))
        rows.append(row)
    return rows


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


def has_price_scale_break(frame: pd.DataFrame, maximum_ratio: float = 20.0) -> bool:
    """Reject provider candles with impossible adjusted-price scale discontinuities."""
    if frame is None or frame.empty or "Close" not in frame.columns:
        return False
    close = pd.to_numeric(frame["Close"], errors="coerce").dropna()
    if len(close) < 2 or (close <= 0).any():
        return bool((close <= 0).any())
    ratios = close / close.shift(1)
    return bool(((ratios > maximum_ratio) | (ratios < 1 / maximum_ratio)).fillna(False).any())


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
    sub = sub.sort_index()
    return pd.DataFrame() if has_price_scale_break(sub) else sub


def download_history(symbols: list[str]) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    chunk_size = int(clamp(env_int("YF_CHUNK_SIZE", 80), 20, 150))
    retries = int(clamp(env_int("YF_RETRIES", 2), 1, 4))
    pause = env_float("YF_CHUNK_PAUSE_SECONDS", 0.7)
    timeout = clamp(env_float("YF_TIMEOUT_SECONDS", 20), 5, 60)
    threads = int(clamp(env_int("YF_THREADS", 4), 1, 8))
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
                downloaded = yf.download(tickers=chunk, period=period, interval="1d", group_by="ticker", auto_adjust=True, progress=False, threads=threads, timeout=timeout)
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
            single = yf.download(tickers=symbol, period=period, interval="1d", auto_adjust=True, progress=False, threads=False, timeout=timeout)
            sub = normalize_download_frame(single, symbol, 1)
            if not sub.empty:
                histories[symbol] = sub
                fallback_used += 1
        except Exception:
            continue

    # Bulk calls can succeed while most US candles are one session behind.
    # Retry every stale symbol, independent of ranking/display limits.
    expected = {"JP": expected_session("JP"), "US": expected_session("US")}
    def session_for(symbol):
        return expected["JP" if symbol.endswith(".T") else "US"]
    for symbol, frame in list(histories.items()):
        histories[symbol] = completed_history(frame, session_for(symbol))
        if histories[symbol].empty:
            del histories[symbol]
    stale = [symbol for symbol in symbols if session_for(symbol) and (symbol not in histories or histories[symbol].index[-1].date().isoformat() < session_for(symbol))]
    recovery = recover_stale_history(
        stale, histories, expected, chunk_size=chunk_size, period=period,
        timeout=timeout, threads=threads, pause=pause,
    )

    missing = [symbol for symbol in symbols if symbol not in histories]
    diagnostics = {
        "provider": "yfinance_bulk", "requested": len(symbols), "downloaded": len(histories),
        "missing": len(symbols) - len(histories), "batchCount": batch_count, "chunkSize": chunk_size,
        "fallbackUsed": fallback_used, "failedChunks": failed_chunks[:10], "period": period,
        "missingSymbols": missing[:30], "timeoutSeconds": timeout,
        "expectedSessions": expected, "threads": threads, **recovery,
    }
    return histories, diagnostics


def recover_stale_history(symbols, histories, expected, *, chunk_size, period, timeout, threads, pause):
    """Retry unresolved sessions, preserving history and adjusted-price continuity."""
    attempts = int(clamp(env_int("YF_FRESHNESS_RETRIES", 3), 1, 4))
    backoff = clamp(env_float("YF_FRESHNESS_BACKOFF_SECONDS", 15), 0, 60)
    pending = list(symbols)
    rounds = []
    adjustment_reloads = 0

    def market_for(symbol):
        return "JP" if symbol.endswith(".T") else "US"

    def distributions():
        result = {"JP": Counter(), "US": Counter()}
        for symbol in symbols:
            history = histories.get(symbol)
            latest = history.index[-1].date().isoformat() if history is not None and not history.empty else "missing"
            result[market_for(symbol)][latest] += 1
        return {market: dict(sorted(counts.items())) for market, counts in result.items()}

    for attempt in range(1, attempts + 1):
        if not pending:
            break
        if attempt > 1 and backoff:
            time.sleep(backoff * 2 ** (attempt - 2))
        before = len(pending)
        detail = {"attempt": attempt, "requested": before, "beforeDates": distributions(), "errors": [], "requests": {}}
        recovered = set()
        # Explicit end is exclusive. Range queries include the completed session
        # instead of relying exclusively on the provider's rolling 5d response.
        for market in ("JP", "US"):
            market_symbols = [symbol for symbol in pending if market_for(symbol) == market]
            if not market_symbols:
                continue
            day = date.fromisoformat(expected[market])
            window = {"period": "5d"} if attempt == 2 else {
                "start": (day - timedelta(days=10 * attempt)).isoformat(),
                "end": (day + timedelta(days=1)).isoformat(),
            }
            detail["requests"][market] = window
            for chunk in chunked(market_symbols, chunk_size):
                try:
                    recent = yf.download(tickers=chunk, interval="1d", group_by="ticker", auto_adjust=True,
                                         progress=False, threads=threads, timeout=timeout, **window)
                except Exception as error:
                    detail["errors"].append({"symbols": chunk[:5], "error": error.__class__.__name__})
                    if pause > 0:
                        time.sleep(pause)
                    continue
                for symbol in chunk:
                    try:
                        sub = completed_history(normalize_download_frame(recent, symbol, len(chunk)), expected[market])
                        if sub.empty or sub.index[-1].date().isoformat() != expected[market]:
                            continue
                        previous = histories.get(symbol, pd.DataFrame())
                        merged = merge_fresh_history(previous, sub, expected[market]) if not previous.empty else None
                        if merged is None:
                            adjustment_reloads += 1
                            full = yf.download(tickers=symbol, period=period, interval="1d", auto_adjust=True,
                                               progress=False, threads=False, timeout=timeout)
                            full = completed_history(normalize_download_frame(full, symbol, 1), expected[market])
                            # A short retry is never a replacement for missing full history.
                            merged = merge_fresh_history(full, sub, expected[market]) if len(full) >= 30 else None
                        if (merged is not None and not merged.empty
                                and merged.index[-1].date().isoformat() == expected[market]
                                and len(merged) >= len(previous) and not has_price_scale_break(merged)):
                            histories[symbol] = merged
                            recovered.add(symbol)
                    except Exception as error:
                        # One malformed ticker must not prevent recovery of its peers.
                        detail["errors"].append({"symbols": [symbol], "error": error.__class__.__name__})
                if pause > 0:
                    time.sleep(pause)
        pending = [symbol for symbol in pending if symbol not in recovered]
        detail.update({"recovered": before - len(pending), "unresolved": len(pending), "afterDates": distributions()})
        detail["errorCount"] = len(detail["errors"])
        detail["errors"] = detail["errors"][:20]
        rounds.append(detail)
        print(json.dumps({"freshnessRetry": detail}, ensure_ascii=False), flush=True)

    return {
        "staleRetryRequested": len(symbols), "staleRecovered": len(symbols) - len(pending),
        "staleUnresolved": len(pending), "staleUnresolvedSymbols": pending[:30],
        "adjustmentReloads": adjustment_reloads, "freshnessRetries": rounds,
    }
