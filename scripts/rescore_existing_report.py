from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from screener_data import REPORT_DIR, finite, read_input_rows, rounded
from screener_metrics import preference_match
from screener_report import build_themes, market_summary
from screener_scoring import enrich_market_candidates

LATEST = REPORT_DIR / "latest.json"
DYNAMIC_WARNINGS = {"RS不足", "出来高確認待ち", "ベース深さ過大"}


def refresh_metadata(candidate: dict[str, Any], metadata: dict[str, str]) -> dict[str, Any]:
    result = dict(candidate)
    for key in ("name", "market", "sector", "industry", "theme", "note"):
        if metadata.get(key):
            result[key] = metadata[key]
    result["preferenceMatch"] = preference_match({key: str(result.get(key) or "") for key in ("name", "sector", "industry", "theme")})
    warnings = [warning for warning in result.get("warnings", []) if warning not in DYNAMIC_WARNINGS]
    base_depth = finite((result.get("metrics") or {}).get("baseDepth60Pct"))
    if base_depth is not None and base_depth > 40:
        warnings.append("ベース深さ過大")
    result["warnings"] = list(dict.fromkeys(warnings))
    return result


def summary_for(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    ranks: dict[str, int] = defaultdict(int)
    setups: dict[str, int] = defaultdict(int)
    for item in candidates:
        ranks[str(item.get("rank") or "D")] += 1
        setups[str(item.get("setupType") or "watch_only")] += 1
    return {
        "total": len(candidates),
        "sRank": ranks["S"],
        "aRank": ranks["A"],
        "bRank": ranks["B"],
        "actionable": sum(
            1 for item in candidates
            if item.get("setupType") in {"vcp_ready", "breakout_ready", "pullback_ready"}
            and item.get("rank") in {"S", "A", "B"}
        ),
        "vcpReady": setups["vcp_ready"],
        "breakoutReady": setups["breakout_ready"],
        "pullbackReady": setups["pullback_ready"],
        "extended": setups["extended"],
        "avoid": setups["avoid"],
        "averageScore": rounded(np.mean([finite(item.get("score")) or 0 for item in candidates]), 1) if candidates else 0,
    }


def main() -> None:
    report = json.loads(LATEST.read_text(encoding="utf-8"))
    rows, _ = read_input_rows()
    metadata = {row["symbol"]: row for row in rows}
    grouped: dict[str, list[dict[str, Any]]] = {"JP": [], "US": []}
    for candidate in report.get("candidates", []):
        refreshed = refresh_metadata(candidate, metadata.get(str(candidate.get("symbol"))) or {})
        grouped.setdefault(str(refreshed.get("market") or "US"), []).append(refreshed)

    rescored_by_market = {market: enrich_market_candidates(items) for market, items in grouped.items()}
    candidates = sorted(
        rescored_by_market.get("JP", []) + rescored_by_market.get("US", []),
        key=lambda item: (finite(item.get("score")) or 0, finite((item.get("metrics") or {}).get("rsRating")) or 0),
        reverse=True,
    )
    previous_market_summary = report.get("marketSummary") or {}
    refreshed_market_summary: dict[str, Any] = {}
    for market in ("JP", "US"):
        items = rescored_by_market.get(market, [])
        row = market_summary([{"symbol": str(item.get("symbol"))} for item in items], items, items)
        previous = previous_market_summary.get(market) or {}
        for key in ("universeRows", "builtRows", "downloadedRows", "missingRows", "missingSymbols", "coveragePct"):
            if key in previous:
                row[key] = previous[key]
        refreshed_market_summary[market] = row

    report.update({
        "schemaVersion": 4,
        "marketSummary": refreshed_market_summary,
        "marketDataAsOf": {market: row.get("asOf") for market, row in refreshed_market_summary.items()},
        "summary": summary_for(candidates),
        "candidates": candidates,
        "themes": build_themes(candidates),
        "jquantsStatus": {
            "enabled": False,
            "status": "not_used_in_bulk_mode",
            "message": "1000銘柄版は日米を同条件で一括取得できるyfinanceを使用。J-Quants認証情報は現在の処理では使用しません。",
        },
        "methodology": {
            "model": "Technical SEPA/VCP v4",
            "scoreComponents": {"trend": 25, "relativeStrength": 20, "vcp": 25, "volume": 10, "risk": 10, "liquidity": 10},
            "themeInScore": False,
            "limitations": [
                "決算・EPS・売上成長率は未取得",
                "ニュース材料と次回決算日は未評価",
                "VCPは固定期間の値幅収縮による一次判定",
                "ピボットと無効化水準は機械計算のためチャート確認必須",
                "追跡成績は検出日の終値を基準に日次終値で更新",
            ],
        },
        "rescoredFromExistingData": True,
    })
    report.pop("candidatesByMarket", None)
    report.pop("topTurnoverByMarket", None)
    LATEST.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"generatedAtPreserved": report.get("generatedAt"), "summary": report["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
