from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "latest.json"
SIGNALS = ROOT / "data" / "external_signals.csv"

FIELDS = [
    "kabutan_signal",
    "karauri_short_score",
    "minkabu_target_gap_pct",
    "credit_score",
    "earnings_momentum",
]


def to_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("%", "")
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
    with SIGNALS.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    result = {}
    for row in rows:
        symbol = (row.get("symbol") or "").strip().upper()
        if symbol:
            result[symbol] = {k: (v or "").strip() for k, v in row.items()}
    return result


def external_score(row: dict[str, str]) -> tuple[float | None, float]:
    nums = [to_float(row.get(field)) for field in FIELDS]
    usable = [n for n in nums if n is not None]
    if not usable:
        return None, 0.0
    base = sum(usable) / len(usable)
    target_gap = to_float(row.get("minkabu_target_gap_pct"))
    gap_bonus = 0.0
    if target_gap is not None:
        gap_bonus = clamp(target_gap / 10.0, -3.0, 3.0)
    score = clamp(base * 10.0 + gap_bonus, 0.0, 100.0)
    bonus = clamp((score - 50.0) / 10.0, -5.0, 8.0)
    return round(score, 1), round(bonus, 1)


def maybe_promote_rank(rank: str, score: int, ext_score: float | None) -> str:
    if ext_score is None:
        return rank
    if score >= 90 and ext_score >= 85:
        return "S"
    if score >= 84 and ext_score >= 75 and rank not in {"S", "A"}:
        return "A"
    return rank


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
        ext_score, bonus = external_score(row)
        item["externalSignals"] = row
        item["externalSignalScore"] = ext_score
        item["externalScoreBonus"] = bonus
        if ext_score is not None:
            new_score = int(round(clamp(float(item.get("score") or 0) + bonus, 0, 100)))
            item["baseScoreBeforeExternal"] = item.get("score")
            item["score"] = new_score
            item["rank"] = maybe_promote_rank(str(item.get("rank") or "D"), new_score, ext_score)
        matched += 1

    report["externalSignals"] = {
        "source": str(SIGNALS.relative_to(ROOT)),
        "matchedCandidates": matched,
        "availableRows": len(signals),
        "fields": FIELDS,
    }
    report["candidates"] = sorted(report.get("candidates", []), key=lambda x: int(x.get("score") or 0), reverse=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["externalSignals"], ensure_ascii=False))


if __name__ == "__main__":
    main()
