from __future__ import annotations

import csv
import io
import os
import tempfile
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "universes" / "us_sp500.csv"
HEADER = ["symbol", "name", "market", "sector", "industry", "theme", "note"]
MIN_VALID_ROWS = 490


def clean(value: object) -> str:
    text = str(value or "").strip()
    return "" if text.lower() == "nan" else text


def existing_count() -> int:
    if not OUT.exists():
        return 0
    with OUT.open(newline="", encoding="utf-8-sig") as handle:
        return sum(1 for row in csv.DictReader(handle) if (row.get("symbol") or "").strip())


def write_rows(rows: list[list[str]]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=OUT.parent) as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(rows)
        temp_path = Path(handle.name)
    temp_path.replace(OUT)


def fetch_table(url: str) -> pd.DataFrame:
    response = requests.get(
        url,
        timeout=45,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; japan-stock-portal/4.0)",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    response.raise_for_status()
    tables = pd.read_html(io.StringIO(response.text))
    for table in tables:
        columns = {str(column).strip() for column in table.columns}
        if "Symbol" in columns and "Security" in columns:
            return table
    raise RuntimeError("S&P 500 constituent table not found")


def main() -> None:
    url = os.getenv("SP500_SOURCE_URL", "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies").strip()
    try:
        table = fetch_table(url)
        rows: list[list[str]] = []
        seen: set[str] = set()
        for _, row in table.iterrows():
            symbol = clean(row.get("Symbol")).replace(".", "-").upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            name = clean(row.get("Security")) or symbol
            sector = clean(row.get("GICS Sector")) or "S&P 500"
            industry = clean(row.get("GICS Sub-Industry"))
            rows.append([symbol, name, "US", sector, industry, sector, "S&P 500 constituent"])
        if len(rows) < MIN_VALID_ROWS:
            raise RuntimeError(f"unexpected constituent count: {len(rows)}")
        write_rows(rows[:520])
        print(f"Wrote {len(rows[:520])} S&P 500 symbols with GICS metadata")
    except Exception as error:
        count = existing_count()
        if count >= MIN_VALID_ROWS:
            print(f"S&P 500 refresh failed; preserving {count} existing rows: {error.__class__.__name__}: {error}")
            return
        raise RuntimeError(
            f"S&P 500 universe unavailable: refresh failed and existing file has only {count} rows"
        ) from error


if __name__ == "__main__":
    main()
