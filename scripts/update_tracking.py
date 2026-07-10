from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"
LATEST = REPORT_DIR / "latest.json"
TRACKING = REPORT_DIR / "candidate_tracking.json"
READY_SETUPS = {"vcp_ready", "breakout_ready", "pullback_ready"}


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def rounded(value: Any, digits: int = 1) -> float | None:
    result = number(value)
    return round(result, digits) if result is not None else None


def load_tracking() -> list[dict[str, Any]]:
    if not TRACKING.exists():
        return []
    try:
        payload = json.loads(TRACKING.read_text(encoding="utf-8"))
        rows = payload.get("records", []) if isinstance(payload, dict) else []
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def status_for(record: dict[str, Any]) -> str:
    max_gain = number(record.get("maxGainPct")) or 0
    max_drawdown = number(record.get("maxDrawdownPct")) or 0
    risk = number(record.get("initialRiskPct")) or 7
    if max_gain >= risk * 3:
        return "3R達成"
    if max_gain >= risk * 2:
        return "2R達成"
    if max_drawdown <= -risk:
        return "損切り到達"
    return "追跡中"


def main() -> None:
    report = json.loads(LATEST.read_text(encoding="utf-8"))
    candidates = report.get("candidates") or []
    generated = str(report.get("generatedAt") or datetime.utcnow().isoformat())
    today = generated[:10]
    current_by_symbol = {item.get("symbol"): item for item in candidates if item.get("symbol")}
    records = load_tracking()

    updated: list[dict[str, Any]] = []
    seen_active: set[str] = set()
    for record in records:
        symbol = record.get("symbol")
        detected_at = str(record.get("detectedAt") or today)
        try:
            age = (date.fromisoformat(today) - date.fromisoformat(detected_at)).days
        except ValueError:
            age = 999
        if age > 180:
            continue
        item = current_by_symbol.get(symbol)
        entry = number(record.get("entryPrice"))
        if item and entry:
            price = number(item.get("price")) or number((item.get("metrics") or {}).get("price"))
            if price:
                gain = (price / entry - 1) * 100
                record["currentPrice"] = rounded(price, 2)
                record["currentGainPct"] = rounded(gain, 1)
                record["maxGainPct"] = rounded(max(number(record.get("maxGainPct")) or gain, gain), 1)
                record["maxDrawdownPct"] = rounded(min(number(record.get("maxDrawdownPct")) or gain, gain), 1)
                record["lastUpdated"] = today
                record["days"] = age
                record["currentRank"] = item.get("rank")
                record["currentSetupType"] = item.get("setupType")
        record["status"] = status_for(record)
        updated.append(record)
        seen_active.add(f"{symbol}|{detected_at}")

    new_candidates = [
        item for item in candidates
        if item.get("rank") in {"S", "A"} and item.get("setupType") in READY_SETUPS
    ][:30]
    for item in new_candidates:
        symbol = item.get("symbol")
        record_key = f"{symbol}|{today}"
        if not symbol or record_key in seen_active:
            continue
        plan = item.get("tradePlan") or {}
        entry = number(plan.get("entryReference")) or number(item.get("price"))
        if not entry:
            continue
        risk = number(plan.get("riskPct")) or 7
        updated.append({
            "id": record_key,
            "symbol": symbol,
            "name": item.get("name"),
            "market": item.get("market"),
            "sector": item.get("sector"),
            "detectedAt": today,
            "lastUpdated": today,
            "days": 0,
            "detectedRank": item.get("rank"),
            "detectedScore": item.get("score"),
            "detectedSetupType": item.get("setupType"),
            "currentRank": item.get("rank"),
            "currentSetupType": item.get("setupType"),
            "entryPrice": rounded(entry, 2),
            "initialStop": rounded(plan.get("stop"), 2),
            "initialRiskPct": rounded(risk, 1),
            "currentPrice": rounded(item.get("price"), 2),
            "currentGainPct": 0.0,
            "maxGainPct": 0.0,
            "maxDrawdownPct": 0.0,
            "status": "追跡中",
        })

    updated = sorted(updated, key=lambda row: (str(row.get("detectedAt")), number(row.get("detectedScore")) or 0), reverse=True)[:600]
    report["tracking"] = updated[:120]
    report["trackingSummary"] = {
        "total": len(updated),
        "tracking": sum(1 for row in updated if row.get("status") == "追跡中"),
        "twoR": sum(1 for row in updated if row.get("status") in {"2R達成", "3R達成"}),
        "stopped": sum(1 for row in updated if row.get("status") == "損切り到達"),
    }
    TRACKING.write_text(json.dumps({"records": updated}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    LATEST.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(report["trackingSummary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
