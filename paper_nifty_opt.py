"""Live paper trader: NIFTY 15-min Supertrend flip -> 8 option structures.

Stateless by design: on every run it recomputes the whole signal history from
the 15-min feed and rewrites the book. That makes a missed cron tick harmless
and keeps the book reproducible from data alone.
"""

import datetime as dt
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest_nifty_opt import load, summarise  # noqa: E402
from nifty_opt.options import LOT, atm_strike, evaluate, weekly_expiry  # noqa: E402
from nifty_opt.signals import find_signals  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK = os.path.join(HERE, "paper_nifty_book.json")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
START = os.environ.get("PAPER_START", "")     # ISO date; only count trades from here


def build():
    bars, daily = load()
    sigs = find_signals(bars)
    last_bar = bars.index[-1]

    rows = []
    for t in sigs:
        for name, o in evaluate(t, daily, bars["Close"]).items():
            rows.append({
                "side": t["side"], "structure": name,
                "signal_time": str(t["signal_time"]), "entry_time": str(t["entry_time"]),
                "exit_time": str(t["exit_time"]), "reason": t["reason"],
                "spot_entry": t["spot_entry"], "spot_stop": t["spot_stop"],
                "spot_exit": t["spot_exit"], "points": t["points"], "r": t["r"],
                "strike": o["strike"], "expiry": str(o["expiry"]),
                "prem_in": o["prem_in"], "prem_out": o["prem_out"],
                "pnl_rs": o["pnl_rs"], "rolls": o["rolls"],
                # a trade whose exit is the last bar has not actually closed yet
                "open": t["reason"] == "OPEN",
            })

    df = pd.DataFrame(rows)
    if START and not df.empty:
        df = df[df.entry_time >= START]

    closed = df[~df.open] if not df.empty else df
    live = df[df.open] if not df.empty else df

    summ = summarise(closed) if len(closed) else pd.DataFrame()
    book = {
        "generated": dt.datetime.now(IST).isoformat(timespec="seconds"),
        "last_bar": str(last_bar),
        "spot": round(float(bars["Close"].iloc[-1]), 2),
        "paper_start": START or str(df.entry_time.min()) if len(df) else START,
        "lot": LOT,
        "open_positions": live.to_dict("records") if len(live) else [],
        "closed_trades": closed.to_dict("records") if len(closed) else [],
        "summary": summ.to_dict("records") if len(summ) else [],
        # each signal fans out into 4 structures for its side, so the trade
        # count is the number of distinct signals, not the number of legs
        "totals": {
            "closed": int(closed.entry_time.nunique()) if len(closed) else 0,
            "open": int(live.entry_time.nunique()) if len(live) else 0,
            "best_structure": (summ.iloc[0]["structure"] if len(summ) else None),
            "best_rs": int(summ.iloc[0]["total_pnl_rs"]) if len(summ) else 0,
        },
    }
    return book


if __name__ == "__main__":
    b = build()
    json.dump(b, open(BOOK, "w"), indent=2, default=str)
    print(f"spot {b['spot']}  last bar {b['last_bar']}")
    t = b["totals"]
    print(f"closed signals {t['closed']}  open {t['open']}")
    print(f"best structure: {t['best_structure']}  Rs {t['best_rs']:,}")
