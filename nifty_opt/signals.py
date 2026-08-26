"""15-min Supertrend flip signals on NIFTY 50 index (both directions)."""

import numpy as np
import pandas as pd

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from st_core import supertrend  # noqa: E402

IST = "Asia/Kolkata"


def find_signals(bars: pd.DataFrame, period: int = 10, mult: float = 3.0,
                 entry_window: int = 3, htf_minutes: int | None = None) -> list[dict]:
    """Both-sided Supertrend flip breakout on the index.

    LONG  : ST flips red->green. Trigger = flip candle HIGH, taken within the
            next `entry_window` candles. Stop = flip candle LOW.
            Exit  = ST flips back to red (at that candle's close).
    SHORT : mirror image (flip green->red, trigger = LOW, stop = HIGH,
            exit on flip back to green).

    If `htf_minutes` is set (e.g. 75), a flip is only taken when the higher
    timeframe's Supertrend already points the same way, using the last
    COMPLETED higher-timeframe bar so no future information leaks in.

    Returns index-level trades; the option overlay is applied separately.
    """
    st = supertrend(bars, period, mult)
    b = bars.join(st)

    o = b["Open"].to_numpy(float)
    h = b["High"].to_numpy(float)
    l = b["Low"].to_numpy(float)
    c = b["Close"].to_numpy(float)
    d = b["dir"].to_numpy(int)
    ts = b.index
    n = len(b)

    htf = (htf_direction(bars, period, mult, htf_minutes).to_numpy(float)
           if htf_minutes else None)

    out: list[dict] = []
    i = 1
    while i < n:
        flipped = d[i] != d[i - 1] and d[i - 1] != 0
        if not flipped:
            i += 1
            continue

        side = "LONG" if d[i] == 1 else "SHORT"
        if htf is not None and htf[i] != d[i]:   # higher timeframe disagrees
            i += 1
            continue
        if side == "LONG":
            trigger, stop = h[i], l[i]
        else:
            trigger, stop = l[i], h[i]
        if trigger == stop:
            i += 1
            continue

        # --- wait up to entry_window candles for the break of the flip candle
        entry_idx = None
        for j in range(i + 1, min(i + 1 + entry_window, n)):
            if d[j] != d[i]:          # setup invalidated before we got filled
                break
            hit = h[j] >= trigger if side == "LONG" else l[j] <= trigger
            if hit:
                entry_idx = j
                break
        if entry_idx is None:
            i += 1
            continue

        # gap through the trigger fills at the open
        entry = (max(trigger, o[entry_idx]) if side == "LONG"
                 else min(trigger, o[entry_idx]))

        # --- manage: stop-loss vs supertrend flip back
        exit_idx = exit_px = reason = None
        for k in range(entry_idx, n):
            if side == "LONG":
                stopped = l[k] <= stop and not (k == entry_idx and o[k] <= stop)
                fill = min(stop, o[k])
            else:
                stopped = h[k] >= stop and not (k == entry_idx and o[k] >= stop)
                fill = max(stop, o[k])
            if stopped:
                exit_idx, exit_px, reason = k, fill, "SL"
                break
            if d[k] != d[i]:
                exit_idx, exit_px, reason = k, c[k], "ST_FLIP"
                break
        if exit_idx is None:
            exit_idx, exit_px, reason = n - 1, c[n - 1], "OPEN"

        risk = abs(entry - stop)
        pts = (exit_px - entry) if side == "LONG" else (entry - exit_px)
        out.append({
            "side": side,
            "htf_dir": int(htf[i]) if htf is not None else 0,
            "signal_time": ts[i], "entry_time": ts[entry_idx], "exit_time": ts[exit_idx],
            "spot_entry": round(entry, 2), "spot_stop": round(stop, 2),
            "spot_exit": round(exit_px, 2), "reason": reason,
            "points": round(pts, 2), "risk_pts": round(risk, 2),
            "r": round(pts / risk, 3) if risk > 0 else np.nan,
            "bars_held": exit_idx - entry_idx,
        })
        i = exit_idx + 1               # one position at a time

    return out


# ------------------------------------------------------------------ HTF filter
HTF_MINUTES = 75          # 375-min NSE session = exactly 5 bars/day


def to_htf(bars15: pd.DataFrame, minutes: int = HTF_MINUTES) -> pd.DataFrame:
    """Aggregate 15-min bars into higher-timeframe bars anchored at 09:15.

    Time-based bucketing (not count-based) so a missing 15-min bar cannot shift
    the boundaries for the rest of the session.
    """
    if bars15.empty:
        return bars15
    idx = bars15.index
    mins = np.asarray(idx.hour) * 60 + np.asarray(idx.minute) - (9 * 60 + 15)
    bucket = np.clip(mins, 0, None) // minutes
    start = (9 * 60 + 15) + bucket * minutes
    key = pd.to_datetime(idx.date.astype(str)) + pd.to_timedelta(start, unit="m")
    key = key.tz_localize(IST)

    out = bars15.groupby(key).agg(
        Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"),
        Close=("Close", "last"), Volume=("Volume", "sum"),
    )
    out.index.name = "Datetime"
    return out.dropna()


def htf_direction(bars15: pd.DataFrame, period: int = 10, mult: float = 3.0,
                  minutes: int = HTF_MINUTES) -> pd.Series:
    """Higher-timeframe Supertrend direction, as known to a 15-min bar.

    The 75-min bar containing a given 15-min candle is still forming at that
    moment, so its direction is not yet knowable. We therefore forward-fill the
    LAST COMPLETED 75-min bar's direction onto each 15-min timestamp: the value
    is stamped at the HTF bar's close and only becomes visible after it.
    """
    htf = to_htf(bars15, minutes)
    d = supertrend(htf, period, mult)["dir"]

    # a bar opening at T closes at T+minutes; its direction is usable from then on
    stamped = d.copy()
    stamped.index = d.index + pd.Timedelta(minutes=minutes)
    return stamped.reindex(bars15.index, method="ffill")
