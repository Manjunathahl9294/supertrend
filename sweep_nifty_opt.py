"""Parameter robustness sweep for the Nifty option strategy."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest_nifty_opt import OUT, run, summarise  # noqa: E402


def sweep(mults=(2.0, 2.5, 3.0, 3.5), windows=(2, 3), period=10):
    rows = []
    for m in mults:
        for w in windows:
            tr, idx, _ = run(period, m, w)
            if tr.empty:
                continue
            s = summarise(tr).set_index("structure")
            rows.append({
                "mult": m, "entry_window": w, "signals": len(idx),
                "index_pts": round(idx.points.sum(), 1),
                "index_win_%": round((idx.points > 0).mean() * 100, 1),
                **{k: int(s.loc[k, "total_pnl_rs"]) for k in s.index},
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    df = sweep()
    df.to_csv(f"{OUT}/sweep.csv", index=False)
    print(df.to_string(index=False))
