"""Does a higher-timeframe Supertrend filter improve the 15-min flip strategy?

Runs the baseline against several HTF lengths and multipliers and writes the
comparison to results/nifty_opt/htf_compare.csv.
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest_nifty_opt import OUT, run, summarise  # noqa: E402

KEY = ["naked_call_buy", "naked_put_sell", "bull_call_spread", "naked_put_buy"]


def compare(htfs=(None, 30, 45, 60, 75, 125), mults=(2.5, 3.0, 3.5)):
    rows = []
    for htf in htfs:
        for m in mults:
            tr, idx, _ = run(10, m, 3, htf)
            if tr.empty:
                continue
            s = summarise(tr).set_index("structure")
            rows.append({
                "htf_min": htf or 0, "mult": m, "signals": len(idx),
                "long": int((idx.side == "LONG").sum()),
                "short": int((idx.side == "SHORT").sum()),
                "index_pts": round(idx.points.sum(), 1),
                "index_win_%": round((idx.points > 0).mean() * 100, 1),
                **{k: (int(s.loc[k, "total_pnl_rs"]) if k in s.index else 0) for k in KEY},
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    df = compare()
    df.to_csv(f"{OUT}/htf_compare.csv", index=False)
    print(df.to_string(index=False))
    base = df[df.htf_min == 0].index_pts.max()
    print(f"\nbest baseline index pts: {base:+.1f}")
    print(f"best filtered index pts: {df[df.htf_min > 0].index_pts.max():+.1f}")
