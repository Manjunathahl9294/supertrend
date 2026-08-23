"""Core: Supertrend, 125-min resampling, signal + trade simulation."""

import numpy as np
import pandas as pd

IST = "Asia/Kolkata"
SESSION_START_MIN = 9 * 60 + 15   # 09:15
BAR_MINUTES = 125                 # 3 bars/day: 09:15, 11:20, 13:25


# ---------------------------------------------------------------- indicators
def atr(df: pd.DataFrame, period: int) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    # Wilder smoothing, as used by TradingView's Supertrend
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def supertrend(df: pd.DataFrame, period: int = 10, mult: float = 3.0) -> pd.DataFrame:
    """Returns DataFrame with columns: st (line), dir (1 green / -1 red)."""
    a = atr(df, period)
    hl2 = (df["High"] + df["Low"]) / 2
    upper = hl2 + mult * a
    lower = hl2 - mult * a

    close = df["Close"].to_numpy(float)
    ub = upper.to_numpy(float)
    lb = lower.to_numpy(float)
    n = len(df)
    fub = np.full(n, np.nan)
    flb = np.full(n, np.nan)
    direction = np.zeros(n, dtype=int)
    st = np.full(n, np.nan)

    start = int(np.argmax(~np.isnan(ub))) if np.isnan(ub).any() else 0
    if np.isnan(ub).all():
        return pd.DataFrame({"st": st, "dir": direction}, index=df.index)

    fub[start], flb[start] = ub[start], lb[start]
    direction[start] = 1
    st[start] = flb[start]

    for i in range(start + 1, n):
        # final bands ratchet in the direction of trend
        fub[i] = ub[i] if (ub[i] < fub[i - 1] or close[i - 1] > fub[i - 1]) else fub[i - 1]
        flb[i] = lb[i] if (lb[i] > flb[i - 1] or close[i - 1] < flb[i - 1]) else flb[i - 1]

        if direction[i - 1] == 1:
            direction[i] = -1 if close[i] < flb[i] else 1
        else:
            direction[i] = 1 if close[i] > fub[i] else -1
        st[i] = flb[i] if direction[i] == 1 else fub[i]

    return pd.DataFrame({"st": st, "dir": direction}, index=df.index)


# ---------------------------------------------------------------- resampling
def to_125min(df5: pd.DataFrame) -> pd.DataFrame:
    """Aggregate 5-min bars into 125-min bars anchored at 09:15 each session.

    Bucketing is time-based (not count-based) so missing 5-min bars do not
    shift the boundaries. NSE 09:15-15:30 = 375 min = exactly 3 bars/day.
    """
    if df5.empty:
        return df5
    idx = df5.index
    mins = np.asarray(idx.hour) * 60 + np.asarray(idx.minute) - SESSION_START_MIN
    bucket = np.clip(mins, 0, None) // BAR_MINUTES
    start_min = SESSION_START_MIN + bucket * BAR_MINUTES
    key = pd.to_datetime(idx.date.astype(str)) + pd.to_timedelta(start_min, unit="m")
    key = key.tz_localize(IST)

    out = df5.groupby(key).agg(
        Open=("Open", "first"),
        High=("High", "max"),
        Low=("Low", "min"),
        Close=("Close", "last"),
        Volume=("Volume", "sum"),
    )
    out.index.name = "Datetime"
    return out.dropna()


# ---------------------------------------------------------------- strategy
def daily_green_map(daily: pd.DataFrame, period: int, mult: float) -> pd.Series:
    """date -> was the DAILY supertrend green at the previous day's close.

    Uses the previous completed daily bar, so an intraday signal on day D never
    peeks at day D's own daily close.
    """
    st = supertrend(daily, period, mult)
    prev = st["dir"].shift(1)
    prev.index = pd.to_datetime(prev.index).date
    return prev


def find_trades(
    bars: pd.DataFrame,
    daily: pd.DataFrame,
    period: int = 10,
    mult: float = 3.0,
    entry_window: int = 3,
) -> list[dict]:
    """Long-only.

    Setup   : 125-min supertrend flips red->green while daily supertrend is green.
    Entry   : break of the signal candle's HIGH, within `entry_window` later bars.
    Stop    : signal candle's LOW.
    Target  : exit when the 125-min supertrend flips back to red (exit at close).
    """
    st = supertrend(bars, period, mult)
    bars = bars.join(st)
    dg = daily_green_map(daily, period, mult)

    o = bars["Open"].to_numpy(float)
    h = bars["High"].to_numpy(float)
    lo = bars["Low"].to_numpy(float)
    c = bars["Close"].to_numpy(float)
    d = bars["dir"].to_numpy(int)
    ts = bars.index
    n = len(bars)

    trades: list[dict] = []
    i = 1
    while i < n:
        flip_green = d[i] == 1 and d[i - 1] == -1
        if not flip_green:
            i += 1
            continue
        if dg.get(ts[i].date(), 0) != 1:      # daily filter
            i += 1
            continue

        trigger, stop = h[i], lo[i]
        if stop >= trigger:
            i += 1
            continue

        # --- wait for the high breakout
        entry_idx = None
        for j in range(i + 1, min(i + 1 + entry_window, n)):
            if d[j] == -1:                     # setup invalidated before entry
                break
            if h[j] >= trigger:
                entry_idx = j
                break
        if entry_idx is None:
            i += 1
            continue

        entry = max(trigger, o[entry_idx])     # gap-up fills at the open
        # --- manage the position
        exit_idx, exit_px, reason = None, None, None
        for k in range(entry_idx, n):
            if lo[k] <= stop and not (k == entry_idx and o[k] <= stop):
                exit_idx, exit_px, reason = k, min(stop, o[k]), "SL"
                break
            if d[k] == -1:
                exit_idx, exit_px, reason = k, c[k], "ST_FLIP"
                break
        if exit_idx is None:
            exit_idx, exit_px, reason = n - 1, c[n - 1], "OPEN"

        risk = entry - stop
        trades.append({
            "signal_time": ts[i], "entry_time": ts[entry_idx], "exit_time": ts[exit_idx],
            "entry": entry, "stop": stop, "exit": exit_px, "reason": reason,
            "pct": (exit_px - entry) / entry * 100,
            "r": (exit_px - entry) / risk if risk > 0 else np.nan,
            "bars_held": exit_idx - entry_idx,
        })
        i = exit_idx + 1                       # one position at a time per stock

    return trades


def stats(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"trades": 0}
    wins = trades[trades["pct"] > 0]
    losses = trades[trades["pct"] <= 0]
    gp, gl = wins["pct"].sum(), abs(losses["pct"].sum())
    return {
        "trades": len(trades),
        "win_rate": round(len(wins) / len(trades) * 100, 1),
        "avg_pct": round(trades["pct"].mean(), 3),
        "avg_win": round(wins["pct"].mean(), 2) if len(wins) else 0.0,
        "avg_loss": round(losses["pct"].mean(), 2) if len(losses) else 0.0,
        "expectancy_R": round(trades["r"].mean(), 3),
        "profit_factor": round(gp / gl, 2) if gl > 0 else np.inf,
        "total_pct": round(trades["pct"].sum(), 1),
        "avg_bars": round(trades["bars_held"].mean(), 1),
    }
