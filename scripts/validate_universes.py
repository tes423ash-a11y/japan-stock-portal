from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_DIR = ROOT / "universes"
REQUIREMENTS = {
    "jp_topix500.csv": 450,
    "us_sp500.csv": 490,
}
MIN_COMBINED_PER_MARKET = 500
MIN_METADATA_ROWS = {
    "jp_topix500.csv": 450,
    "us_sp500.csv": 490,
}


def rows_in(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [row for row in csv.DictReader(handle) if (row.get("symbol") or "").strip()]


def symbols_in(path: Path) -> set[str]:
    return {(row.get("symbol") or "").strip().upper() for row in rows_in(path)}


def has_metadata(row: dict[str, str]) -> bool:
    symbol = (row.get("symbol") or "").strip().upper()
    name = (row.get("name") or "").strip().upper()
    sector = (row.get("sector") or "").strip()
    return bool(name and sector and name not in {symbol, symbol.replace(".T", "")})


def main() -> None:
    failures: list[str] = []
    counts: dict[str, int] = {}
    for filename, minimum in REQUIREMENTS.items():
        path = UNIVERSE_DIR / filename
        count = len(symbols_in(path))
        counts[filename] = count
        if count < minimum:
            failures.append(f"{filename}: {count} < {minimum}")
        metadata_count = sum(1 for row in rows_in(path) if has_metadata(row))
        metadata_minimum = MIN_METADATA_ROWS.get(filename, 0)
        counts[f"{filename}:metadata"] = metadata_count
        if metadata_count < metadata_minimum:
            failures.append(f"{filename} metadata: {metadata_count} < {metadata_minimum}")

    all_symbols: set[str] = set()
    jp_symbols: set[str] = set()
    us_symbols: set[str] = set()
    for path in sorted(UNIVERSE_DIR.glob("*.csv")):
        symbols = symbols_in(path)
        all_symbols.update(symbols)
        jp_symbols.update(symbol for symbol in symbols if symbol.endswith(".T"))
        us_symbols.update(symbol for symbol in symbols if not symbol.endswith(".T"))

    print({
        "requiredFiles": counts,
        "combinedUnique": len(all_symbols),
        "JP": len(jp_symbols),
        "US": len(us_symbols),
    })

    if len(jp_symbols) < MIN_COMBINED_PER_MARKET:
        failures.append(f"combined JP universe: {len(jp_symbols)} < {MIN_COMBINED_PER_MARKET}")
    if len(us_symbols) < MIN_COMBINED_PER_MARKET:
        failures.append(f"combined US universe: {len(us_symbols)} < {MIN_COMBINED_PER_MARKET}")
    if failures:
        raise SystemExit("Universe validation failed: " + "; ".join(failures))


if __name__ == "__main__":
    main()
