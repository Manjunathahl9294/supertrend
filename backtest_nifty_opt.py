"""Backtest: NIFTY 50 15-min Supertrend flip -> option structures."""

import json
import os
import sys

import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nifty_opt.options import LOT, evaluate  # noqa: E402
from nifty_opt.signals import find_signals  # noqa: E402

OUT = os.path.join("results", "nifty_opt")
STRUCTS = ["naked_call_buy", "naked_put_sell", "bull_call_spread", "bull_put_spread",
           "naked_put_buy", "naked_call_sell", "bear_call_spread", "bear_put_spread"]


def load():
    i = yf.download("^NSEI", period="60d", interval="15m",
                    auto_adjust=False, progress=False, threads=False)
    d = yf.download("^NSEI", period="2y", interval="1d",
                    auto_adjust=False, progress=False, threads=False)
    for x in (i, d):
        if isinstance(x.columns, pd.MultiIndex):
            x.columns = x.columns.get_level_values(0)
    cols = ["Open", "High", "Low", "Close", "Volume"]
    return i[cols].dropna(), d[cols].dropna()


def run(period=10, mult=3.0, entry_window=3):
    bars, daily = load()
    sigs = find_signals(bars, period, mult, entry_window)
    if not sigs:
        return pd.DataFrame(), pd.DataFrame(), {}

    rows = []
    for t in sigs:
        opts = evaluate(t, daily, bars["Close"])
        for name, o in opts.items():
            rows.append({**{k: t[k] for k in
                            ("side", "signal_time", "entry_time", "exit_time",
                             "spot_entry", "spot_stop", "spot_exit", "reason",
                             "points", "risk_pts", "r")},
                         "structure": name, **o})

    trades = pd.DataFrame(rows)
    idx = pd.DataFrame(sigs)
    meta = {"bars": len(bars), "from": str(bars.index[0]), "to": str(bars.index[-1]),
            "signals": len(sigs), "lot": LOT,
            "params": {"period": period, "mult": mult, "entry_window": entry_window}}
    return trades, idx, meta


def summarise(trades: pd.DataFrame) -> pd.DataFrame:
    out = []
    for name, g in trades.groupby("structure"):
        w = g[g.pnl_rs > 0]
        gp, gl = w.pnl_rs.sum(), abs(g[g.pnl_rs <= 0].pnl_rs.sum())
        eq = g.sort_values("exit_time").pnl_rs.cumsum()
        out.append({
            "structure": name,
            "trades": len(g),
            "win_rate_%": round(len(w) / len(g) * 100, 1),
            "total_pnl_rs": int(g.pnl_rs.sum()),
            "avg_pnl_rs": int(g.pnl_rs.mean()),
            "best_rs": int(g.pnl_rs.max()),
            "worst_rs": int(g.pnl_rs.min()),
            "profit_factor": round(gp / gl, 2) if gl else float("inf"),
            "max_dd_rs": int((eq - eq.cummax()).min()),
        })
    return (pd.DataFrame(out)
            .sort_values("total_pnl_rs", ascending=False)
            .reset_index(drop=True))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    trades, idx, meta = run()
    if trades.empty:
        print("no signals")
        raise SystemExit(0)

    summ = summarise(trades)
    trades.to_csv(f"{OUT}/option_trades.csv", index=False)
    idx.to_csv(f"{OUT}/index_signals.csv", index=False)
    summ.to_csv(f"{OUT}/summary.csv", index=False)
    meta["index_stats"] = {
        "total_points": round(idx.points.sum(), 1),
        "win_rate_%": round((idx.points > 0).mean() * 100, 1),
        "long": int((idx.side == "LONG").sum()),
        "short": int((idx.side == "SHORT").sum()),
        "sl_exits": int((idx.reason == "SL").sum()),
        "flip_exits": int((idx.reason == "ST_FLIP").sum()),
    }
    json.dump(meta, open(f"{OUT}/meta.json", "w"), indent=2, default=str)

    print(f"\n{meta['from'][:10]} -> {meta['to'][:10]}  |  {meta['signals']} signals "
          f"({meta['index_stats']['long']}L / {meta['index_stats']['short']}S)")
    print(f"index: {meta['index_stats']['total_points']} pts, "
          f"win {meta['index_stats']['win_rate_%']}%, "
          f"{meta['index_stats']['sl_exits']} SL / {meta['index_stats']['flip_exits']} flip\n")
    print(summ.to_string(index=False))
