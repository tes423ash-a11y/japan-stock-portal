from __future__ import annotations

import csv
import json
from collections import defaultdict
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
                symbol = (row.get("symbol") or "").strip()
                if symbol:
                    rows.append({key: (value or "").strip() for key, value in row.items()})
    return rows


def rank_from_score(score: int) -> str:
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    return "D"


def build_candidate(row: dict[str, str], index: int) -> dict[str, object]:
    score = max(55, 92 - index * 5)
    symbol = row.get("symbol", "")
    market = row.get("market", "")
    setup = "VCP watch" if score >= 80 else "Pullback watch" if score >= 65 else "Watch only"
    action = "Priority review" if score >= 80 else "Wait for setup"
    return {
        "symbol": symbol,
        "code": symbol.replace(".T", ""),
        "name": row.get("name", "Unnamed"),
        "market": market,
        "theme": row.get("theme", "Uncategorized"),
        "rank": rank_from_score(score),
        "score": score,
        "setup": setup,
        "price": "",
        "pivot": "",
        "stop": "",
        "target1": "",
        "target2": "",
        "rr": "",
        "riskLabel": "Not calculated",
        "action": action,
        "reasons": [row.get("note", "watchlist candidate")],
    }


def build_themes(candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in candidates:
        grouped[str(item.get("theme") or "Uncategorized")].append(item)

    themes = []
    for theme, items in grouped.items():
        average = sum(int(item.get("score", 0)) for item in items) / len(items)
        leaders = [str(item.get("symbol")) for item in sorted(items, key=lambda x: int(x.get("score", 0)), reverse=True)[:3]]
        themes.append({
            "name": theme,
            "strength": round(average, 1),
            "leaders": leaders,
            "note": f"{len(items)} candidates in watchlist",
        })
    return sorted(themes, key=lambda item: float(item["strength"]), reverse=True)


def write_markdown(report: dict[str, object]) -> str:
    candidates = report.get("candidates", [])
    lines = ["# Daily Screener Report", "", f"Generated: {report['generatedAt']}", "", "## Top Candidates", ""]
    for item in candidates[:10]:
        lines.append(f"- {item['rank']} / {item['score']} / {item['symbol']} / {item['name']} / {item['theme']}")
    lines.append("")
    lines.append("Dashboard input: `reports/latest.json`")
    return "\n".join(lines) + "\n"


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_watchlists()
    candidates = [build_candidate(row, i) for i, row in enumerate(rows)]
    average_score = round(sum(int(item["score"]) for item in candidates) / len(candidates), 1) if candidates else 0
    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "universe": "watchlists",
        "summary": {
            "total": len(candidates),
            "aRank": sum(1 for item in candidates if item["rank"] == "A"),
            "breakoutReady": sum(1 for item in candidates if "VCP" in str(item.get("setup"))),
            "pullbackReady": sum(1 for item in candidates if "Pullback" in str(item.get("setup"))),
            "averageScore": average_score,
        },
        "candidates": candidates,
        "themes": build_themes(candidates),
        "tracking": [],
    }
    (REPORT_DIR / "latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORT_DIR / "latest.md").write_text(write_markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
