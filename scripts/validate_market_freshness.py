"""Fail closed when a published market is mostly from an older session."""

import json
import os
from pathlib import Path


def validate_market_freshness(report, minimum_pct=90.0, markets=("JP", "US")):
    summaries = report.get("marketSummary") or {}
    failures = []
    for market in markets:
        summary = summaries.get(market) or {}
        expected = summary.get("expectedSession")
        dominant = summary.get("dominantDate")
        coverage = summary.get("freshCoveragePct")
        if not expected or not dominant or not isinstance(coverage, (int, float)):
            failures.append(f"{market}: freshness metadata missing")
            continue
        if dominant != expected or float(coverage) < float(minimum_pct):
            failures.append(
                f"{market}: expected={expected}, dominant={dominant}, "
                f"freshCoveragePct={coverage} (minimum {minimum_pct})"
            )
    if failures:
        raise ValueError("Critical per-market freshness failure: " + "; ".join(failures))
    return {
        market: {
            "expectedSession": summaries[market]["expectedSession"],
            "dominantDate": summaries[market]["dominantDate"],
            "freshCoveragePct": summaries[market]["freshCoveragePct"],
        }
        for market in markets
    }


if __name__ == "__main__":
    path = Path(os.environ.get("REPORT_PATH", "reports/latest.json"))
    threshold = float(os.environ.get("MIN_FRESH_COVERAGE_PCT", "90"))
    result = validate_market_freshness(
        json.loads(path.read_text(encoding="utf-8")), minimum_pct=threshold
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
