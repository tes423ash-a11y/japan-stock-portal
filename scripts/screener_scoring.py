from __future__ import annotations

import math
from typing import Any

from screener_data import clamp, finite, rounded, safe_text


def percentile(values: list[float | None]) -> list[float | None]:
    valid = [(index, value) for index, value in enumerate(values) if value is not None and math.isfinite(value)]
    result: list[float | None] = [None] * len(values)
    if not valid:
        return result
    ordered = sorted(valid, key=lambda item: item[1])
    if len(ordered) == 1:
        result[ordered[0][0]] = 50.0
        return result
    for rank, (index, _) in enumerate(ordered, start=1):
        result[index] = round(1 + 98 * (rank - 1) / (len(ordered) - 1), 1)
    return result


def trend_template(metrics: dict[str, Any]) -> tuple[int, list[str]]:
    price = finite(metrics.get("price")); ma50 = finite(metrics.get("ma50")); ma150 = finite(metrics.get("ma150")); ma200 = finite(metrics.get("ma200"))
    high52 = finite(metrics.get("high52w")); low52 = finite(metrics.get("low52w")); slope = finite(metrics.get("ma200Slope20dPct"))
    checks = [
        (price is not None and ma50 is not None and price > ma50, "株価>50MA"),
        (price is not None and ma150 is not None and price > ma150, "株価>150MA"),
        (price is not None and ma200 is not None and price > ma200, "株価>200MA"),
        (ma50 is not None and ma150 is not None and ma50 > ma150, "50MA>150MA"),
        (ma150 is not None and ma200 is not None and ma150 > ma200, "150MA>200MA"),
        (slope is not None and slope > 0, "200MA上向き"),
        (price is not None and low52 is not None and price >= low52 * 1.25, "52週安値+25%以上"),
        (price is not None and high52 is not None and price >= high52 * 0.75, "52週高値の25%以内"),
    ]
    passed = [label for ok, label in checks if ok]
    return len(passed), passed


def score_vcp(metrics: dict[str, Any]) -> int:
    score = 8 if metrics.get("contractionSequence") else 0
    range15 = finite(metrics.get("range15Pct")); tight10 = finite(metrics.get("tightness10Pct")); dry = finite(metrics.get("volumeDryUp5vs50"))
    pivot_distance = finite(metrics.get("distanceToPivotPct")); close_location = finite(metrics.get("closeLocation20Pct"))
    base_depth = finite(metrics.get("baseDepth60Pct")); atr_pct = finite(metrics.get("atrPct"))
    if range15 is not None: score += 6 if range15 <= 7 else 4 if range15 <= 10 else 2 if range15 <= 14 else 0
    if tight10 is not None and tight10 <= 7: score += 3
    if dry is not None: score += 5 if dry <= .7 else 3 if dry <= .9 else 1 if dry <= 1.05 else 0
    if pivot_distance is not None: score += 4 if -5 <= pivot_distance <= 2 else 2 if -10 <= pivot_distance <= 4 else 0
    if close_location is not None and close_location >= 70: score += 2
    if base_depth is not None: score -= 8 if base_depth > 45 else 5 if base_depth > 40 else 2 if base_depth > 35 else 0
    if range15 is not None and range15 > 15: score -= 2
    if atr_pct is not None: score -= 3 if atr_pct > 10 else 1 if atr_pct > 8 else 0
    return int(clamp(score, 0, 25))


def liquidity_score(turnover: float) -> int:
    if turnover >= 1_000_000_000: return 10
    if turnover >= 250_000_000: return 9
    if turnover >= 50_000_000: return 7
    if turnover >= 20_000_000: return 5
    if turnover >= 5_000_000: return 2
    return 0


def risk_score(atr_pct: float | None) -> int:
    if atr_pct is None: return 2
    if atr_pct <= 3.5: return 10
    if atr_pct <= 5.5: return 8
    if atr_pct <= 8: return 5
    if atr_pct <= 12: return 2
    return 0


def volume_score(metrics: dict[str, Any]) -> int:
    dry = finite(metrics.get("volumeDryUp5vs50")); surge = finite(metrics.get("latestVolumeRatio20")); distance = finite(metrics.get("distanceToPivotPct"))
    score = 0
    if dry is not None: score += 5 if dry <= .7 else 4 if dry <= .9 else 2 if dry <= 1.05 else 0
    if surge is not None: score += 5 if surge >= 1.5 else 3 if surge >= 1.15 else 1 if surge >= .9 else 0
    if distance is not None and distance < 0 and surge is not None and surge > 1.8: score -= 2
    return int(clamp(score, 0, 10))


def setup_type(metrics: dict[str, Any], trend_count: int, vcp: int, rs_rating: float, turnover: float, quality: str) -> str:
    price = finite(metrics.get("price")); ma20 = finite(metrics.get("ma20")); ma50 = finite(metrics.get("ma50")); ma200 = finite(metrics.get("ma200"))
    slope = finite(metrics.get("ma200Slope20dPct")); distance = finite(metrics.get("distanceToPivotPct")); volume_ratio = finite(metrics.get("latestVolumeRatio20"))
    dry = finite(metrics.get("volumeDryUp5vs50")); extended20 = finite(metrics.get("extendedFromMa20Pct"))
    base_depth = finite(metrics.get("baseDepth60Pct")); range15 = finite(metrics.get("range15Pct"))
    if quality == "missing" or price is None: return "data_issue"
    if turnover < 2_000_000: return "avoid"
    if ma200 is not None and price < ma200 and (slope is None or slope <= 0): return "avoid"
    if distance is not None and (distance > 5 or (extended20 is not None and extended20 > 12)): return "extended"
    vcp_shape_ready = (
        bool(metrics.get("contractionSequence"))
        and (base_depth is None or base_depth <= 40)
        and (range15 is None or range15 <= 15)
    )
    if trend_count >= 7 and vcp >= 18 and vcp_shape_ready and distance is not None and -5 <= distance < 0: return "vcp_ready"
    if trend_count >= 7 and distance is not None and 0 <= distance <= 4 and (volume_ratio or 0) >= 1.35: return "breakout_ready"
    near20 = ma20 is not None and -1.5 <= ((price / ma20) - 1) * 100 <= 3.5
    near50 = ma50 is not None and -1.5 <= ((price / ma50) - 1) * 100 <= 3.5
    if trend_count >= 6 and rs_rating >= 70 and (near20 or near50) and (dry is None or dry <= 1): return "pullback_ready"
    if trend_count >= 6 and rs_rating >= 65: return "trend_watch"
    if trend_count >= 4: return "early_stage"
    return "watch_only"


def setup_label(value: str) -> str:
    return {"vcp_ready":"VCPピボット接近","breakout_ready":"出来高伴うブレイク","pullback_ready":"上昇トレンドの押し目","trend_watch":"強いトレンド監視","early_stage":"初動候補","extended":"買い場超過","watch_only":"形待ち","avoid":"除外寄り","data_issue":"データ不足"}.get(value, "形待ち")


def action_for_setup(value: str) -> str:
    return {
        "vcp_ready":"ピボット超えと出来高増加を確認。基準ゾーン外では追わない。",
        "breakout_ready":"終値のピボット維持と出来高を確認し、基準ゾーン内か再点検。",
        "pullback_ready":"20日線または50日線での反発と出来高減少を確認。",
        "trend_watch":"トレンドは強いが形が未完成。横ばい化かタイト化待ち。",
        "early_stage":"トレンドテンプレート完成前。監視に留める。",
        "extended":"追わない。20日線接近か新しいベース形成待ち。",
        "watch_only":"RS・出来高・ベース形成の改善待ち。",
        "avoid":"流動性または長期トレンドが不適。原則見送り。",
        "data_issue":"価格履歴不足のため判定対象外。",
    }.get(value, "監視継続。")


def trade_plan(metrics: dict[str, Any], setup: str) -> dict[str, Any]:
    price = finite(metrics.get("price")); pivot = finite(metrics.get("pivot")); ma20 = finite(metrics.get("ma20")); ma50 = finite(metrics.get("ma50"))
    recent_low = finite(metrics.get("recentLow10")); atr_pct = finite(metrics.get("atrPct"))
    if price is None:
        return {"entryLow":None,"entryHigh":None,"entryReference":None,"stop":None,"riskPct":None,"target1":None,"target2":None,"positionSizePctAt1PctRisk":None}
    if setup == "pullback_ready":
        supports = [value for value in (ma20, ma50) if value is not None and value <= price * 1.04]
        reference = max(supports) if supports else price
        entry_low, entry_high = reference * .995, reference * 1.02
    else:
        reference = pivot or price
        entry_low, entry_high = reference * .995, reference * 1.03
    estimated_atr = reference * (atr_pct or 5) / 100
    atr_stop = reference - estimated_atr * 2
    supports = [value for value in (recent_low, ma20, ma50) if value is not None and value < reference]
    support_stop = min(supports) * .995 if supports else atr_stop
    stop = min(reference * .975, max(reference * .93, min(atr_stop, support_stop)))
    risk_pct = max(.1, (reference - stop) / reference * 100)
    return {
        "entryLow":rounded(entry_low,2), "entryHigh":rounded(entry_high,2), "entryReference":rounded(reference,2),
        "stop":rounded(stop,2), "riskPct":rounded(risk_pct,1),
        "target1":rounded(reference + (reference-stop)*2,2), "target2":rounded(reference + (reference-stop)*3,2),
        "positionSizePctAt1PctRisk":rounded(min(25,100/risk_pct),1),
    }


def rank_candidate(score: int, setup: str, rs: float, trend: int, vcp: int, atr: float | None, turnover: float, quality: str) -> str:
    if quality in {"missing","limited"} or setup in {"avoid","data_issue"}: return "D"
    if score >= 90 and rs >= 85 and trend >= 7 and vcp >= 18 and setup in {"vcp_ready","breakout_ready"} and (atr is None or atr <= 6) and turnover >= 20_000_000: return "S"
    if score >= 80 and rs >= 75 and trend >= 6 and setup in {"vcp_ready","breakout_ready","pullback_ready"} and (atr is None or atr <= 8) and turnover >= 10_000_000: return "A"
    if score >= 70 and trend >= 5 and setup not in {"extended","avoid"}: return "B"
    if score >= 60: return "C"
    return "D"


def enrich_market_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    horizons = [20, 60, 120, 252]
    percentiles = {horizon: percentile([finite((item.get("metrics") or {}).get(f"ret{horizon}Pct")) for item in candidates]) for horizon in horizons}
    enriched: list[dict[str, Any]] = []
    for index, item in enumerate(candidates):
        metrics = item.get("metrics") or {}
        if not metrics:
            item.update({"rank":"D","score":0,"technicalScore":0,"setupType":"data_issue","setup":setup_label("data_issue"),"action":action_for_setup("data_issue"),"componentScores":{"trend":0,"rs":0,"vcp":0,"volume":0,"risk":0,"liquidity":0},"reasons":["価格データを取得できませんでした"],"tradePlan":trade_plan({},"data_issue")})
            enriched.append(item); continue
        rs_values = {horizon: percentiles[horizon][index] for horizon in horizons}
        weighted = [(rs_values[20],.15),(rs_values[60],.35),(rs_values[120],.30),(rs_values[252],.20)]
        available = [(value,weight) for value,weight in weighted if value is not None]
        rs_rating = sum(value*weight for value,weight in available)/sum(weight for _,weight in available) if available else 1
        metrics.update({f"rs{horizon}Rating":rounded(rs_values[horizon],1) for horizon in horizons}); metrics["rsRating"] = rounded(rs_rating,1)
        trend_count, trend_checks = trend_template(metrics); trend_score = round(trend_count/8*25); vcp = score_vcp(metrics)
        rs_score = int(round(clamp((rs_rating-35)/64*20,0,20))); turnover = finite(metrics.get("avgTradingValue20Usd")) or 0
        liquidity = liquidity_score(turnover); risk = risk_score(finite(metrics.get("atrPct"))); volume = volume_score(metrics)
        quality = safe_text((item.get("dataQuality") or {}).get("status")) or "missing"
        setup = setup_type(metrics,trend_count,vcp,rs_rating,turnover,quality)
        score = int(round(clamp(trend_score+vcp+rs_score+liquidity+risk+volume,0,100)))
        if setup == "extended": score = max(0,score-10)
        if quality == "partial": score = max(0,score-4)
        if (finite((item.get("dataQuality") or {}).get("staleDays")) or 0) > 5: score = max(0,score-5)
        rank = rank_candidate(score,setup,rs_rating,trend_count,vcp,finite(metrics.get("atrPct")),turnover,quality)
        plan = trade_plan(metrics,setup); warnings = list(item.get("warnings") or [])
        if rs_rating < 60: warnings.append("RS不足")
        if setup in {"vcp_ready","breakout_ready"} and (finite(metrics.get("latestVolumeRatio20")) or 0) < 1.35: warnings.append("出来高確認待ち")
        reasons = trend_checks + [f"RS {rs_rating:.0f}",f"VCP {vcp}/25",f"ピボット距離 {finite(metrics.get('distanceToPivotPct')) or 0:.1f}%"]
        item.update({
            "rank":rank,"score":score,"technicalScore":score,"setupType":setup,"setup":setup_label(setup),"action":action_for_setup(setup),
            "componentScores":{"trend":trend_score,"rs":rs_score,"vcp":vcp,"volume":volume,"risk":risk,"liquidity":liquidity},
            "trendTemplate":{"passed":trend_count,"total":8,"checks":trend_checks},"vcpScore":vcp,"tradePlan":plan,
            "stop":plan.get("stop"),"target1":plan.get("target1"),"target2":plan.get("target2"),"rr":2 if plan.get("target1") else None,
            "riskLabel":"低ボラ" if (finite(metrics.get("atrPct")) or 99)<=3.5 else "許容" if (finite(metrics.get("atrPct")) or 99)<=6 else "高ボラ",
            "warnings":list(dict.fromkeys(warnings)),"reasons":reasons,
        })
        enriched.append(item)
    return enriched
