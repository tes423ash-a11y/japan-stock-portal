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
TRACKING_SCHEMA_VERSION = 2


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
        if not isinstance(payload, dict) or payload.get("schemaVersion") != TRACKING_SCHEMA_VERSION:
            return []
        rows = payload.get("records", [])
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


def session_date(item: dict[str, Any] | None, fallback: str) -> str:
    value = str(((item or {}).get("dataQuality") or {}).get("asOf") or fallback)
    try:
        date.fromisoformat(value)
        return value
    except ValueError:
        return fallback


def update_extremes(record: dict[str, Any], gain: float) -> None:
    previous_gain = number(record.get("maxGainPct"))
    previous_drawdown = number(record.get("maxDrawdownPct"))
    record["maxGainPct"] = rounded(max(0.0 if previous_gain is None else previous_gain, gain), 1)
    record["maxDrawdownPct"] = rounded(min(0.0 if previous_drawdown is None else previous_drawdown, gain), 1)


def main() -> None:
    report = json.loads(LATEST.read_text(encoding="utf-8"))
    candidates = report.get("candidates") or []
    generated = str(report.get("generatedAt") or datetime.utcnow().isoformat())
    report_date = generated[:10]
    current_by_symbol = {item.get("symbol"): item for item in candidates if item.get("symbol")}
    records = load_tracking()

    updated: list[dict[str, Any]] = []
    active_symbols: set[str] = set()
    existing_keys: set[str] = set()
    for record in records:
        symbol = record.get("symbol")
        item = current_by_symbol.get(symbol)
        current_session = session_date(item, report_date)
        detected_at = str(record.get("detectedAt") or current_session)
        try:
            age = (date.fromisoformat(current_session) - date.fromisoformat(detected_at)).days
        except ValueError:
            age = 999
        if age > 180:
            continue
        entry = number(record.get("entryPrice"))
        if item and entry:
            price = number(item.get("price")) or number((item.get("metrics") or {}).get("price"))
            if price:
                gain = (price / entry - 1) * 100
                record["currentPrice"] = rounded(price, 2)
                record["currentGainPct"] = rounded(gain, 1)
                update_extremes(record, gain)
                record["lastUpdated"] = current_session
                record["days"] = age
                record["name"] = item.get("name")
                record["market"] = item.get("market")
                record["sector"] = item.get("sector")
                record["currentRank"] = item.get("rank")
                record["currentSetupType"] = item.get("setupType")
        record["status"] = status_for(record)
        updated.append(record)
        existing_keys.add(f"{symbol}|{detected_at}")
        if record["status"] == "追跡中" and symbol:
            active_symbols.add(str(symbol))

    new_candidates = [
        item for item in candidates
        if item.get("rank") in {"S", "A"} and item.get("setupType") in READY_SETUPS
    ][:30]
    for item in new_candidates:
        symbol = item.get("symbol")
        detected_at = session_date(item, report_date)
        record_key = f"{symbol}|{detected_at}"
        if not symbol or str(symbol) in active_symbols or record_key in existing_keys:
            continue
        plan = item.get("tradePlan") or {}
        entry = number(item.get("price")) or number((item.get("metrics") or {}).get("price"))
        if not entry:
            continue
        risk = number(plan.get("riskPct")) or 7
        updated.append({
            "id": record_key,
            "symbol": symbol,
            "name": item.get("name"),
            "market": item.get("market"),
            "sector": item.get("sector"),
            "detectedAt": detected_at,
            "lastUpdated": detected_at,
            "days": 0,
            "detectedRank": item.get("rank"),
            "detectedScore": item.get("score"),
            "detectedSetupType": item.get("setupType"),
            "currentRank": item.get("rank"),
            "currentSetupType": item.get("setupType"),
            "entryPrice": rounded(entry, 2),
            "entryBasis": "detection_close",
            "plannedEntryPrice": rounded(plan.get("entryReference"), 2),
            "outcomeBasis": "daily_close_from_detection",
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
        "basis": "検出日の終値を基準に日次終値で更新",
    }
    TRACKING.write_text(json.dumps({"schemaVersion": TRACKING_SCHEMA_VERSION, "records": updated}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    LATEST.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(report["trackingSummary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
