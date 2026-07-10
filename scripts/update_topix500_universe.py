from __future__ import annotations

import csv
import io
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "universes" / "jp_topix500.csv"
HEADER = ["symbol", "name", "market", "sector", "industry", "theme", "note"]


def clean(value: object) -> str:
    return str(value or "").replace("\u3000", " ").strip()


def pick(row: dict[str, str], names: list[str]) -> str:
    for name in names:
        for key, value in row.items():
            if name.lower() in str(key).lower():
                result = clean(value)
                if result:
                    return result
    return ""


def decode_csv(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp932", "shift_jis"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def write_rows(rows: list[list[str]]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(rows)


def main() -> None:
    urls = [url.strip() for url in os.getenv("TOPIX_SOURCE_URLS", "").split("|") if url.strip()]
    collected: dict[str, tuple[list[str], float]] = {}
    for url in urls:
        try:
            response = requests.get(url, timeout=40, headers={"User-Agent": "japan-stock-portal/3.0"})
            response.raise_for_status()
            reader = csv.DictReader(io.StringIO(decode_csv(response.content)))
            for row in reader:
                code = pick(row, ["Local Code", "code", "コード"])
                name = pick(row, ["Issue Name", "銘柄名", "name", "Company"])
                sector = pick(row, ["33 Sector Name", "33業種区分", "Sector Name", "sector"])
                industry = pick(row, ["17 Sector Name", "17業種区分", "Industry"])
                weight_raw = pick(row, ["TOPIX Weight", "weight", "ウェイト"])
                digits = "".join(character for character in code if character.isdigit())
                if len(digits) < 4:
                    continue
                symbol = digits[:4] + ".T"
                try:
                    weight = float(weight_raw.replace("%", "").replace(",", ""))
                except ValueError:
                    weight = 0.0
                label = sector or industry or "TOPIX 500"
                collected[symbol] = ([symbol, name or digits[:4], "JP", label, industry, label, "TOPIX weight universe"], weight)
            if len(collected) >= 450:
                break
        except Exception as error:
            print(f"TOPIX source skipped: {error.__class__.__name__}: {error}")

    ordered = sorted(collected.values(), key=lambda item: item[1], reverse=True)[:500]
    rows = [row for row, _ in ordered]
    if len(rows) < 400:
        print(f"TOPIX update produced only {len(rows)} rows; preserving existing file")
        return
    write_rows(rows)
    print(f"Wrote {len(rows)} TOPIX symbols with sector metadata")


if __name__ == "__main__":
    main()
