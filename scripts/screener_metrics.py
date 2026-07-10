from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from screener_data import PREFERRED_THEME_WORDS, finite, market_of, rounded


def pct_change(series: pd.Series, days: int) -> float | None:
    if len(series) <= days:
        return None
    start = finite(series.iloc[-days - 1])
    end = finite(series.iloc[-1])
    if start in (None, 0) or end is None:
        return None
    return (end / start - 1) * 100


def average(series: pd.Series) -> float | None:
    if series.empty:
        return None
    return finite(series.mean())


def range_pct(frame: pd.DataFrame, days: int) -> float | None:
    if len(frame) < days:
        return None
    high = finite(frame["High"].tail(days).max())
    low = finite(frame["Low"].tail(days).min())
    if high in (None, 0) or low is None:
        return None
    return (high / low - 1) * 100


def atr14(frame: pd.DataFrame) -> float | None:
    if len(frame) < 16 or not {"High", "Low", "Close"}.issubset(frame.columns):
        return None
    high = frame["High"].astype(float)
    low = frame["Low"].astype(float)
    close = frame["Close"].astype(float)
    previous = close.shift(1)
    true_range = pd.concat([(high - low), (high - previous).abs(), (low - previous).abs()], axis=1).max(axis=1)
    return finite(true_range.tail(14).mean())


def moving_average(series: pd.Series, days: int) -> float | None:
    if len(series) < days:
        return None
    return finite(series.tail(days).mean())


def preference_match(row: dict[str, str]) -> bool:
    text = " ".join([row.get("theme", ""), row.get("sector", ""), row.get("industry", ""), row.get("name", "")]).lower()
    return any(word in text for word in PREFERRED_THEME_WORDS)


def build_raw_candidate(row: dict[str, str], frame: pd.DataFrame | None, usd_jpy: float) -> dict[str, Any]:
    symbol = row.get("symbol", "")
    market = market_of(row)
    sector = row.get("sector") or row.get("theme") or "未分類"
    theme = row.get("theme") or sector
    base: dict[str, Any] = {
        "symbol": symbol, "code": symbol.replace(".T", ""), "name": row.get("name") or symbol,
        "market": market, "sector": sector, "industry": row.get("industry", ""), "theme": theme,
        "note": row.get("note", ""), "preferenceMatch": preference_match(row), "dataSource": "yfinance_bulk",
    }
    if frame is None or frame.empty or len(frame) < 30:
        base.update({"dataQuality": {"status": "missing", "bars": 0, "asOf": None, "staleDays": None}, "metrics": {}, "warnings": ["価格データ不足"]})
        return base

    close = frame["Close"].astype(float).dropna()
    aligned = frame.loc[close.index].copy()
    high = aligned["High"].astype(float) if "High" in aligned.columns else close
    low = aligned["Low"].astype(float) if "Low" in aligned.columns else close
    volume = aligned["Volume"].astype(float).fillna(0) if "Volume" in aligned.columns else pd.Series(0, index=aligned.index, dtype=float)
    bars = len(close)
    price = finite(close.iloc[-1]) or 0.0
    latest_date = close.index[-1].date()
    stale_days = max(0, (date.today() - latest_date).days)

    ma20, ma50, ma150, ma200 = (moving_average(close, days) for days in (20, 50, 150, 200))
    ma200_20ago = finite(close.iloc[:-20].tail(200).mean()) if bars >= 220 else None
    ma200_slope = ((ma200 / ma200_20ago) - 1) * 100 if ma200 and ma200_20ago else None
    high252 = finite(high.tail(min(252, bars)).max())
    low252 = finite(low.tail(min(252, bars)).min())
    high60 = finite(high.tail(min(60, bars)).max())
    low60 = finite(low.tail(min(60, bars)).min())
    pivot_window = high.iloc[-56:-1] if bars >= 56 else high.iloc[:-1]
    pivot = finite(pivot_window.max()) if not pivot_window.empty else high252
    pivot_distance = ((price / pivot) - 1) * 100 if pivot else None
    drawdown = ((price / high252) - 1) * 100 if high252 else None
    base_depth = ((high60 - low60) / high60) * 100 if high60 and low60 is not None else None

    avg_volume5, avg_volume20, avg_volume50 = (average(volume.tail(days)) for days in (5, 20, 50))
    latest_volume = finite(volume.iloc[-1])
    volume_dry_up = avg_volume5 / avg_volume50 if avg_volume5 is not None and avg_volume50 else None
    latest_volume_ratio = latest_volume / avg_volume20 if latest_volume is not None and avg_volume20 else None
    avg_trading_value20 = price * avg_volume20 if avg_volume20 else 0.0
    latest_trading_value = price * latest_volume if latest_volume else 0.0
    avg_trading_value20_usd = avg_trading_value20 / usd_jpy if market == "JP" else avg_trading_value20
    latest_trading_value_usd = latest_trading_value / usd_jpy if market == "JP" else latest_trading_value

    atr_value = atr14(aligned)
    atr_pct = (atr_value / price) * 100 if atr_value and price else None
    range60, range30, range15, tightness10 = (range_pct(aligned, days) for days in (60, 30, 15, 10))
    contraction_sequence = bool(range60 is not None and range30 is not None and range15 is not None and range60 >= range30 * 1.08 and range30 >= range15 * 1.08)
    high20, low20 = finite(high.tail(20).max()), finite(low.tail(20).min())
    close_location20 = ((price - low20) / (high20 - low20) * 100) if high20 is not None and low20 is not None and high20 > low20 else None

    metrics = {
        "price": rounded(price, 2), "ma20": rounded(ma20, 2), "ma50": rounded(ma50, 2),
        "ma150": rounded(ma150, 2), "ma200": rounded(ma200, 2), "ma200Slope20dPct": rounded(ma200_slope, 2),
        "ret5Pct": rounded(pct_change(close, 5), 1), "ret20Pct": rounded(pct_change(close, 20), 1),
        "ret60Pct": rounded(pct_change(close, 60), 1), "ret120Pct": rounded(pct_change(close, 120), 1),
        "ret252Pct": rounded(pct_change(close, 252), 1), "atrPct": rounded(atr_pct, 2),
        "drawdownFromHighPct": rounded(drawdown, 1), "distanceToPivotPct": rounded(pivot_distance, 2),
        "baseDepth60Pct": rounded(base_depth, 1), "range60Pct": rounded(range60, 1), "range30Pct": rounded(range30, 1),
        "range15Pct": rounded(range15, 1), "tightness10Pct": rounded(tightness10, 1), "contractionSequence": contraction_sequence,
        "volumeDryUp5vs50": rounded(volume_dry_up, 2), "latestVolumeRatio20": rounded(latest_volume_ratio, 2),
        "avgVolume20": rounded(avg_volume20, 0), "latestVolume": rounded(latest_volume, 0),
        "avgTradingValue20": rounded(avg_trading_value20, 0), "avgTradingValue20Usd": rounded(avg_trading_value20_usd, 0),
        "latestTradingValue": rounded(latest_trading_value, 0), "latestTradingValueUsd": rounded(latest_trading_value_usd, 0),
        "closeLocation20Pct": rounded(close_location20, 1),
        "extendedFromMa20Pct": rounded(((price / ma20) - 1) * 100 if ma20 else None, 1),
        "extendedFromMa50Pct": rounded(((price / ma50) - 1) * 100 if ma50 else None, 1),
        "high52w": rounded(high252, 2), "low52w": rounded(low252, 2), "pivot": rounded(pivot, 2),
        "recentLow10": rounded(finite(low.tail(10).min()), 2), "bars": bars,
    }
    quality_status = "full" if bars >= 252 else "partial" if bars >= 200 else "limited"
    warnings: list[str] = []
    if quality_status != "full": warnings.append("履歴不足")
    if stale_days > 5: warnings.append("データ更新遅延")
    if atr_pct is not None and atr_pct > 8: warnings.append("高ATR")
    if avg_trading_value20_usd < 10_000_000: warnings.append("流動性低め")
    if ma200 and price < ma200: warnings.append("200日線下")
    if pivot_distance is not None and pivot_distance > 5: warnings.append("買い場超過")
    base.update({
        "price": rounded(price, 2), "pivot": rounded(pivot, 2), "metrics": metrics, "warnings": warnings,
        "dataQuality": {"status": quality_status, "bars": bars, "asOf": latest_date.isoformat(), "staleDays": stale_days},
    })
    return base
