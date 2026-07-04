from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
WATCHLISTS = [ROOT / "watchlists" / "jp_candidates.csv", ROOT / "watchlists" / "us_candidates.csv"]
REPORT_DIR = ROOT / "reports"
JQUANTS_BASE_URL = "https://api.jquants.com/v2"


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


def jquants_code_candidates(symbol: str) -> list[str]:
    code = symbol.replace(".T", "").strip()
    if code.isdigit() and len(code) == 4:
        return [code, f"{code}0"]
    return [code]


def safe_http_status(error: requests.RequestException) -> str:
    response = getattr(error, "response", None)
    if response is None:
        return error.__class__.__name__
    detail = ""
    try:
        body = response.text.strip().replace("\n", " ")
        if body:
            detail = f" body={body[:240]}"
    except Exception:
        detail = ""
    return f"HTTP {response.status_code}{detail}"


def jquants_recent_unavailable(diagnostics: list[dict[str, object]]) -> bool:
    for item in diagnostics:
        message = str(item.get("message", ""))
        if "subscription covers" in message or "Rate limit exceeded" in message:
            return True
    return False


def get_jquants_api_key() -> tuple[str | None, dict[str, object]]:
    api_key = os.getenv("JQUANTS_API_KEY") or os.getenv("JQUANTS_REFRESH_TOKEN")
    legacy_email = os.getenv("JQUANTS_EMAIL")
    legacy_password = os.getenv("JQUANTS_PASSWORD")

    if os.getenv("JQUANTS_API_KEY"):
        auth_source = "api_key"
    elif os.getenv("JQUANTS_REFRESH_TOKEN"):
        auth_source = "api_key_from_refresh_token_secret"
    elif legacy_email or legacy_password:
        auth_source = "legacy_email_password"
    else:
        auth_source = "none"

    status: dict[str, object] = {
        "enabled": bool(api_key or legacy_email or legacy_password),
        "authSource": auth_source,
        "status": "missing_credentials",
        "message": "Set JQUANTS_API_KEY. J-Quants v2 uses x-api-key authentication.",
    }

    if api_key:
        status["status"] = "api_key_loaded"
        status["message"] = "API key loaded. J-Quants will be tried first, then yfinance will be used as fallback."
        print(f"J-Quants status: {status['status']} via {auth_source}")
        return api_key, status

    if legacy_email or legacy_password:
        status["status"] = "legacy_auth_unsupported"
        status["message"] = "Email/password auth is not used by this v2 workflow. Set JQUANTS_API_KEY or put the API key in JQUANTS_REFRESH_TOKEN."
        print(f"J-Quants status: {status['status']}")
        return None, status

    print("J-Quants status: missing_credentials")
    return None, status


def fetch_jquants_daily_quotes(code: str, api_key: str) -> list[dict[str, Any]]:
    end = date.today()
    start = end - timedelta(days=95)
    params: dict[str, Any] = {"code": code, "from": start.isoformat(), "to": end.isoformat()}
    headers = {"x-api-key": api_key, "User-Agent": "japan-stock-portal/1.0"}
    all_rows: list[dict[str, Any]] = []

    while True:
        response = requests.get(f"{JQUANTS_BASE_URL}/equities/bars/daily", params=params, headers=headers, timeout=30)
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", [])
        if isinstance(rows, list):
            all_rows.extend(rows)
        pagination_key = payload.get("pagination_key")
        if not pagination_key:
            break
        params["pagination_key"] = pagination_key

    return sorted(all_rows, key=lambda item: item.get("Date", ""))


def fetch_yfinance_daily_quotes(symbol: str) -> list[dict[str, Any]]:
    ticker = yf.Ticker(symbol)
    history = ticker.history(period="1y", interval="1d", auto_adjust=True)
    if history.empty:
        return []

    rows: list[dict[str, Any]] = []
    for idx, item in history.iterrows():
        close = item.get("Close")
        high = item.get("High")
        low = item.get("Low")
        volume = item.get("Volume")
        rows.append({
            "Date": idx.strftime("%Y-%m-%d"),
            "AdjC": float(close) if close == close else None,
            "AdjH": float(high) if high == high else None,
            "AdjL": float(low) if low == low else None,
            "AdjVo": float(volume) if volume == volume else None,
        })
    return rows


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
    previous_close = value(quotes[-period - 1], "AdjC", "AdjustmentClose", "C", "Close")
    for row in recent:
        high = value(row, "AdjH", "AdjustmentHigh", "H", "High")
        low = value(row, "AdjL", "AdjustmentLow", "L", "Low")
        close = value(row, "AdjC", "AdjustmentClose", "C", "Close")
        if high is None or low is None or close is None or previous_close is None:
            continue
        ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
        previous_close = close
    return avg(ranges)


def clamp(number: float, low: float, high: float) -> float:
    return max(low, min(high, number))


def round_or_none(number: float | None, digits: int = 1) -> float | None:
    return round(number, digits) if number is not None else None


def rank_from_score(score: int, setup_type: str) -> str:
    if setup_type == "avoid":
        return "D"
    if score >= 76 and setup_type not in {"high_volatility"}:
        return "A"
    if score >= 62:
        return "B"
    if score >= 46:
        return "C"
    return "D"


def theme_score(theme: str, symbol: str, name: str) -> int:
    text = f"{theme} {symbol} {name}".lower()
    score = 5
    if any(word in text for word in ["hbm", "memory", "dram", "nand", "micron", "sandisk"]):
        score += 10
    if any(word in text for word in ["ai", "infrastructure", "data center", "datacenter", "optical"]):
        score += 8
    if any(word in text for word in ["defense", "重工", "防衛"]):
        score += 7
    if any(word in text for word in ["power", "electric", "電力", "原子力"]):
        score += 5
    return int(clamp(score, 0, 15))


def setup_label(setup_type: str) -> str:
    return {
        "breakout": "ブレイク候補",
        "pullback": "押し目候補",
        "theme_leader": "テーマリーダー監視",
        "high_volatility": "高ボラ注意",
        "trend_watch": "トレンド監視",
        "watch_only": "監視のみ",
        "avoid": "除外寄り",
    }.get(setup_type, "監視のみ")


def action_for_setup(setup_type: str) -> str:
    return {
        "breakout": "ピボット超えと出来高増を確認。高値掴みは避ける。",
        "pullback": "20日線/50日線の反発、下げ止まり、出来高減少を確認。",
        "theme_leader": "テーマ資金が戻るまで優先監視。地合い回復時に再評価。",
        "high_volatility": "ボラが高い。サイズを落とすか、ATR低下・横ばい化を待つ。",
        "trend_watch": "上昇トレンドは残る。セットアップ形成待ち。",
        "watch_only": "現時点では形不足。監視継続。",
        "avoid": "トレンド修復まで原則見送り。",
    }.get(setup_type, "監視継続。")


def build_placeholder_candidate(row: dict[str, str], index: int, reason: str | None = None) -> dict[str, object]:
    symbol = row.get("symbol", "")
    reasons = [row.get("note", "watchlist candidate")]
    if reason:
        reasons.insert(0, reason)
    setup_type = "watch_only"
    score = max(35, 55 - index * 3)
    return {
        "symbol": symbol,
        "code": symbol.replace(".T", ""),
        "name": row.get("name", "Unnamed"),
        "market": row.get("market", ""),
        "theme": row.get("theme", "Uncategorized"),
        "rank": rank_from_score(score, setup_type),
        "score": score,
        "setup": setup_label(setup_type),
        "setupType": setup_type,
        "price": "",
        "pivot": "",
        "stop": "",
        "target1": "",
        "target2": "",
        "rr": "",
        "riskLabel": "Not calculated",
        "action": action_for_setup(setup_type),
        "dataSource": "watchlist",
        "componentScores": {"trend": 0, "momentum": 0, "volume": 0, "risk": 0, "theme": theme_score(row.get("theme", ""), symbol, row.get("name", "")), "setup": 0},
        "metrics": {},
        "reasons": reasons,
    }


def build_quote_candidate(row: dict[str, str], quotes: list[dict[str, Any]], index: int, source: str) -> dict[str, object]:
    symbol = row.get("symbol", "")
    name = row.get("name", "Unnamed")
    theme = row.get("theme", "Uncategorized")
    closes = [value(item, "AdjC", "AdjustmentClose", "C", "Close") for item in quotes]
    closes = [item for item in closes if item is not None]
    volumes = [value(item, "AdjVo", "AdjustmentVolume", "Vo", "Volume") for item in quotes]
    volumes = [item for item in volumes if item is not None]

    if len(closes) < 30:
        return build_placeholder_candidate(row, index, f"{source} history was too short.")

    price = closes[-1]
    ma20 = sma(closes, 20)
    ma50 = sma(closes, 50)
    ma150 = sma(closes, 150)
    ma200 = sma(closes, 200)
    lookback_high = max(closes[-252:]) if len(closes) >= 252 else max(closes)
    lookback_low = min(closes[-252:]) if len(closes) >= 252 else min(closes)
    volume20 = avg(volumes[-20:]) if len(volumes) >= 20 else None
    volume50 = avg(volumes[-50:]) if len(volumes) >= 50 else None
    volume_ratio = (volume20 / volume50) if volume20 and volume50 and volume50 > 0 else None
    atr14 = atr(quotes, 14)
    atr_pct = (atr14 / price) * 100 if atr14 and price else None
    ret20 = pct_change(closes, 20)
    ret60 = pct_change(closes, 60)
    drawdown_from_high = ((price / lookback_high) - 1) * 100 if lookback_high else None

    reasons: list[str] = []
    trend = 0
    if ma20 and price > ma20:
        trend += 4
        reasons.append("20MA上")
    if ma50 and price > ma50:
        trend += 6
        reasons.append("50MA上")
    if ma150 and price > ma150:
        trend += 5
        reasons.append("150MA上")
    if ma200 and price > ma200:
        trend += 5
        reasons.append("200MA上")
    if ma50 and ma150 and ma200 and ma50 > ma150 > ma200:
        trend += 5
        reasons.append("50>150>200MA")
    trend = int(clamp(trend, 0, 25))

    momentum = 0.0
    if ret20 is not None:
        momentum += clamp((ret20 + 8) / 28 * 9, 0, 9)
        reasons.append(f"20日 {ret20:.1f}%")
    if ret60 is not None:
        momentum += clamp((ret60 + 15) / 60 * 11, 0, 11)
        reasons.append(f"60日 {ret60:.1f}%")
    if drawdown_from_high is not None and drawdown_from_high >= -12:
        momentum += 5
        reasons.append(f"高値から {drawdown_from_high:.1f}%")
    momentum = int(round(clamp(momentum, 0, 25)))

    volume = 0
    if volume_ratio is not None:
        if volume_ratio >= 1.5:
            volume = 10
            reasons.append(f"出来高拡大 x{volume_ratio:.2f}")
        elif volume_ratio >= 1.05:
            volume = 7
            reasons.append(f"出来高安定 x{volume_ratio:.2f}")
        elif volume_ratio >= 0.75:
            volume = 4
            reasons.append(f"出来高収縮 x{volume_ratio:.2f}")

    risk = 0
    risk_label = "ATR unknown"
    if atr_pct is not None:
        if atr_pct <= 3.5:
            risk = 15
            risk_label = "低ボラ"
        elif atr_pct <= 5.5:
            risk = 12
            risk_label = "許容ボラ"
        elif atr_pct <= 8:
            risk = 8
            risk_label = "やや高ボラ"
        elif atr_pct <= 12:
            risk = 4
            risk_label = "高ボラ"
        else:
            risk = 1
            risk_label = "超高ボラ"
        reasons.append(f"ATR {atr_pct:.1f}%")

    theme_points = theme_score(theme, symbol, name)

    breakout_setup = 0
    if trend >= 18 and drawdown_from_high is not None and drawdown_from_high >= -8:
        breakout_setup += 8
    if ma20 and price > ma20:
        breakout_setup += 3
    if volume_ratio is not None and volume_ratio >= 1.05:
        breakout_setup += 4

    pullback_setup = 0
    if trend >= 16 and drawdown_from_high is not None and -35 <= drawdown_from_high <= -5:
        pullback_setup += 8
    if ma20 and price >= ma20 * 0.95:
        pullback_setup += 3
    if ret20 is not None and ret20 >= -12:
        pullback_setup += 4

    theme_leader_setup = 0
    if theme_points >= 12 and trend >= 14:
        theme_leader_setup += 8
    if ret60 is not None and ret60 >= -20:
        theme_leader_setup += 4
    if price >= lookback_low * 1.25:
        theme_leader_setup += 3

    setup_points = int(clamp(max(breakout_setup, pullback_setup, theme_leader_setup), 0, 15))

    if trend < 10 and (ret60 is not None and ret60 < -15):
        setup_type = "avoid"
    elif atr_pct is not None and atr_pct >= 10:
        setup_type = "high_volatility"
    elif breakout_setup >= 11:
        setup_type = "breakout"
    elif pullback_setup >= 10:
        setup_type = "pullback"
    elif theme_leader_setup >= 10:
        setup_type = "theme_leader"
    elif trend >= 16:
        setup_type = "trend_watch"
    else:
        setup_type = "watch_only"

    total_score = int(round(clamp(trend + momentum + volume + risk + theme_points + setup_points, 0, 100)))
    rank = rank_from_score(total_score, setup_type)
    stop = round(price - (atr14 * 2), 1) if atr14 else ""
    pivot = round(lookback_high, 1) if lookback_high else ""
    target1 = round(price + (price - stop) * 2, 1) if isinstance(stop, float) and price > stop else ""
    target2 = round(price + (price - stop) * 3, 1) if isinstance(stop, float) and price > stop else ""

    return {
        "symbol": symbol,
        "code": symbol.replace(".T", ""),
        "name": name,
        "market": row.get("market", ""),
        "theme": theme,
        "rank": rank,
        "score": total_score,
        "setup": setup_label(setup_type),
        "setupType": setup_type,
        "price": round(price, 1),
        "pivot": pivot,
        "stop": stop,
        "target1": target1,
        "target2": target2,
        "rr": 2 if target1 else "",
        "riskLabel": risk_label,
        "action": action_for_setup(setup_type),
        "dataSource": source,
        "componentScores": {"trend": trend, "momentum": momentum, "volume": volume, "risk": risk, "theme": theme_points, "setup": setup_points},
        "metrics": {
            "ma20": round_or_none(ma20),
            "ma50": round_or_none(ma50),
            "ma150": round_or_none(ma150),
            "ma200": round_or_none(ma200),
            "ret20Pct": round_or_none(ret20),
            "ret60Pct": round_or_none(ret60),
            "atrPct": round_or_none(atr_pct),
            "drawdownFromHighPct": round_or_none(drawdown_from_high),
            "volumeRatio20vs50": round_or_none(volume_ratio, 2),
        },
        "reasons": reasons or [row.get("note", "watchlist candidate")],
    }


def build_candidate(row: dict[str, str], index: int, api_key: str | None, diagnostics: list[dict[str, object]]) -> dict[str, object]:
    market = (row.get("market") or "").upper()
    symbol = row.get("symbol", "")
    if api_key and (market == "JP" or symbol.endswith(".T")) and not jquants_recent_unavailable(diagnostics):
        for code in jquants_code_candidates(symbol):
            try:
                quotes = fetch_jquants_daily_quotes(code, api_key)
                diagnostics.append({"provider": "jquants_v2", "symbol": symbol, "code": code, "endpoint": "v2/equities/bars/daily", "status": "ok", "rows": len(quotes)})
                if quotes:
                    return build_quote_candidate(row, quotes, index, "jquants_v2")
            except requests.RequestException as error:
                diagnostics.append({"provider": "jquants_v2", "symbol": symbol, "code": code, "endpoint": "v2/equities/bars/daily", "status": "quote_failed", "message": safe_http_status(error)})
                print(f"J-Quants v2 quote fetch skipped for {symbol} ({code}): {safe_http_status(error)}")

    try:
        quotes = fetch_yfinance_daily_quotes(symbol)
        diagnostics.append({"provider": "yfinance", "symbol": symbol, "status": "ok", "rows": len(quotes)})
        if quotes:
            return build_quote_candidate(row, quotes, index, "yfinance")
    except Exception as error:
        diagnostics.append({"provider": "yfinance", "symbol": symbol, "status": "quote_failed", "message": error.__class__.__name__})
        print(f"yfinance quote fetch skipped for {symbol}: {error.__class__.__name__}")

    return build_placeholder_candidate(row, index, "All data providers failed.")


def build_themes(candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in candidates:
        grouped[str(item.get("theme") or "Uncategorized")].append(item)
    themes = []
    for theme, items in grouped.items():
        average = sum(int(item.get("score", 0)) for item in items) / len(items)
        leaders = [str(item.get("symbol")) for item in sorted(items, key=lambda x: int(x.get("score", 0)), reverse=True)[:3]]
        setup_counts = defaultdict(int)
        for item in items:
            setup_counts[str(item.get("setupType", "watch_only"))] += 1
        themes.append({"name": theme, "strength": round(average, 1), "leaders": leaders, "note": dict(setup_counts)})
    return sorted(themes, key=lambda item: float(item["strength"]), reverse=True)


def write_markdown(report: dict[str, object]) -> str:
    candidates = report.get("candidates", [])
    lines = ["# Daily Screener Report", "", f"Generated: {report['generatedAt']}", "", "## Data Provider Status", ""]
    lines.append(f"- J-Quants: {report.get('jquantsStatus', {}).get('status', 'unknown')}")
    lines.append(f"- Universe: {report.get('universe')}")
    lines.extend(["", "## Top Candidates", ""])
    for item in candidates[:10]:
        lines.append(f"- {item['rank']} / {item['score']} / {item['setup']} / {item['symbol']} / {item['name']} / {item['theme']} / {item.get('dataSource', 'unknown')}")
    lines.append("")
    lines.append("Dashboard input: `reports/latest.json`")
    return "\n".join(lines) + "\n"


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_watchlists()
    api_key, jquants_status = get_jquants_api_key()
    diagnostics: list[dict[str, object]] = []
    candidates = [build_candidate(row, i, api_key, diagnostics) for i, row in enumerate(rows)]

    average_score = round(sum(int(item["score"]) for item in candidates) / len(candidates), 1) if candidates else 0
    jquants_candidates = sum(1 for item in candidates if item.get("dataSource") == "jquants_v2")
    yfinance_candidates = sum(1 for item in candidates if item.get("dataSource") == "yfinance")
    data_sources = sorted({str(item.get("dataSource")) for item in candidates})
    setup_counts = defaultdict(int)
    for item in candidates:
        setup_counts[str(item.get("setupType", "watch_only"))] += 1

    if jquants_candidates > 0:
        jquants_status["status"] = "ok"
        jquants_status["message"] = "J-Quants v2 quote data was loaded."
    elif api_key:
        jquants_status["status"] = "fallback_to_yfinance"
        jquants_status["message"] = "J-Quants was unavailable for the requested range; yfinance fallback was used when possible."

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "universe": "+".join(["watchlists", *data_sources]),
        "jquantsStatus": jquants_status,
        "jquantsQuoteDiagnostics": diagnostics,
        "summary": {
            "total": len(candidates),
            "aRank": sum(1 for item in candidates if item["rank"] == "A"),
            "breakoutReady": setup_counts["breakout"],
            "pullbackReady": setup_counts["pullback"],
            "themeLeader": setup_counts["theme_leader"],
            "highVolatility": setup_counts["high_volatility"],
            "avoid": setup_counts["avoid"],
            "averageScore": average_score,
            "jquantsCandidates": jquants_candidates,
            "yfinanceCandidates": yfinance_candidates,
        },
        "candidates": sorted(candidates, key=lambda item: int(item.get("score", 0)), reverse=True),
        "themes": build_themes(candidates),
        "tracking": [],
    }
    print(json.dumps({"universe": report["universe"], "jquantsStatus": jquants_status, "diagnostics": diagnostics}, ensure_ascii=False))
    (REPORT_DIR / "latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORT_DIR / "latest.md").write_text(write_markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
