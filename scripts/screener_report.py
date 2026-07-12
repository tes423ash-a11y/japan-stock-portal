from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

from screener_data import finite, rounded


def top_by_metric(candidates: list[dict[str, Any]], top_n: int, metric: str) -> list[dict[str, Any]]:
    return sorted(candidates, key=lambda item: finite((item.get("metrics") or {}).get(metric)) or 0, reverse=True)[:top_n]


def build_themes(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        groups[item.get("theme") or item.get("sector") or "未分類"].append(item)
    rows = []
    for name, items in groups.items():
        scores = [finite(item.get("score")) or 0 for item in items]
        leaders = sorted(items, key=lambda item: finite(item.get("score")) or 0, reverse=True)[:5]
        rows.append({
            "name": name, "strength": rounded(np.median(scores), 1) if scores else 0, "count": len(items),
            "leaders": [item.get("symbol") for item in leaders],
            "note": {
                "S": sum(1 for item in items if item.get("rank") == "S"),
                "A": sum(1 for item in items if item.get("rank") == "A"),
                "ready": sum(1 for item in items if item.get("setupType") in {"vcp_ready", "breakout_ready", "pullback_ready"}),
            },
        })
    return sorted(rows, key=lambda row: (finite(row.get("strength")) or 0, row.get("count", 0)), reverse=True)


def usable_coverage(requested: int, built: list[dict[str, Any]], provider_downloaded: int = 0) -> dict[str, Any]:
    missing_symbols = sorted({
        str(item.get("symbol"))
        for item in built
        if item.get("symbol") and (item.get("dataQuality") or {}).get("status") == "missing"
    })
    usable = sum(1 for item in built if (item.get("dataQuality") or {}).get("status") != "missing")
    usable = min(requested, usable)
    coverage_pct = rounded(usable / requested * 100, 1) if requested else 0
    return {
        "requested": requested,
        "providerDownloaded": provider_downloaded,
        "usable": usable,
        "downloaded": usable,
        "missing": max(0, requested - usable),
        "missingSymbols": missing_symbols,
        "coveragePct": coverage_pct,
        "status": "good" if coverage_pct >= 95 else "degraded" if coverage_pct >= 80 else "poor",
    }


def market_summary(universe: list[dict[str, str]], built: list[dict[str, Any]], selected: list[dict[str, Any]]) -> dict[str, Any]:
    ranks = defaultdict(int); setups = defaultdict(int)
    for item in selected:
        ranks[item.get("rank") or "D"] += 1
        setups[item.get("setupType") or "watch_only"] += 1
    downloaded = [item for item in built if (item.get("dataQuality") or {}).get("status") != "missing"]
    as_of_dates = sorted({
        str((item.get("dataQuality") or {}).get("asOf"))
        for item in downloaded
        if (item.get("dataQuality") or {}).get("asOf")
    })
    missing_symbols = [str(item.get("symbol")) for item in built if (item.get("dataQuality") or {}).get("status") == "missing"]
    return {
        "universeRows": len(universe), "builtRows": len(built), "selectedRows": len(selected),
        "downloadedRows": len(downloaded), "missingRows": len(missing_symbols), "missingSymbols": missing_symbols,
        "asOf": as_of_dates[-1] if as_of_dates else None,
        "sRank": ranks["S"], "aRank": ranks["A"], "bRank": ranks["B"],
        "averageScore": rounded(np.mean([finite(item.get("score")) or 0 for item in selected]), 1) if selected else 0,
        "fullHistoryRows": sum(1 for item in selected if (item.get("dataQuality") or {}).get("status") == "full"),
        "coveragePct": rounded(len(downloaded) / len(universe) * 100, 1) if universe else 0,
        "setupCounts": dict(setups),
    }


def write_markdown(report: dict[str, Any]) -> str:
    coverage = report.get("coverage") or {}
    lines = [
        "# Daily Technical SEPA/VCP Report", "", f"Generated: {report.get('generatedAt')}", "", "## Coverage", "",
        f"- Requested: {coverage.get('requested')}", f"- Downloaded: {coverage.get('downloaded')}", f"- Coverage: {coverage.get('coveragePct')}%", "",
        "## Methodology", "", "- Trend template, market-relative strength, VCP quality, volume, risk and liquidity.",
        "- Theme preference is displayed separately and does not inflate the technical score.",
        "- Fundamentals and earnings acceleration are not included; this is not a complete SEPA/CAN SLIM model.", "", "## Top actionable candidates", "",
    ]
    actionable = [item for item in report.get("candidates", []) if item.get("rank") in {"S", "A"}]
    for item in actionable[:40]:
        metrics = item.get("metrics") or {}; plan = item.get("tradePlan") or {}
        lines.append(f"- {item.get('rank')} {item.get('score')} | {item.get('market')} {item.get('symbol')} {item.get('name')} | {item.get('setup')} | RS {metrics.get('rsRating')} | VCP {item.get('vcpScore')} | Zone {plan.get('entryLow')}-{plan.get('entryHigh')} | Invalidation {plan.get('stop')}")
    return "\n".join(lines) + "\n"
