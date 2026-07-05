from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "universes" / "us_sp500.csv"


def clean(value: object) -> str:
    return str(value or "").replace(",", " ").strip()


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    url = os.getenv("SP500_SOURCE_URL", "")
    if not url:
        OUT.write_text("symbol,name,market,theme,note\n", encoding="utf-8")
        print("SP500_SOURCE_URL is empty; wrote header only")
        return
    try:
        table = pd.read_html(url)[0]
        lines = ["symbol,name,market,theme,note"]
        for _, row in table.iterrows():
            symbol = clean(row.get("Symbol")).replace(".", "-")
            name = clean(row.get("Security"))
            sector = clean(row.get("GICS Sector")) or "S&P500"
            if symbol and symbol.lower() != "nan":
                lines.append(f"{symbol},{name},US,{sector},S&P 500")
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Wrote {len(lines) - 1} S&P 500 symbols")
    except Exception as error:
        if not OUT.exists():
            OUT.write_text("symbol,name,market,theme,note\n", encoding="utf-8")
        print(f"S&P 500 update skipped: {error.__class__.__name__}")


if __name__ == "__main__":
    main()
