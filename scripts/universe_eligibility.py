"""Effective-dated exclusions for current screening, never historical records.

This small registry is deliberately not a complete point-in-time universe. An
unknown symbol remains eligible; absence from a monthly metadata file is not a
delisting. Invalid or missing exclusion data stops generation rather than
silently admitting a known delisted symbol.
"""
from __future__ import annotations

import csv
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, TypeVar
from zoneinfo import ZoneInfo

CONFIRMED_DELISTINGS = Path(__file__).resolve().parents[1] / "data" / "confirmed_delistings.csv"
Row = TypeVar("Row", bound=dict[str, Any])


def eligibility_date(as_of: date | str | None = None) -> date:
    if as_of is None:
        return datetime.now(ZoneInfo("Asia/Tokyo")).date()
    if type(as_of) is date:
        return as_of
    if not isinstance(as_of, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of):
        raise ValueError(f"Invalid eligibility date: {as_of!r}; expected YYYY-MM-DD")
    return date.fromisoformat(as_of)


def confirmed_delistings() -> dict[str, dict[str, str]]:
    events: dict[str, dict[str, str]] = {}
    with CONFIRMED_DELISTINGS.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"symbol", "market", "delisted_on", "name", "source"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Confirmed delistings registry is missing required columns")
        for row in reader:
            event = {key: str(value or "").strip() for key, value in row.items() if key}
            symbol = event["symbol"].upper()
            if not re.fullmatch(r"[0-9A-Z]{4}\.T", symbol) or event["market"] != "JP":
                raise ValueError(f"Invalid JP delisting symbol/market: {symbol!r}")
            if symbol in events:
                raise ValueError(f"Duplicate confirmed delisting: {symbol}")
            eligibility_date(event["delisted_on"])
            if not event["name"] or not event["source"].startswith("https://www.jpx.co.jp/"):
                raise ValueError(f"Missing name or JPX source for delisting: {symbol}")
            event["symbol"] = symbol
            events[symbol] = event
    if not events:
        raise ValueError("Confirmed delistings registry is empty")
    return events


def effective_delistings(as_of: date | str | None = None) -> dict[str, dict[str, str]]:
    cutoff = eligibility_date(as_of)
    return {
        symbol: event for symbol, event in confirmed_delistings().items()
        if eligibility_date(event["delisted_on"]) <= cutoff
    }


def filter_current_rows(rows: list[Row], as_of: date | str | None = None) -> list[Row]:
    """Preserve row order and metadata; exclude only effective confirmed events."""
    excluded = effective_delistings(as_of)
    return [row for row in rows if str(row.get("symbol") or "").strip().upper() not in excluded]
