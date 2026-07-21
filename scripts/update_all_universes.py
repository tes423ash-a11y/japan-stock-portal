from __future__ import annotations

import csv
import io
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_DIR = ROOT / "universes"
JP_OUT = UNIVERSE_DIR / "jp_tse_all.csv"
US_OUT = UNIVERSE_DIR / "us_all_listed.csv"
HEADER = ["symbol", "name", "market", "sector", "industry", "theme", "note"]

DEFAULT_JP_SOURCE = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
DEFAULT_US_SOURCE = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&offset=0&download=true"

JP_DOMESTIC_MARKETS = ("プライム（内国株式）", "スタンダード（内国株式）", "グロース（内国株式）")
US_EXCLUDED_SECURITY = re.compile(
    r"\b(warrants?|rights?|units?|preferred|notes? due|bonds?|closed[- ]end fund|"
    r"exchange traded fund|exchange traded note|acquisition corp(?:oration)?|blank check)\b",
    re.IGNORECASE,
)


def clean(value: object) -> str:
    text = str(value or "").replace("\u3000", " ").strip()
    return "" if text.lower() == "nan" else re.sub(r"\s+", " ", text)


def numeric(value: object) -> float | None:
    text = clean(value).replace("$", "").replace(",", "").replace("%", "")
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if number == number else None


def pick(row: dict[str, str], names: tuple[str, ...]) -> str:
    for name in names:
        target = name.casefold()
        for key, value in row.items():
            if target in clean(key).casefold():
                result = clean(value)
                if result:
                    return result
    return ""


def normalize_jp_code(value: object) -> str:
    code = clean(value).upper().removesuffix(".0")
    match = re.fullmatch(r"([0-9A-Z]{4})(?:\.T)?", code)
    return f"{match.group(1)}.T" if match else ""


def normalize_us_symbol(value: object) -> str:
    symbol = clean(value).upper().replace(".", "-")
    return symbol if re.fullmatch(r"[A-Z][A-Z0-9-]{0,7}", symbol) else ""


def write_rows(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent) as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(HEADER)
        writer.writerows(rows)
        temporary = Path(handle.name)
    temporary.replace(path)


def existing_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return sum(1 for row in csv.DictReader(handle) if clean(row.get("symbol")))


def session_get(url: str, accept: str) -> requests.Response:
    response = requests.get(
        url,
        timeout=60,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; japan-stock-portal/6.0; full-market-universe)",
            "Accept": accept,
            "Accept-Language": "ja,en-US;q=0.8,en;q=0.7",
            "Origin": "https://www.nasdaq.com",
            "Referer": "https://www.nasdaq.com/market-activity/stocks/screener",
        },
    )
    response.raise_for_status()
    return response


def parse_jp_frame(frame: pd.DataFrame) -> list[list[str]]:
    rows: dict[str, list[str]] = {}
    for _, source in frame.iterrows():
        row = {clean(key): clean(value) for key, value in source.items()}
        symbol = normalize_jp_code(pick(row, ("コード", "Local Code", "Code")))
        market_product = pick(row, ("市場・商品区分", "Market / Product", "Market and Product"))
        if not symbol or not any(label in market_product for label in JP_DOMESTIC_MARKETS):
            continue
        name = pick(row, ("銘柄名", "Issue Name", "Company Name")) or symbol.removesuffix(".T")
        sector = pick(row, ("33業種区分", "33 Sector Name", "Sector Name")) or "未分類"
        industry = pick(row, ("17業種区分", "17 Sector Name", "Industry"))
        rows[symbol] = [symbol, name, "JP", sector, industry, sector, market_product]
    return [rows[symbol] for symbol in sorted(rows)]


def refresh_japan(url: str) -> int:
    response = session_get(url, "application/vnd.ms-excel,application/octet-stream,*/*;q=0.8")
    frame = pd.read_excel(io.BytesIO(response.content), dtype=str)
    rows = parse_jp_frame(frame)
    if len(rows) < 3_000:
        raise RuntimeError(f"unexpected JP domestic-stock count: {len(rows)}")
    write_rows(JP_OUT, rows)
    return len(rows)


def rows_from_nasdaq(payload: dict[str, Any]) -> list[list[str]]:
    rows: dict[str, list[str]] = {}
    minimum_price = float(os.getenv("US_UNIVERSE_MIN_PRICE", "1"))
    minimum_market_cap = float(os.getenv("US_UNIVERSE_MIN_MARKET_CAP", "100000000"))
    minimum_volume = float(os.getenv("US_UNIVERSE_MIN_VOLUME", "50000"))
    minimum_dollar_volume = float(os.getenv("US_UNIVERSE_MIN_DOLLAR_VOLUME", "1000000"))
    source_rows = ((payload.get("data") or {}).get("rows") or [])
    for source in source_rows:
        symbol = normalize_us_symbol(source.get("symbol"))
        name = clean(source.get("name"))
        price = numeric(source.get("lastsale"))
        market_cap = numeric(source.get("marketCap"))
        volume = numeric(source.get("volume"))
        if not symbol or not name or US_EXCLUDED_SECURITY.search(name):
            continue
        if price is None or market_cap is None or volume is None:
            continue
        if price < minimum_price or market_cap < minimum_market_cap or volume < minimum_volume:
            continue
        if price * volume < minimum_dollar_volume:
            continue
        sector = clean(source.get("sector")) or "未分類"
        industry = clean(source.get("industry"))
        rows[symbol] = [symbol, name, "US", sector, industry, sector, "Nasdaq Stock Screener eligible common stock"]
    return [rows[symbol] for symbol in sorted(rows)]


def refresh_united_states(url: str) -> int:
    response = session_get(url, "application/json,text/plain,*/*;q=0.8")
    rows = rows_from_nasdaq(response.json())
    if len(rows) < 1_500:
        raise RuntimeError(f"unexpected US eligible-stock count: {len(rows)}")
    write_rows(US_OUT, rows)
    return len(rows)


def refresh_or_preserve(label: str, path: Path, minimum_existing: int, callback: Any) -> int:
    try:
        count = int(callback())
        print(f"{label}: wrote {count} symbols")
        return count
    except Exception as error:
        count = existing_count(path)
        if count >= minimum_existing:
            print(f"{label}: refresh failed; preserving {count} existing rows ({error.__class__.__name__}: {error})")
            return count
        raise RuntimeError(f"{label} universe unavailable and no safe fallback exists: {error}") from error


def main() -> None:
    jp_url = os.getenv("TSE_LISTED_ISSUES_URL", DEFAULT_JP_SOURCE).strip() or DEFAULT_JP_SOURCE
    us_url = os.getenv("NASDAQ_SCREENER_URL", DEFAULT_US_SOURCE).strip() or DEFAULT_US_SOURCE
    jp_count = refresh_or_preserve("JP all-listed", JP_OUT, 3_000, lambda: refresh_japan(jp_url))
    us_count = refresh_or_preserve("US eligible", US_OUT, 1_500, lambda: refresh_united_states(us_url))
    print({"JP": jp_count, "US": us_count, "combined": jp_count + us_count})


if __name__ == "__main__":
    main()
