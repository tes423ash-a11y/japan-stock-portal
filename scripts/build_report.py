from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCHLISTS = [ROOT / "watchlists" / "jp_candidates.csv", ROOT / "watchlists" / "us_candidates.csv"]
REPORT_DIR = ROOT / "reports"


def read_watchlists() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in WATCHLISTS:
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if row.get("symbol"):
                    rows.append(row)
    return rows


def build_candidate(row: dict[str, str], index: int) -> dict[str, object]:
    base_score = max(50, 90 - index * 4)
    rank = "A" if base_score >= 80 else "B" if base_score >= 65 else "C"
    return {
        "symbol": row.get("symbol", ""),
        "code": row.get("symbol", ""),
        "name": row.get("name", "名称未設定"),
        "market": row.get("market", ""),
        "theme": row.get("theme", "未分類"),
        "rank": rank,
        "score": base_score,
        "setup": "manual watchlist",
        "price": "",
        "pivot": "",
        "stop": "",
        "target1": "",
        "target2": "",
        "rr": "",
        "riskLabel": "未計算",
        "action": "チャート確認",
        "reasons": [row.get("note", "watchlist candidate")],
    }


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_watchlists()
    candidates = [build_candidate(row, i) for i, row in enumerate(rows)]
    summary = {
        "total": len(candidates),
        "aRank": sum(1 for item in candidates if item["rank"] == "A"),
        "breakoutReady": 0,
        "pullbackReady": 0,
        "averageScore": round(sum(int(item["score"]) for item in candidates) / len(candidates), 1) if candidates else 0,
    }
    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "universe": "watchlists",
        "summary": summary,
        "candidates": candidates,
        "themes": [],
        "tracking": [],
    }
    (REPORT_DIR / "latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORT_DIR / "latest.md").write_text("# Daily Screener Report\n\nGenerated report JSON: `reports/latest.json`\n", encoding="utf-8")


if __name__ == "__main__":
    main()
