from __future__ import annotations

import csv
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "universes" / "jp_topix500.csv"


def clean(value: object) -> str:
    return str(value or "").replace(",", " ").strip()


def pick(row: dict[str, str], names: list[str]) -> str:
    lowered = {key.lower(): value for key, value in row.items()}
    for name in names:
        for key, value in lowered.items():
            if name.lower() in key:
                return clean(value)
    return ""


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    urls = [x.strip() for x in os.getenv("TOPIX_SOURCE_URLS", "").split("|") if x.strip()]
    rows = []
    for url in urls:
        try:
            res = requests.get(url, timeout=30)
            res.raise_for_status()
            text = res.content.decode("shift_jis", errors="ignore")
            reader = csv.DictReader(text.splitlines())
            for row in reader:
                code = pick(row, ["code", "コード", "Local Code"])
                name = pick(row, ["name", "銘柄名", "Issue Name", "Company"])
                weight_raw = pick(row, ["weight", "ウェイト", "Weight"])
                if not code or not code[:4].isdigit():
                    continue
                try:
                    weight = float(weight_raw.replace("%", ""))
                except Exception:
                    weight = 0.0
                rows.append((code[:4] + ".T", name or code[:4], "JP", "TOPIX500", "TOPIX weight proxy", weight))
            if rows:
                break
        except Exception as error:
            print(f"TOPIX source skipped: {error.__class__.__name__}")
    rows = sorted({r[0]: r for r in rows}.values(), key=lambda r: r[-1], reverse=True)[:500]
    lines = ["symbol,name,market,theme,note"]
    for symbol, name, market, theme, note, _ in rows:
        lines.append(f"{symbol},{clean(name)},{market},{theme},{note}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} TOPIX500 proxy symbols")


if __name__ == "__main__":
    main()
