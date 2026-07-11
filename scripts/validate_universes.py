from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_DIR = ROOT / "universes"
REQUIREMENTS = {
    "jp_topix500.csv": 450,
    "us_sp500.csv": 490,
}


def symbols_in(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return {
            (row.get("symbol") or "").strip().upper()
            for row in csv.DictReader(handle)
            if (row.get("symbol") or "").strip()
        }


def main() -> None:
    failures: list[str] = []
    counts: dict[str, int] = {}
    for filename, minimum in REQUIREMENTS.items():
        count = len(symbols_in(UNIVERSE_DIR / filename))
        counts[filename] = count
        if count < minimum:
            failures.append(f"{filename}: {count} < {minimum}")

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

    if len(jp_symbols) < 450:
        failures.append(f"combined JP universe: {len(jp_symbols)} < 450")
    if len(us_symbols) < 490:
        failures.append(f"combined US universe: {len(us_symbols)} < 490")
    if failures:
        raise SystemExit("Universe validation failed: " + "; ".join(failures))


if __name__ == "__main__":
    main()
