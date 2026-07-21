from __future__ import annotations

import json
from pathlib import Path
from typing import Any


METRIC_KEYS = (
    "price", "ma20", "ma50", "ma150", "ma200", "ma200Slope20dPct",
    "ret5Pct", "ret20Pct", "ret60Pct", "ret120Pct", "ret252Pct",
    "rs20Rating", "rs60Rating", "rs120Rating", "rs252Rating", "rsRating",
    "atrPct", "drawdownFromHighPct", "distanceToPivotPct", "baseDepth60Pct",
    "range60Pct", "range30Pct", "range15Pct", "tightness10Pct", "contractionSequence",
    "volumeDryUp5vs50", "latestVolumeRatio20", "avgVolume20", "latestVolume",
    "avgTradingValue20", "avgTradingValue20Usd", "latestTradingValue", "latestTradingValueUsd",
    "closeLocation20Pct", "extendedFromMa20Pct", "extendedFromMa50Pct",
    "high52w", "low52w", "pivot", "recentLow10", "bars",
)


def compact_candidate(item: dict[str, Any]) -> dict[str, Any]:
    metrics = item.get("metrics") or {}
    quality = item.get("dataQuality") or {}
    plan = item.get("tradePlan") or {}
    return {
        "symbol": item.get("symbol"),
        "code": item.get("code"),
        "name": item.get("name"),
        "market": item.get("market"),
        "sector": item.get("sector"),
        "industry": item.get("industry"),
        "theme": item.get("theme"),
        "preferenceMatch": bool(item.get("preferenceMatch")),
        "price": item.get("price"),
        "rank": item.get("rank"),
        "score": item.get("score"),
        "setupType": item.get("setupType"),
        "componentScores": item.get("componentScores") or {},
        "trendTemplate": item.get("trendTemplate") or {},
        "vcpScore": item.get("vcpScore"),
        "tradePlan": {
            key: plan.get(key)
            for key in ("entryLow", "entryHigh", "entryReference", "stop", "riskPct", "target1", "target2")
        },
        "dataQuality": {
            key: quality.get(key)
            for key in ("status", "bars", "asOf", "staleDays")
        },
        "metrics": {key: metrics.get(key) for key in METRIC_KEYS},
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def write_shared_feeds(
    report_dir: Path,
    generated_at: str,
    model: str,
    built_by_market: dict[str, list[dict[str, Any]]],
    selected_by_market: dict[str, list[dict[str, Any]]],
    market_summaries: dict[str, dict[str, Any]],
    top_n: int,
) -> dict[str, Any]:
    shared_dir = report_dir / "shared"
    files: dict[str, str] = {}
    top_rows: list[dict[str, Any]] = []
    market_manifest: dict[str, Any] = {}

    for market in ("JP", "US"):
        built = built_by_market.get(market, [])
        compact = [compact_candidate(item) for item in sorted(built, key=lambda row: str(row.get("symbol") or ""))]
        usable = sum(1 for item in compact if (item.get("dataQuality") or {}).get("status") != "missing")
        filename = f"{market.lower()}-base.json"
        files[market] = f"reports/shared/{filename}"
        write_json(shared_dir / filename, {
            "schemaVersion": 1,
            "generatedAt": generated_at,
            "model": model,
            "market": market,
            "screenedRows": len(compact),
            "usableRows": usable,
            "asOf": (market_summaries.get(market) or {}).get("asOf"),
            "rows": compact,
        })

        selected = sorted(
            selected_by_market.get(market, []),
            key=lambda row: (float(row.get("score") or 0), float((row.get("metrics") or {}).get("rsRating") or 0)),
            reverse=True,
        )[:top_n]
        top_rows.extend(compact_candidate(item) for item in selected)
        market_manifest[market] = {
            "screenedRows": len(compact),
            "usableRows": usable,
            "publishedTopRows": len(selected),
            "asOf": (market_summaries.get(market) or {}).get("asOf"),
            "basePath": files[market],
        }

    top_path = "reports/shared/technical-top.json"
    write_json(report_dir / "shared" / "technical-top.json", {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "model": model,
        "topNPerMarket": top_n,
        "markets": market_manifest,
        "candidates": top_rows,
    })

    manifest = {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "model": model,
        "architecture": "shared-base-metrics-with-strategy-specific-ranking",
        "markets": market_manifest,
        "technicalTopPath": top_path,
    }
    write_json(report_dir / "shared" / "manifest.json", manifest)
    return manifest
