from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class SimulationConfig:
    """Conservative assumptions for a long-only daily-bar simulation."""

    fee_bps_per_side: float = 5.0
    slippage_bps_per_side: float = 10.0
    max_hold_sessions: int = 20
    target_r: float = 2.0

    def as_dict(self) -> dict[str, float | int]:
        return asdict(self)


def number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _signal_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _prepared_bars(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    bars = frame.copy()
    bars.index = pd.to_datetime(bars.index, errors="coerce")
    bars = bars.loc[~bars.index.isna()].sort_index()
    required = {"Open", "High", "Low", "Close"}
    if not required.issubset(bars.columns):
        return pd.DataFrame()
    for column in required:
        bars[column] = pd.to_numeric(bars[column], errors="coerce")
    return bars.dropna(subset=["Open", "High", "Low", "Close"])


def _fill_price(price: float, side: str, slippage_rate: float) -> float:
    multiplier = 1 + slippage_rate if side == "buy" else 1 - slippage_rate
    return price * multiplier


def _trade_result(
    *,
    status: str,
    entry_date: str | None = None,
    entry_price: float | None = None,
    exit_date: str | None = None,
    exit_price: float | None = None,
    stop: float | None = None,
    target: float | None = None,
    exit_reason: str | None = None,
    closed: bool = False,
    fee_rate: float = 0.0,
) -> dict[str, Any]:
    gross_return = None
    net_return = None
    risk_pct = None
    r_multiple = None
    if entry_price and exit_price:
        gross_return = (exit_price / entry_price - 1) * 100
        entry_cost = entry_price * (1 + fee_rate)
        exit_proceeds = exit_price * (1 - fee_rate)
        net_return = (exit_proceeds / entry_cost - 1) * 100
        if stop is not None and stop < entry_price:
            stop_proceeds = stop * (1 - fee_rate)
            risk_pct = (entry_cost - stop_proceeds) / entry_cost * 100
            if risk_pct > 0:
                r_multiple = net_return / risk_pct
    return {
        "status": status,
        "closed": closed,
        "entryDate": entry_date,
        "entryPrice": round(entry_price, 4) if entry_price is not None else None,
        "exitDate": exit_date,
        "exitPrice": round(exit_price, 4) if exit_price is not None else None,
        "exitReason": exit_reason,
        "stop": round(stop, 4) if stop is not None else None,
        "target": round(target, 4) if target is not None else None,
        "grossReturnPct": round(gross_return, 3) if gross_return is not None else None,
        "netReturnPct": round(net_return, 3) if net_return is not None else None,
        "riskPct": round(risk_pct, 3) if risk_pct is not None else None,
        "rMultiple": round(r_multiple, 3) if r_multiple is not None else None,
    }


def simulate_long_trade(
    frame: pd.DataFrame,
    signal_date: str | date,
    initial_stop: float,
    target: float | None = None,
    *,
    config: SimulationConfig | None = None,
    terminal_event: str | None = None,
) -> dict[str, Any]:
    """Simulate one long trade without using the signal bar for execution.

    Entry is the next available session's open. If a daily bar touches both the
    stop and target, the stop is assumed to have filled first. This intentionally
    biases ambiguous daily-bar results against the strategy.
    """

    cfg = config or SimulationConfig()
    bars = _prepared_bars(frame)
    stop = number(initial_stop)
    try:
        detected = _signal_date(signal_date)
    except ValueError:
        return _trade_result(status="invalid_signal_date")
    if bars.empty or stop is None:
        return _trade_result(status="missing_history")

    future = bars.loc[[timestamp.date() > detected for timestamp in bars.index]]
    if future.empty:
        return _trade_result(status="pending_next_session", stop=stop, target=number(target))

    fee_rate = max(0.0, cfg.fee_bps_per_side) / 10_000
    slippage_rate = max(0.0, cfg.slippage_bps_per_side) / 10_000
    entry_bar = future.iloc[0]
    entry_timestamp = future.index[0]
    entry_price = _fill_price(float(entry_bar["Open"]), "buy", slippage_rate)
    if stop >= entry_price:
        return _trade_result(
            status="invalid_stop",
            entry_date=entry_timestamp.date().isoformat(),
            entry_price=entry_price,
            stop=stop,
            target=number(target),
            fee_rate=fee_rate,
        )

    target_price = number(target)
    if target_price is None or target_price <= entry_price:
        target_price = entry_price + (entry_price - stop) * max(0.5, cfg.target_r)

    observed = future.iloc[: max(1, cfg.max_hold_sessions)]
    for timestamp, bar in observed.iterrows():
        open_price = float(bar["Open"])
        low = float(bar["Low"])
        high = float(bar["High"])
        session = timestamp.date().isoformat()

        if open_price <= stop:
            exit_price = _fill_price(open_price, "sell", slippage_rate)
            return _trade_result(
                status="closed",
                entry_date=entry_timestamp.date().isoformat(),
                entry_price=entry_price,
                exit_date=session,
                exit_price=exit_price,
                stop=stop,
                target=target_price,
                exit_reason="stop_gap",
                closed=True,
                fee_rate=fee_rate,
            )
        if open_price >= target_price:
            exit_price = _fill_price(target_price, "sell", slippage_rate)
            return _trade_result(
                status="closed",
                entry_date=entry_timestamp.date().isoformat(),
                entry_price=entry_price,
                exit_date=session,
                exit_price=exit_price,
                stop=stop,
                target=target_price,
                exit_reason="target_gap_conservative",
                closed=True,
                fee_rate=fee_rate,
            )

        stop_hit = low <= stop
        target_hit = high >= target_price
        if stop_hit:
            reason = "ambiguous_bar_stop_first" if target_hit else "stop"
            exit_price = _fill_price(stop, "sell", slippage_rate)
            return _trade_result(
                status="closed",
                entry_date=entry_timestamp.date().isoformat(),
                entry_price=entry_price,
                exit_date=session,
                exit_price=exit_price,
                stop=stop,
                target=target_price,
                exit_reason=reason,
                closed=True,
                fee_rate=fee_rate,
            )
        if target_hit:
            exit_price = _fill_price(target_price, "sell", slippage_rate)
            return _trade_result(
                status="closed",
                entry_date=entry_timestamp.date().isoformat(),
                entry_price=entry_price,
                exit_date=session,
                exit_price=exit_price,
                stop=stop,
                target=target_price,
                exit_reason="target",
                closed=True,
                fee_rate=fee_rate,
            )

    last_timestamp = observed.index[-1]
    last_close = float(observed.iloc[-1]["Close"])
    if len(observed) >= cfg.max_hold_sessions:
        exit_price = _fill_price(last_close, "sell", slippage_rate)
        return _trade_result(
            status="closed",
            entry_date=entry_timestamp.date().isoformat(),
            entry_price=entry_price,
            exit_date=last_timestamp.date().isoformat(),
            exit_price=exit_price,
            stop=stop,
            target=target_price,
            exit_reason="max_hold",
            closed=True,
            fee_rate=fee_rate,
        )

    if terminal_event == "delisted":
        exit_price = _fill_price(last_close, "sell", slippage_rate)
        return _trade_result(
            status="closed_terminal_event",
            entry_date=entry_timestamp.date().isoformat(),
            entry_price=entry_price,
            exit_date=last_timestamp.date().isoformat(),
            exit_price=exit_price,
            stop=stop,
            target=target_price,
            exit_reason="delisted_last_available_close",
            closed=True,
            fee_rate=fee_rate,
        )

    mark_price = _fill_price(last_close, "sell", slippage_rate)
    return _trade_result(
        status="open",
        entry_date=entry_timestamp.date().isoformat(),
        entry_price=entry_price,
        exit_date=last_timestamp.date().isoformat(),
        exit_price=mark_price,
        stop=stop,
        target=target_price,
        exit_reason="mark_to_market",
        closed=False,
        fee_rate=fee_rate,
    )
