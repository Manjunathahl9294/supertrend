"""15-min Supertrend flip signals on NIFTY 50 index (both directions)."""

import numpy as np
import pandas as pd

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from st_core import supertrend  # noqa: E402

IST = "Asia/Kolkata"


def find_signals(bars: pd.DataFrame, period: int = 10, mult: float = 3.0,
                 entry_window: int = 3) -> list[dict]:
    """Both-sided Supertrend flip breakout on the index.

    LONG  : ST flips red->green. Trigger = flip candle HIGH, taken within the
            next `entry_window` candles. Stop = flip candle LOW.
            Exit  = ST flips back to red (at that candle's close).
    SHORT : mirror image (flip green->red, trigger = LOW, stop = HIGH,
            exit on flip back to green).

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

    out: list[dict] = []
    i = 1
    while i < n:
        flipped = d[i] != d[i - 1] and d[i - 1] != 0
        if not flipped:
            i += 1
            continue

        side = "LONG" if d[i] == 1 else "SHORT"
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
            "signal_time": ts[i], "entry_time": ts[entry_idx], "exit_time": ts[exit_idx],
            "spot_entry": round(entry, 2), "spot_stop": round(stop, 2),
            "spot_exit": round(exit_px, 2), "reason": reason,
            "points": round(pts, 2), "risk_pts": round(risk, 2),
            "r": round(pts / risk, 3) if risk > 0 else np.nan,
            "bars_held": exit_idx - entry_idx,
        })
        i = exit_idx + 1               # one position at a time

    return out
