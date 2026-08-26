"""Black-Scholes option overlay for NIFTY index signals.

WHY MODELLED, NOT HISTORICAL: yfinance exposes no historical NIFTY option
chain. Every option premium below is therefore a Black-Scholes *model* price
computed off the actual index path, with IV estimated from realised
volatility. Directional P&L and payoff shape are faithful; the absolute
premium of any single leg is an estimate, not a filled price.
"""

import numpy as np
import pandas as pd

LOT = 75                 # NIFTY contract multiplier
STRIKE_STEP = 50         # NIFTY strikes
WING = 200               # spread width in index points
RF = 0.065               # risk-free rate
SLIP_PCT = 0.01          # 1% of premium each way (brokerage + bid/ask)
IV_FLOOR, IV_CAP = 0.09, 0.35
VRP = 1.15               # implied sits above realised


def _nd(x):
    return 0.5 * (1.0 + np.vectorize(_erf)(x / np.sqrt(2.0)))


def _erf(x):
    import math
    return math.erf(x)


def bs_price(S, K, T, iv, kind):
    """Black-Scholes price. T in years. kind in {'C','P'}."""
    S, K = float(S), float(K)
    T = max(float(T), 1e-6)
    iv = max(float(iv), 1e-4)
    d1 = (np.log(S / K) + (RF + 0.5 * iv ** 2) * T) / (iv * np.sqrt(T))
    d2 = d1 - iv * np.sqrt(T)
    disc = np.exp(-RF * T)
    if kind == "C":
        return float(S * _nd(d1) - K * disc * _nd(d2))
    return float(K * disc * _nd(-d2) - S * _nd(-d1))


def atm_strike(spot):
    return int(round(spot / STRIKE_STEP) * STRIKE_STEP)


def weekly_expiry(ts: pd.Timestamp) -> pd.Timestamp:
    """Nearest NIFTY weekly expiry (Thursday 15:30 IST).

    Rolls to next week once we are past Thursday's close, so a trade never
    prices against an expiry that has already settled.
    """
    d = ts.normalize()
    ahead = (3 - d.weekday()) % 7          # 3 = Thursday
    exp = d + pd.Timedelta(days=ahead)
    exp = exp.replace(hour=15, minute=30)
    if ts >= exp:
        exp = exp + pd.Timedelta(days=7)
    return exp


def realised_iv(daily: pd.DataFrame, asof, lookback: int = 20) -> float:
    """EWMA realised vol of daily closes, annualised, scaled by the VRP."""
    c = daily["Close"]
    c = c[c.index <= pd.Timestamp(asof).tz_localize(None).normalize()]
    r = np.log(c / c.shift(1)).dropna().tail(lookback)
    if len(r) < 5:
        return 0.13
    rv = float(r.std() * np.sqrt(252))
    return float(np.clip(rv * VRP, IV_FLOOR, IV_CAP))


def yearfrac(now, expiry) -> float:
    return max((pd.Timestamp(expiry) - pd.Timestamp(now)).total_seconds() / (365 * 24 * 3600), 1e-6)


# ------------------------------------------------------------------ structures
def legs_for(side: str, K: int) -> dict[str, list[tuple]]:
    """(kind, strike, qty) per structure. qty +1 = long, -1 = short."""
    if side == "LONG":
        return {
            "naked_call_buy":   [("C", K, +1)],
            "naked_put_sell":   [("P", K, -1)],
            "bull_call_spread": [("C", K, +1), ("C", K + WING, -1)],
            "bull_put_spread":  [("P", K, -1), ("P", K - WING, +1)],
        }
    return {
        "naked_put_buy":    [("P", K, +1)],
        "naked_call_sell":  [("C", K, -1)],
        "bear_call_spread": [("C", K, -1), ("C", K + WING, +1)],
        "bear_put_spread":  [("P", K, +1), ("P", K - WING, -1)],
    }


def price_structure(legs, S, T, iv) -> float:
    """Net premium per unit of index (positive = debit paid)."""
    return sum(q * bs_price(S, K, T, iv, kind) for kind, K, q in legs)


def _segments(t_in, t_out, spot_path: pd.Series):
    """Split a holding period at each weekly expiry.

    A position carried through Thursday 15:30 is settled there and re-opened
    ATM in the next series. Without this the model would hand a long-held
    option MORE time value at exit than it paid at entry.
    """
    segs = []
    cur, exp = pd.Timestamp(t_in), weekly_expiry(t_in)
    while exp < pd.Timestamp(t_out):
        segs.append((cur, exp, exp))
        cur = exp
        exp = weekly_expiry(exp + pd.Timedelta(minutes=1))
    segs.append((cur, pd.Timestamp(t_out), exp))
    return segs


def _spot_at(spot_path: pd.Series, ts, fallback):
    if spot_path is None or spot_path.empty:
        return fallback
    s = spot_path[spot_path.index <= ts]
    return float(s.iloc[-1]) if len(s) else fallback


def evaluate(trade: dict, daily: pd.DataFrame, spot_path: pd.Series | None = None) -> dict[str, dict]:
    """Price every structure across the holding period, rolling at expiry."""
    t_in, t_out = pd.Timestamp(trade["entry_time"]), pd.Timestamp(trade["exit_time"])
    S_in, S_out = trade["spot_entry"], trade["spot_exit"]

    K0 = atm_strike(S_in)
    exp0 = weekly_expiry(t_in)
    iv0 = realised_iv(daily, t_in)
    segs = _segments(t_in, t_out, spot_path)

    res = {}
    for name in legs_for(trade["side"], K0):
        total_net = 0.0
        p_in_first = p_out_last = None

        for si, (a, b, exp) in enumerate(segs):
            Sa = S_in if si == 0 else _spot_at(spot_path, a, S_in)
            Sb = S_out if si == len(segs) - 1 else _spot_at(spot_path, b, S_out)
            K = atm_strike(Sa)                     # re-strike ATM on each roll
            legs = legs_for(trade["side"], K)[name]
            iv = realised_iv(daily, a)

            p_a = price_structure(legs, Sa, yearfrac(a, exp), iv)
            # at expiry the option is worth intrinsic only
            p_b = (price_structure(legs, Sb, yearfrac(b, exp), realised_iv(daily, b))
                   if b < exp else
                   sum(q * max(0.0, (Sb - K_) if kind == "C" else (K_ - Sb))
                       for kind, K_, q in legs))

            total_net += (p_b - p_a) - SLIP_PCT * (abs(p_a) + abs(p_b))
            if si == 0:
                p_in_first = p_a
            p_out_last = p_b

        res[name] = {
            "strike": K0, "expiry": exp0, "iv": round(iv0, 4),
            "rolls": len(segs) - 1,
            "prem_in": round(p_in_first, 2), "prem_out": round(p_out_last, 2),
            "pnl_pts": round(total_net, 2),
            "pnl_rs": round(total_net * LOT, 0),
            "debit": p_in_first > 0,
        }
    return res
