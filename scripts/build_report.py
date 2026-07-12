from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import numpy as np

from screener_data import REPORT_DIR, clamp, download_history, env_float, env_int, finite, read_input_rows, rounded, split_rows_by_market
from screener_metrics import build_raw_candidate
from screener_scoring import enrich_market_candidates
from screener_report import build_themes, market_summary, top_by_metric, usable_coverage, write_markdown


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows, mode = read_input_rows()
    top_n_per_market = int(clamp(env_int("SCREENING_TOP_N", 500), 50, 600))
    max_symbols_per_market = int(clamp(env_int("SCREENING_MAX_SYMBOLS", 550), top_n_per_market, 600))
    usd_jpy = env_float("SCREENING_USDJPY", 150.0)
    turnover_metric = "latestTradingValueUsd" if mode == "top_turnover_today" else "avgTradingValue20Usd"

    universe_by_market = split_rows_by_market(rows)
    rows_by_market = {market: items[:max_symbols_per_market] for market, items in universe_by_market.items()}
    requested_symbols = [row["symbol"] for market in ["JP", "US"] for row in rows_by_market.get(market, [])]
    histories, provider_diagnostics = download_history(requested_symbols)

    built_by_market: dict[str, list[dict[str, Any]]] = {"JP": [], "US": []}
    selected_by_market: dict[str, list[dict[str, Any]]] = {"JP": [], "US": []}
    for market in ["JP", "US"]:
        raw = [build_raw_candidate(row, histories.get(row["symbol"]), usd_jpy) for row in rows_by_market.get(market, [])]
        built = enrich_market_candidates(raw)
        built_by_market[market] = built
        if mode in {"top_turnover", "top_turnover_today"}:
            selected_by_market[market] = top_by_metric(built, top_n_per_market, turnover_metric)
        else:
            selected_by_market[market] = sorted(built, key=lambda item: finite(item.get("score")) or 0, reverse=True)[:top_n_per_market]

    selected = selected_by_market["JP"] + selected_by_market["US"]
    candidates = sorted(selected, key=lambda item: (finite(item.get("score")) or 0, finite((item.get("metrics") or {}).get("rsRating")) or 0), reverse=True)
    ranks = defaultdict(int); setups = defaultdict(int)
    for item in candidates:
        ranks[item.get("rank") or "D"] += 1
        setups[item.get("setupType") or "watch_only"] += 1

    requested = len(requested_symbols)
    built_candidates = built_by_market["JP"] + built_by_market["US"]
    coverage = usable_coverage(requested, built_candidates, int(provider_diagnostics.get("downloaded", 0)))
    market_summaries = {
        market: market_summary(rows_by_market.get(market, []), built_by_market.get(market, []), selected_by_market.get(market, []))
        for market in ["JP", "US"]
    }
    report: dict[str, Any] = {
        "schemaVersion": 4,
        "rescoredFromExistingData": False,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "screeningMode": mode,
        "screeningTopNPerMarket": top_n_per_market,
        "screeningMaxSymbolsPerMarket": max_symbols_per_market,
        "universeRows": len(rows),
        "universeRowsByMarket": {market: len(items) for market, items in universe_by_market.items()},
        "inputRows": requested,
        "inputRowsByMarket": {market: len(items) for market, items in rows_by_market.items()},
        "usdJpyForTurnover": usd_jpy,
        "turnoverSortMetric": turnover_metric,
        "universe": "TOPIX500+S&P500+theme overlays",
        "providerStatus": provider_diagnostics,
        "jquantsStatus": {
            "enabled": False,
            "status": "not_used_in_bulk_mode",
            "message": "1000銘柄版は日米を同条件で一括取得できるyfinanceを使用。J-Quants認証情報は現在の処理では使用しません。",
        },
        "coverage": coverage,
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
        "summary": {
            "total": len(candidates), "sRank": ranks["S"], "aRank": ranks["A"], "bRank": ranks["B"],
            "actionable": sum(1 for item in candidates if item.get("setupType") in {"vcp_ready", "breakout_ready", "pullback_ready"} and item.get("rank") in {"S", "A", "B"}),
            "vcpReady": setups["vcp_ready"], "breakoutReady": setups["breakout_ready"], "pullbackReady": setups["pullback_ready"],
            "extended": setups["extended"], "avoid": setups["avoid"],
            "averageScore": rounded(np.mean([finite(item.get("score")) or 0 for item in candidates]), 1) if candidates else 0,
        },
        "marketSummary": market_summaries,
        "marketDataAsOf": {market: summary.get("asOf") for market, summary in market_summaries.items()},
        "candidates": candidates,
        "themes": build_themes(candidates),
        "tracking": [],
    }

    print(json.dumps({"coverage": report["coverage"], "summary": report["summary"], "marketSummary": report["marketSummary"]}, ensure_ascii=False))
    (REPORT_DIR / "latest.json").write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (REPORT_DIR / "latest.md").write_text(write_markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
