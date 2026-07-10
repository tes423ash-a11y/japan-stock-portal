from __future__ import annotations

import csv
import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "universes" / "us_sp500.csv"
HEADER = ["symbol", "name", "market", "sector", "industry", "theme", "note"]


def clean(value: object) -> str:
    text = str(value or "").strip()
    return "" if text.lower() == "nan" else text


def write_rows(rows: list[list[str]]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(rows)


def main() -> None:
    url = os.getenv("SP500_SOURCE_URL", "").strip()
    if not url:
        print("SP500_SOURCE_URL is empty; preserving existing universe")
        return
    try:
        table = pd.read_html(url)[0]
        rows: list[list[str]] = []
        for _, row in table.iterrows():
            symbol = clean(row.get("Symbol")).replace(".", "-").upper()
            name = clean(row.get("Security"))
            sector = clean(row.get("GICS Sector")) or "S&P 500"
            industry = clean(row.get("GICS Sub-Industry"))
            if symbol:
                rows.append([symbol, name or symbol, "US", sector, industry, sector, "S&P 500 constituent"])
        if len(rows) < 450:
            raise RuntimeError(f"unexpected constituent count: {len(rows)}")
        write_rows(rows[:520])
        print(f"Wrote {len(rows[:520])} S&P 500 symbols with GICS metadata")
    except Exception as error:
        print(f"S&P 500 update skipped; preserving existing file: {error.__class__.__name__}: {error}")


if __name__ == "__main__":
    main()
