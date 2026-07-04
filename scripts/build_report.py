from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
WATCHLISTS = [ROOT / "watchlists" / "jp_candidates.csv", ROOT / "watchlists" / "us_candidates.csv"]
REPORT_DIR = ROOT / "reports"
JQUANTS_BASE_URL = "https://api.jquants.com/v1"


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


def jquants_code(symbol: str) -> str:
    return symbol.replace(".T", "").strip()


def get_jquants_id_token() -> str | None:
    refresh_token = os.getenv("JQUANTS_REFRESH_TOKEN")
    mailaddress = os.getenv("JQUANTS_EMAIL")
    password = os.getenv("JQUANTS_PASSWORD")

    try:
        if not refresh_token and mailaddress and password:
            response = requests.post(
                f"{JQUANTS_BASE_URL}/token/auth_user",
                json={"mailaddress": mailaddress, "password": password},
                timeout=30,
            )
            response.raise_for_status()
            refresh_token = response.json().get("refreshToken")

        if not refresh_token:
            return None

        response = requests.post(
            f"{JQUANTS_BASE_URL}/token/auth_refresh",
            params={"refreshtoken": refresh_token},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("idToken")
    except requests.RequestException as error:
        print(f"J-Quants authentication skipped: {error}")
        return None


def fetch_jquants_daily_quotes(code: str, id_token: str) -> list[dict[str, Any]]:
    end = date.today()
    start = end - timedelta(days=430)
    response = requests.get(
        f"{JQUANTS_BASE_URL}/prices/daily_quotes",
        params={"code": code, "from": start.strftime("%Y%m%d"), "to": end.strftime("%Y%m%d")},
        headers={"Authorization": f"Bearer {id_token}"},
        timeout=30,
    )
    response.raise_for_status()
    quotes = response.json().get("daily_quotes", [])
    return sorted(quotes, key=lambda item: item.get("Date", ""))


def value(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        raw = row.get(key)
        if raw not in (None, ""):
            try:
                return float(raw)
            except (TypeError, ValueError):
                continue
    return None


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def pct_change(values: list[float], days: int) -> float | None:
    if len(values) <= days or values[-days - 1] == 0:
        return None
    return ((values[-1] / values[-days - 1]) - 1) * 100


def avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def atr(quotes: list[dict[str, Any]], period: int = 14) -> float | None:
    if len(quotes) < period + 1:
        return None
    ranges: list[float] = []
    recent = quotes[-period:]
    previous_close = value(quotes[-period - 1], "AdjustmentClose", "Close")
    for row in recent:
        high = value(row, "AdjustmentHigh", "High")
        low = value(row, "AdjustmentLow", "Low")
        close = value(row, "AdjustmentClose", "Close")
        if high is None or low is None or close is None or previous_close is None:
            continue
        ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
        previous_close = close
    return avg(ranges)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def rank_from_score(score: int) -> str:
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    return "D"


def build_placeholder_candidate(row: dict[str, str], index: int) -> dict[str, object]:
    score = max(55, 92 - index * 5)
    symbol = row.get("symbol", "")
    setup = "VCP watch" if score >= 80 else "Pullback watch" if score >= 65 else "Watch only"
    action = "Priority review" if score >= 80 else "Wait for setup"
    return {
        "symbol": symbol,
        "code": symbol.replace(".T", ""),
        "name": row.get("name", "Unnamed"),
        "market": row.get("market", ""),
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


def build_jquants_candidate(row: dict[str, str], quotes: list[dict[str, Any]], index: int) -> dict[str, object]:
    symbol = row.get("symbol", "")
    closes = [value(item, "AdjustmentClose", "Close") for item in quotes]
    closes = [item for item in closes if item is not None]
    volumes = [value(item, "AdjustmentVolume", "Volume") for item in quotes]
    volumes = [item for item in volumes if item is not None]

    if len(closes) < 60:
        return build_placeholder_candidate(row, index)

    price = closes[-1]
    ma50 = sma(closes, 50)
    ma150 = sma(closes, 150)
    ma200 = sma(closes, 200)
    high_52w = max(closes[-252:]) if len(closes) >= 252 else max(closes)
    low_52w = min(closes[-252:]) if len(closes) >= 252 else min(closes)
    volume20 = avg(volumes[-20:]) if len(volumes) >= 20 else None
    volume50 = avg(volumes[-50:]) if len(volumes) >= 50 else None
    atr14 = atr(quotes, 14)
    atr_pct = (atr14 / price) * 100 if atr14 and price else None
    ret20 = pct_change(closes, 20)
    ret60 = pct_change(closes, 60)

    trend_points = 0
    trend_checks: list[str] = []
    if ma50 and price > ma50:
        trend_points += 10
        trend_checks.append("price > 50MA")
    if ma150 and price > ma150:
        trend_points += 8
        trend_checks.append("price > 150MA")
    if ma200 and price > ma200:
        trend_points += 8
        trend_checks.append("price > 200MA")
    if ma50 and ma150 and ma200 and ma50 > ma150 > ma200:
        trend_points += 10
        trend_checks.append("50MA > 150MA > 200MA")
    if high_52w and price >= high_52w * 0.75:
        trend_points += 8
        trend_checks.append("within 25% of 52w high")
    if low_52w and price >= low_52w * 1.25:
        trend_points += 6
        trend_checks.append("25% above 52w low")

    momentum_points = 0
    if ret20 is not None:
        momentum_points += clamp(ret20, -10, 20) * 0.35
    if ret60 is not None:
        momentum_points += clamp(ret60, -20, 45) * 0.35

    volume_points = 0
    if volume20 and volume50 and volume50 > 0:
        ratio = volume20 / volume50
        if ratio >= 1.4:
            volume_points += 10
        elif ratio >= 1.0:
            volume_points += 6
        elif ratio >= 0.75:
            volume_points += 3

    contraction_points = 0
    if atr_pct is not None:
        if atr_pct <= 3.5:
            contraction_points += 12
        elif atr_pct <= 5.5:
            contraction_points += 8
        elif atr_pct <= 8:
            contraction_points += 4

    score = int(round(clamp(trend_points + momentum_points + volume_points + contraction_points, 0, 100)))
    rank = rank_from_score(score)
    setup = "SEPA/VCP candidate" if score >= 80 else "Pullback watch" if score >= 65 else "Watch only"
    stop = round(price - (atr14 * 2), 1) if atr14 else ""
    pivot = round(high_52w, 1) if high_52w else ""
    target1 = round(price + (price - stop) * 2, 1) if isinstance(stop, float) and price > stop else ""
    target2 = round(price + (price - stop) * 3, 1) if isinstance(stop, float) and price > stop else ""
    rr = 2 if target1 else ""

    reasons = trend_checks[:]
    if ret20 is not None:
        reasons.append(f"20d return {ret20:.1f}%")
    if ret60 is not None:
        reasons.append(f"60d return {ret60:.1f}%")
    if atr_pct is not None:
        reasons.append(f"ATR% {atr_pct:.1f}")

    return {
        "symbol": symbol,
        "code": jquants_code(symbol),
        "name": row.get("name", "Unnamed"),
        "market": row.get("market", "JP"),
        "theme": row.get("theme", "Uncategorized"),
        "rank": rank,
        "score": score,
        "setup": setup,
        "price": round(price, 1),
        "pivot": pivot,
        "stop": stop,
        "target1": target1,
        "target2": target2,
        "rr": rr,
        "riskLabel": "ATR stop" if atr14 else "Not calculated",
        "action": "Priority review" if rank == "A" else "Wait for setup",
        "reasons": reasons or [row.get("note", "watchlist candidate")],
    }


def build_candidate(row: dict[str, str], index: int, id_token: str | None) -> dict[str, object]:
    market = (row.get("market") or "").upper()
    symbol = row.get("symbol", "")
    if id_token and (market == "JP" or symbol.endswith(".T")):
        try:
            quotes = fetch_jquants_daily_quotes(jquants_code(symbol), id_token)
            if quotes:
                return build_jquants_candidate(row, quotes, index)
        except requests.RequestException as error:
            print(f"J-Quants quote fetch skipped for {symbol}: {error}")
    return build_placeholder_candidate(row, index)


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
    id_token = get_jquants_id_token()
    candidates = [build_candidate(row, i, id_token) for i, row in enumerate(rows)]
    average_score = round(sum(int(item["score"]) for item in candidates) / len(candidates), 1) if candidates else 0
    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "universe": "watchlists+jquants" if id_token else "watchlists",
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
