from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"
LATEST = REPORT_DIR / "latest.json"
PREVIOUS = REPORT_DIR / "sector_strength_previous.json"
HISTORY = REPORT_DIR / "sector_strength_history.json"


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def rounded(value: Any, digits: int = 1) -> float | None:
    result = number(value)
    return round(result, digits) if result is not None else None


def median_of(values: list[Any]) -> float:
    valid = [number(value) for value in values]
    valid = [value for value in valid if value is not None]
    return round(median(valid), 1) if valid else 0.0


def average_of(values: list[Any]) -> float:
    valid = [number(value) for value in values]
    valid = [value for value in valid if value is not None]
    return round(sum(valid) / len(valid), 1) if valid else 0.0


def percentile_map(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
    valid = [(row["key"], number(row.get(key))) for row in rows]
    valid = [(row_key, value) for row_key, value in valid if value is not None]
    if not valid:
        return {}
    ordered = sorted(valid, key=lambda item: item[1])
    if len(ordered) == 1:
        return {ordered[0][0]: 50.0}
    return {
        row_key: round(1 + 98 * index / (len(ordered) - 1), 1)
        for index, (row_key, _) in enumerate(ordered)
    }


def load_history() -> dict[str, Any]:
    if not HISTORY.exists():
        return {"snapshots": []}
    try:
        payload = json.loads(HISTORY.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("snapshots"), list):
            return payload
    except Exception:
        pass
    return {"snapshots": []}


def group_candidates(candidates: list[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        market = item.get("market") or "-"
        label = item.get(field) or item.get("theme") or item.get("sector") or "未分類"
        groups[f"{market}|{label}"].append(item)
    return groups


def build_rows(candidates: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    by_market: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        by_market[item.get("market") or "-"].append(item)

    market_baselines: dict[str, dict[str, float]] = {}
    for market, items in by_market.items():
        market_baselines[market] = {
            "ret20": median_of([(item.get("metrics") or {}).get("ret20Pct") for item in items]),
            "ret60": median_of([(item.get("metrics") or {}).get("ret60Pct") for item in items]),
            "ret120": median_of([(item.get("metrics") or {}).get("ret120Pct") for item in items]),
            "breadth50": average_of([
                100 if number((item.get("metrics") or {}).get("price")) and number((item.get("metrics") or {}).get("ma50"))
                and number((item.get("metrics") or {}).get("price")) > number((item.get("metrics") or {}).get("ma50")) else 0
                for item in items
            ]),
        }

    rows: list[dict[str, Any]] = []
    for key, items in group_candidates(candidates, field).items():
        market, label = key.split("|", 1)
        ret20 = median_of([(item.get("metrics") or {}).get("ret20Pct") for item in items])
        ret60 = median_of([(item.get("metrics") or {}).get("ret60Pct") for item in items])
        ret120 = median_of([(item.get("metrics") or {}).get("ret120Pct") for item in items])
        base = market_baselines.get(market, {"ret20": 0, "ret60": 0, "ret120": 0, "breadth50": 0})
        breadth50 = average_of([
            100 if number((item.get("metrics") or {}).get("price")) and number((item.get("metrics") or {}).get("ma50"))
            and number((item.get("metrics") or {}).get("price")) > number((item.get("metrics") or {}).get("ma50")) else 0
            for item in items
        ])
        breadth200 = average_of([
            100 if number((item.get("metrics") or {}).get("price")) and number((item.get("metrics") or {}).get("ma200"))
            and number((item.get("metrics") or {}).get("price")) > number((item.get("metrics") or {}).get("ma200")) else 0
            for item in items
        ])
        rs70_breadth = average_of([
            100 if (number((item.get("metrics") or {}).get("rsRating")) or 0) >= 70 else 0
            for item in items
        ])
        leaders = sorted(
            items,
            key=lambda item: (
                number((item.get("metrics") or {}).get("rsRating")) or 0,
                number(item.get("score")) or 0,
            ),
            reverse=True,
        )[:8]
        rows.append({
            "key": key,
            "market": market,
            "name": label,
            "sector": label if field == "sector" else None,
            "theme": label if field == "theme" else None,
            "count": len(items),
            "confidence": "high" if len(items) >= 20 else "medium" if len(items) >= 8 else "low",
            "ret20": ret20,
            "ret60": ret60,
            "ret120": ret120,
            "marketRet20": base["ret20"],
            "marketRet60": base["ret60"],
            "marketRet120": base["ret120"],
            "rs20": round(ret20 - base["ret20"], 1),
            "rs60": round(ret60 - base["ret60"], 1),
            "rs120": round(ret120 - base["ret120"], 1),
            "breadth50": breadth50,
            "breadth200": breadth200,
            "rs70Breadth": rs70_breadth,
            "marketBreadth50": base["breadth50"],
            "atr": average_of([(item.get("metrics") or {}).get("atrPct") for item in items]),
            "turnover": round(sum(number((item.get("metrics") or {}).get("avgTradingValue20Usd")) or 0 for item in items), 0),
            "sCount": sum(1 for item in items if item.get("rank") == "S"),
            "aCount": sum(1 for item in items if item.get("rank") == "A"),
            "bCount": sum(1 for item in items if item.get("rank") == "B"),
            "actionable": sum(1 for item in items if item.get("setupType") in {"vcp_ready", "breakout_ready", "pullback_ready"}),
            "leaders": [
                {
                    "symbol": item.get("symbol"), "name": item.get("name"), "rank": item.get("rank"),
                    "score": item.get("score"), "setupType": item.get("setupType"),
                    "metrics": item.get("metrics", {}), "tradePlan": item.get("tradePlan", {}),
                }
                for item in leaders
            ],
        })

    for market in {row["market"] for row in rows}:
        market_rows = [row for row in rows if row["market"] == market]
        p20 = percentile_map(market_rows, "rs20")
        p60 = percentile_map(market_rows, "rs60")
        p120 = percentile_map(market_rows, "rs120")
        breadth = percentile_map(market_rows, "breadth50")
        for row in market_rows:
            score = (
                p20.get(row["key"], 50) * 0.25
                + p60.get(row["key"], 50) * 0.35
                + p120.get(row["key"], 50) * 0.25
                + breadth.get(row["key"], 50) * 0.15
            )
            if row["confidence"] == "low":
                score = 50 + (score - 50) * 0.65
            row["rsScore"] = round(score, 1)
            row["strength"] = row["rsScore"]
    return sorted(rows, key=lambda row: (number(row.get("rsScore")) or 0, row.get("count", 0)), reverse=True)


def attach_history(rows: list[dict[str, Any]], snapshots: list[dict[str, Any]]) -> None:
    prior_snapshots = snapshots[:-1] if snapshots else []
    previous = prior_snapshots[-1].get("rows", []) if prior_snapshots else []
    five_back = prior_snapshots[-5].get("rows", []) if len(prior_snapshots) >= 5 else []
    previous_map = {row.get("key"): row for row in previous}
    five_map = {row.get("key"): row for row in five_back}
    history_maps = [{row.get("key"): row for row in snapshot.get("rows", [])} for snapshot in snapshots[-20:]]

    for row in rows:
        key = row["key"]
        current = number(row.get("rsScore")) or 0
        previous_score = number((previous_map.get(key) or {}).get("rsScore"))
        five_score = number((five_map.get(key) or {}).get("rsScore"))
        row["previousRsScore"] = rounded(previous_score, 1)
        row["change1d"] = round(current - previous_score, 1) if previous_score is not None else None
        row["change5d"] = round(current - five_score, 1) if five_score is not None else None
        row["sparkline"] = [
            rounded((history_map.get(key) or {}).get("rsScore"), 1)
            for history_map in history_maps
            if number((history_map.get(key) or {}).get("rsScore")) is not None
        ]
        change = row.get("change5d") if row.get("change5d") is not None else row.get("change1d")
        if current >= 70 and (change is None or change >= 0):
            row["phase"] = "leading"
        elif current >= 50 and (change or 0) > 0:
            row["phase"] = "improving"
        elif current < 50 and (change or 0) < 0:
            row["phase"] = "lagging"
        else:
            row["phase"] = "weakening"


def compact_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = ["key", "market", "name", "rsScore", "ret20", "ret60", "ret120", "breadth50", "count"]
    return [{key: row.get(key) for key in keys} for row in rows]


def main() -> None:
    report = json.loads(LATEST.read_text(encoding="utf-8"))
    candidates = report.get("candidates") or []
    sector_rows = build_rows(candidates, "sector")
    theme_rows = build_rows(candidates, "theme")

    history = load_history()
    snapshots = history.get("snapshots", [])
    snapshot_date = str(report.get("generatedAt") or datetime.now(timezone.utc).isoformat())[:10]
    snapshot = {
        "date": snapshot_date,
        "generatedAt": report.get("generatedAt"),
        "rows": compact_rows(sector_rows),
    }
    snapshots = [item for item in snapshots if item.get("date") != snapshot_date]
    snapshots.append(snapshot)
    snapshots = snapshots[-60:]
    history["snapshots"] = snapshots

    attach_history(sector_rows, snapshots)
    report["sectorStrength"] = sector_rows
    report["themeStrength"] = theme_rows
    report["sectorRelativeStrength"] = {
        "definition": "同一市場の中央値に対する20/60/120日相対リターンと50日線上銘柄比率を、市場内パーセンタイル化して合成",
        "weights": {"rs20": 0.25, "rs60": 0.35, "rs120": 0.25, "breadth50": 0.15},
        "interpretation": "RS 70以上は市場内上位、50前後は中立、30以下は劣後。構成銘柄8未満は信頼度低。",
    }
    report["sectorStrengthPreviousAvailable"] = len(snapshots) > 1

    LATEST.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    HISTORY.write_text(json.dumps(history, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    PREVIOUS.write_text(json.dumps({"generatedAt": report.get("generatedAt"), "sectorStrength": sector_rows}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"sectorRows": len(sector_rows), "themeRows": len(theme_rows), "historySnapshots": len(snapshots)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
