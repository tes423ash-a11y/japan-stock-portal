"""Completed exchange sessions, checked against JPX/NYSE on 2026-09-06.
https://www.jpx.co.jp/corporate/about-jpx/calendar/
https://www.nyse.com/trade/hours-calendars
Unknown years return None; never call unverified calendars current.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from collections import Counter

HOLIDAYS = {'JP': {'2026': '01-01 01-02 01-03 01-12 02-11 02-23 03-20 04-29 05-03 05-04 05-05 05-06 07-20 08-11 09-21 09-22 09-23 10-12 11-03 11-23 12-31', '2027': '01-01 01-02 01-03 01-11 02-11 02-23 03-21 03-22 04-29 05-03 05-04 05-05 07-19 08-11 09-20 09-23 10-11 11-03 11-23 12-31'}, 'US': {'2026': '01-01 01-19 02-16 04-03 05-25 06-19 07-03 09-07 11-26 12-25', '2027': '01-01 01-18 02-15 03-26 05-31 06-18 07-05 09-06 11-25 12-24', '2028': '01-17 02-21 04-14 05-29 06-19 07-04 09-04 11-23 12-25'}}
EARLY_CLOSES = {"2026-11-27", "2026-12-24", "2027-11-26", "2028-07-03", "2028-11-24"}

def expected_session(market, now=None):
    market = market.upper()
    local = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo("Asia/Tokyo" if market == "JP" else "America/New_York"))
    close = 930 if market == "JP" else 780 if local.date().isoformat() in EARLY_CLOSES else 960
    day = local.date() if local.hour * 60 + local.minute >= close else local.date() - timedelta(days=1)
    for _ in range(15):
        dates = HOLIDAYS[market].get(str(day.year))
        if dates is None:
            return None
        if day.weekday() < 5 and day.strftime("%m-%d") not in dates.split():
            return day.isoformat()
        day -= timedelta(days=1)
    return None


def completed_history(frame, expected):
    if not expected or frame.empty:
        return frame
    return frame[[stamp.date().isoformat() <= expected for stamp in frame.index]]


def merge_fresh_history(previous, recent, expected):
    """Return None when adjusted prices changed scale; caller must reload full history."""
    import pandas as pd
    recent = completed_history(recent, expected)
    if recent.empty:
        return previous
    if previous.empty:
        return recent
    # Compare by exchange date, as provider timezone representation can differ.
    old = previous.copy(); new = recent.copy()
    old.index = pd.to_datetime([stamp.date() for stamp in old.index])
    new.index = pd.to_datetime([stamp.date() for stamp in new.index])
    overlap = old.index.intersection(new.index)
    # No overlap cannot establish adjusted-price continuity (e.g. an old halted stock).
    if overlap.empty:
        return None
    for col in ("Open", "High", "Low", "Close"):
        if col in old and col in new:
            a, b = old.loc[overlap, col], new.loc[overlap, col]
            if (((a - b).abs() / a.abs().clip(lower=1e-9)) > .001).any():
                return None
    merged = pd.concat([old, new])
    return merged[~merged.index.duplicated(keep="last")].sort_index()


def freshness_summary(built, market, now=None):
    expected = expected_session(market, now)
    dates = Counter(str((r.get("dataQuality") or {}).get("asOf") or "missing") for r in built)
    dated = {day: count for day, count in dates.items() if day != "missing"}
    fresh = sum(1 for r in built if expected and (r.get("dataQuality") or {}).get("asOf") == expected and (r.get("dataQuality") or {}).get("status") == "full")
    return {"expectedSession": expected, "dominantDate": max(dated, key=dated.get) if dated else None, "dateDistribution": dict(sorted(dates.items())), "freshRows": fresh, "freshCoveragePct": round(fresh / len(built) * 100, 1) if built else 0}
