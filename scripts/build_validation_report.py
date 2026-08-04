from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from screener_data import download_history, finite, read_csv_files
from trade_simulation import SimulationConfig, simulate_long_trade

ROOT = Path(__file__).resolve().parents[1]
TRACKING = ROOT / "reports" / "candidate_tracking.json"
OUTPUT = ROOT / "reports" / "validation.json"
HISTORICAL_UNIVERSE = ROOT / "data" / "historical_universe.csv"
READY_SETUPS = {"vcp_ready", "breakout_ready", "pullback_ready"}


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def env_bool(name: str, default: bool = False) -> bool:
    return str(os.getenv(name, str(default))).strip().lower() in {"1", "true", "yes", "on"}


def load_records() -> list[dict[str, Any]]:
    if not TRACKING.exists():
        return []
    payload = json.loads(TRACKING.read_text(encoding="utf-8"))
    records = payload.get("records") if isinstance(payload, dict) else []
    return records if isinstance(records, list) else []


def current_universe_symbols() -> set[str]:
    paths = list((ROOT / "universes").glob("*.csv"))
    return {str(row.get("symbol") or "").upper() for row in read_csv_files(paths)}


def historical_universe_events() -> dict[str, dict[str, str]]:
    if not HISTORICAL_UNIVERSE.exists():
        return {}
    events: dict[str, dict[str, str]] = {}
    with HISTORICAL_UNIVERSE.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            symbol = str(row.get("symbol") or "").strip().upper()
            if symbol:
                events[symbol] = {key: str(value or "").strip() for key, value in row.items() if key}
    return events


def planned_target(record: dict[str, Any], stop: float) -> float | None:
    explicit = finite(record.get("initialTarget1"))
    if explicit is not None:
        return explicit
    reference = finite(record.get("plannedEntryPrice")) or finite(record.get("entryPrice"))
    if reference is None or stop >= reference:
        return None
    return reference + (reference - stop) * 2


def grouped_summary(trades: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        grouped[str(trade.get(field) or "unknown")].append(trade)
    rows = []
    for label, values in grouped.items():
        closed = [item for item in values if item.get("closed") and finite(item.get("rMultiple")) is not None]
        r_values = [float(item["rMultiple"]) for item in closed]
        rows.append({
            "label": label,
            "total": len(values),
            "closed": len(closed),
            "winRatePct": round(sum(value > 0 for value in r_values) / len(r_values) * 100, 1) if r_values else None,
            "expectancyR": round(sum(r_values) / len(r_values), 3) if r_values else None,
        })
    return sorted(rows, key=lambda row: (row["expectancyR"] is not None, row["expectancyR"] or -999), reverse=True)


def main() -> None:
    records = [record for record in load_records() if record.get("detectedSetupType") in READY_SETUPS]
    symbols = sorted({str(record.get("symbol") or "") for record in records if record.get("symbol")})
    offline = env_bool("VALIDATION_OFFLINE")
    if symbols and not offline:
        histories, diagnostics = download_history(symbols)
    else:
        histories, diagnostics = {}, {
            "provider": "offline" if offline else "not_required",
            "requested": len(symbols),
            "downloaded": 0,
            "missing": len(symbols),
            "missingSymbols": symbols[:30],
        }
    current_symbols = current_universe_symbols()
    historical_events = historical_universe_events()
    config = SimulationConfig(
        fee_bps_per_side=max(0, env_float("VALIDATION_FEE_BPS_PER_SIDE", 5)),
        slippage_bps_per_side=max(0, env_float("VALIDATION_SLIPPAGE_BPS_PER_SIDE", 10)),
        max_hold_sessions=max(1, env_int("VALIDATION_MAX_HOLD_SESSIONS", 20)),
        target_r=max(0.5, env_float("VALIDATION_TARGET_R", 2)),
    )

    trades: list[dict[str, Any]] = []
    for record in records:
        symbol = str(record.get("symbol") or "")
        stop = finite(record.get("initialStop"))
        if not symbol or stop is None:
            continue
        event = historical_events.get(symbol) or {}
        terminal_event = "delisted" if event.get("delisted_on") else None
        result = simulate_long_trade(
            histories.get(symbol),
            str(record.get("detectedAt") or ""),
            stop,
            planned_target(record, stop),
            config=config,
            terminal_event=terminal_event,
        )
        result.update({
            "id": record.get("id"),
            "symbol": symbol,
            "name": record.get("name"),
            "market": record.get("market"),
            "setupType": record.get("detectedSetupType"),
            "detectedAt": record.get("detectedAt"),
            "detectedRank": record.get("detectedRank"),
            "detectedScore": record.get("detectedScore"),
            "universeExited": bool(current_symbols and symbol not in current_symbols),
            "terminalEvent": terminal_event,
        })
        trades.append(result)

    closed = [trade for trade in trades if trade.get("closed") and finite(trade.get("rMultiple")) is not None]
    r_values = [float(trade["rMultiple"]) for trade in closed]
    positive = sum(value for value in r_values if value > 0)
    negative = abs(sum(value for value in r_values if value < 0))
    cumulative_by_date: dict[str, float] = defaultdict(float)
    for trade in sorted(closed, key=lambda item: (str(item.get("exitDate") or ""), str(item.get("symbol") or ""))):
        cumulative_by_date[str(trade.get("exitDate"))] += float(trade.get("rMultiple") or 0)
    running = 0.0
    cumulative_r = []
    for session, value in sorted(cumulative_by_date.items()):
        running += value
        cumulative_r.append({"time": session, "value": round(running, 3)})

    historical_coverage = HISTORICAL_UNIVERSE.exists() and bool(historical_events)
    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "config": config.as_dict(),
        "methodology": {
            "signalTiming": "検出日の指標は当日まで。約定は次の取引セッション始値。",
            "costs": "売買両側で手数料とスリッページを控除。",
            "intradayAmbiguity": "同じ日足で損切りと利確の両方に触れた場合は損切りを先に約定。",
            "portfolioModel": "各トレードを独立評価。重複ポジションを含む資金曲線ではなく累積Rを表示。",
            "survivorship": "検出済みレコードは現在の母集団から消えても保持。過去時点の完全な上場母集団は別ファイルがない限り未解決。",
        },
        "summary": {
            "signals": len(trades),
            "closed": len(closed),
            "open": sum(not trade.get("closed") and trade.get("status") == "open" for trade in trades),
            "pending": sum(trade.get("status") == "pending_next_session" for trade in trades),
            "missingHistory": sum(trade.get("status") == "missing_history" for trade in trades),
            "wins": sum(value > 0 for value in r_values),
            "winRatePct": round(sum(value > 0 for value in r_values) / len(r_values) * 100, 1) if r_values else None,
            "expectancyR": round(sum(r_values) / len(r_values), 3) if r_values else None,
            "medianR": round(median(r_values), 3) if r_values else None,
            "profitFactor": round(positive / negative, 3) if negative else None,
            "cumulativeR": round(sum(r_values), 3) if r_values else 0.0,
        },
        "quality": {
            "marketData": diagnostics,
            "offlineGeneration": offline,
            "historicalUniverseCoverage": historical_coverage,
            "survivorshipStatus": "historical_universe_loaded" if historical_coverage else "prospective_only",
            "universeExitedSignals": sum(bool(trade.get("universeExited")) for trade in trades),
            "terminalEvents": sum(bool(trade.get("terminalEvent")) for trade in trades),
            "warning": "ローカルのオフライン検証レポートです。次回のGitHub Actions実行で価格を再取得します。" if offline else None if historical_coverage else "過去時点の全上場・上場廃止銘柄を完全復元していないため、長期バックテストではなく前向き検証として解釈してください。",
        },
        "byMarket": grouped_summary(trades, "market"),
        "bySetup": grouped_summary(trades, "setupType"),
        "cumulativeR": cumulative_r,
        "trades": sorted(trades, key=lambda item: (str(item.get("detectedAt") or ""), str(item.get("symbol") or "")), reverse=True)[:600],
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"summary": payload["summary"], "quality": payload["quality"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
