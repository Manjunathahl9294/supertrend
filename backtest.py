"""Backtest the daily+125min Supertrend breakout across Nifty 50, with a param sweep.

Usage:
    python backtest.py            # full sweep, writes results/*.csv
    python backtest.py --quick    # default params only
"""

import argparse
import itertools
import os

import pandas as pd

from data import YF, load_stock
from st_core import find_trades, stats, to_125min

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS, exist_ok=True)

ATR_GRID = [7, 10, 14]
MULT_GRID = [1.5, 2.0, 3.0]
WINDOW_GRID = [1, 2, 3]


def load_universe() -> dict[str, tuple[pd.DataFrame, pd.DataFrame]]:
    book = {}
    for n, sym in enumerate(YF, 1):
        five, daily = load_stock(sym)
        if five.empty or daily.empty:
            print(f"[{n:2}/{len(YF)}] {sym:16} SKIP (no data)")
            continue
        bars = to_125min(five)
        book[sym] = (bars, daily)
        print(f"[{n:2}/{len(YF)}] {sym:16} {len(bars):4} x 125m bars  "
              f"{bars.index[0].date()} -> {bars.index[-1].date()}")
    return book


def run(book, period, mult, window) -> pd.DataFrame:
    rows = []
    for sym, (bars, daily) in book.items():
        for t in find_trades(bars, daily, period, mult, window):
            t["symbol"] = sym.replace(".NS", "")
            rows.append(t)
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="only ATR 10 / mult 3 / window 3")
    args = ap.parse_args()

    print("Downloading Nifty 50 (5-min x 60d, daily x 3y)...\n")
    book = load_universe()
    if not book:
        print("\nNo data downloaded - check your connection and retry.")
        return
    print(f"\n{len(book)} stocks loaded.\n")

    combos = ([(10, 3.0, 3)] if args.quick
              else list(itertools.product(ATR_GRID, MULT_GRID, WINDOW_GRID)))

    sweep, best_trades, best_key = [], None, None
    for period, mult, window in combos:
        tr = run(book, period, mult, window)
        s = stats(tr)
        s.update({"atr": period, "mult": mult, "entry_window": window})
        sweep.append(s)
        print(f"ATR {period:>2} | mult {mult:>3} | win {window} -> "
              f"{s.get('trades', 0):4} trades, "
              f"win {s.get('win_rate', 0):>5}%, "
              f"exp {s.get('expectancy_R', 0):>6} R, "
              f"PF {s.get('profit_factor', 0)}")
        if s.get("trades", 0) >= 30:
            key = s["expectancy_R"]
            if best_key is None or key > best_key:
                best_key, best_trades = key, (tr, s)

    cols = ["atr", "mult", "entry_window", "trades", "win_rate", "expectancy_R",
            "profit_factor", "avg_pct", "avg_win", "avg_loss", "total_pct", "avg_bars"]
    sw = pd.DataFrame(sweep).reindex(columns=cols).sort_values(
        "expectancy_R", ascending=False)
    sw.to_csv(os.path.join(RESULTS, "sweep.csv"), index=False)

    print("\n" + "=" * 78)
    print("TOP 10 PARAMETER SETS (min 30 trades)")
    print("=" * 78)
    print(sw[sw["trades"] >= 30].head(10).to_string(index=False))

    if best_trades is not None:
        tr, s = best_trades
        tr.sort_values("entry_time").to_csv(
            os.path.join(RESULTS, "trades_best.csv"), index=False)
        per_stock = (tr.groupby("symbol")
                       .agg(trades=("pct", "size"),
                            win_rate=("pct", lambda x: round((x > 0).mean() * 100, 1)),
                            total_pct=("pct", lambda x: round(x.sum(), 2)),
                            avg_R=("r", lambda x: round(x.mean(), 2)))
                       .sort_values("total_pct", ascending=False))
        per_stock.to_csv(os.path.join(RESULTS, "per_stock_best.csv"))
        print("\nBest set:", {k: s[k] for k in
                              ("trades", "win_rate", "expectancy_R", "profit_factor")})
        print("\nExit reasons:\n", tr["reason"].value_counts().to_string())
        print("\nPer-stock (best set):\n", per_stock.to_string())

    print(f"\nWritten to {RESULTS}")


if __name__ == "__main__":
    main()
