from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "latest.json"
SIGNALS = ROOT / "data" / "external_signals.csv"
FIELDS = ["kabutan_signal", "karauri_short_score", "minkabu_target_gap_pct", "credit_score", "earnings_momentum"]


def to_float(value: str | None) -> float | None:
    text = str(value or "").strip().replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def load_signals() -> dict[str, dict[str, str]]:
    if not SIGNALS.exists():
        return {}
    with SIGNALS.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        symbol = (row.get("symbol") or "").strip().upper()
        if symbol:
            result[symbol] = {key: (value or "").strip() for key, value in row.items()}
    return result


def external_score(row: dict[str, str]) -> float | None:
    usable = [value for value in (to_float(row.get(field)) for field in FIELDS) if value is not None]
    if not usable:
        return None
    return round(clamp(sum(usable) / len(usable) * 10, 0, 100), 1)


def main() -> None:
    if not REPORT.exists():
        raise FileNotFoundError("reports/latest.json not found")
    signals = load_signals()
    report: dict[str, Any] = json.loads(REPORT.read_text(encoding="utf-8"))
    matched = 0
    for item in report.get("candidates", []):
        symbol = str(item.get("symbol") or "").upper()
        row = signals.get(symbol)
        if not row:
            continue
        item["externalSignals"] = row
        item["externalSignalScore"] = external_score(row)
        item["externalSignalPolicy"] = "context_only"
        matched += 1

    report["externalSignals"] = {
        "source": str(SIGNALS.relative_to(ROOT)),
        "matchedCandidates": matched,
        "availableRows": len(signals),
        "fields": FIELDS,
        "policy": "External/manual signals are context only and never modify technical score or rank.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(report["externalSignals"], ensure_ascii=False))


if __name__ == "__main__":
    main()
