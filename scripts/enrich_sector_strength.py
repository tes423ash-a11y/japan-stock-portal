from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"
LATEST = REPORT_DIR / "latest.json"
HISTORY = REPORT_DIR / "sector_strength_previous.json"


def fnum(x):
    return x if isinstance(x, (int, float)) else None


def avg(xs):
    vals = [x for x in xs if isinstance(x, (int, float))]
    return round(sum(vals) / len(vals), 1) if vals else 0.0


def main():
    report = json.loads(LATEST.read_text(encoding="utf-8"))
    prev_rows = []
    if HISTORY.exists():
        prev_rows = json.loads(HISTORY.read_text(encoding="utf-8")).get("sectorStrength", [])
    prev = {r.get("key"): r for r in prev_rows if r.get("key")}

    groups = defaultdict(list)
    for item in report.get("candidates", []):
        key = f"{item.get('market') or '-'}|{item.get('theme') or '未分類'}"
        groups[key].append(item)

    rows = []
    for key, items in groups.items():
        market, theme = key.split("|", 1)
        leaders = sorted(items, key=lambda x: int(x.get("score") or 0), reverse=True)[:8]
        strength = avg([fnum(i.get("score")) for i in items])
        old_strength = fnum(prev.get(key, {}).get("strength"))
        change = 0.0 if old_strength is None else round(strength - old_strength, 1)
        label = "new" if old_strength is None else "up" if change > 0 else "down" if change < 0 else "flat"
        rows.append({
            "key": key,
            "market": market,
            "theme": theme,
            "count": len(items),
            "strength": strength,
            "previousStrength": old_strength,
            "strengthChange": change,
            "changeLabel": label,
            "ret20": avg([fnum((i.get("metrics") or {}).get("ret20Pct")) for i in items]),
            "ret60": avg([fnum((i.get("metrics") or {}).get("ret60Pct")) for i in items]),
            "atr": avg([fnum((i.get("metrics") or {}).get("atrPct")) for i in items]),
            "turnover": round(sum(fnum((i.get("metrics") or {}).get("avgTradingValue20Usd")) or 0 for i in items), 0),
            "sCount": sum(1 for i in items if i.get("rank") == "S"),
            "aCount": sum(1 for i in items if i.get("rank") == "A"),
            "breakout": sum(1 for i in items if i.get("setupType") == "breakout"),
            "pullback": sum(1 for i in items if i.get("setupType") == "pullback"),
            "highVol": sum(1 for i in items if i.get("setupType") == "high_volatility"),
            "leaders": [{"symbol": i.get("symbol"), "name": i.get("name"), "rank": i.get("rank"), "score": i.get("score"), "setupType": i.get("setupType"), "metrics": i.get("metrics", {})} for i in leaders],
        })

    rows = sorted(rows, key=lambda r: (r.get("strengthChange") or 0, r.get("strength") or 0), reverse=True)
    report["sectorStrength"] = rows
    report["sectorStrengthPreviousAvailable"] = bool(prev_rows)
    LATEST.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    HISTORY.write_text(json.dumps({"generatedAt": report.get("generatedAt"), "sectorStrength": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"sectorStrengthRows": len(rows), "previousAvailable": bool(prev_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
