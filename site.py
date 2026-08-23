"""Render paper_book.json as a mobile-friendly static page -> docs/index.html.

GitHub Pages serves docs/ directly, so the scan workflow just commits the file.
"""

import datetime as dt
import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK_FILE = os.path.join(HERE, "paper_book.json")
OUT_DIR = os.path.join(HERE, "docs")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0e1117;--card:#171b23;--line:#262c38;--tx:#e6e9ef;--dim:#8b94a7;
  --up:#26a96c;--dn:#e5484d;--amber:#e8a33d;--accent:#4c8dff;
}
body{background:var(--bg);color:var(--tx);font:15px/1.5 -apple-system,BlinkMacSystemFont,
  "Segoe UI",Roboto,sans-serif;padding:14px;max-width:900px;margin:0 auto;
  -webkit-text-size-adjust:100%}
h1{font-size:19px;letter-spacing:-.2px}
h2{font-size:14px;text-transform:uppercase;letter-spacing:.8px;color:var(--dim);
  margin:26px 0 10px}
.sub{color:var(--dim);font-size:12.5px;margin-top:4px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(94px,1fr));gap:8px;
  margin-top:14px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px}
.kpi .v{font-size:19px;font-weight:650;letter-spacing:-.3px}
.kpi .l{font-size:10.5px;color:var(--dim);text-transform:uppercase;letter-spacing:.5px;
  margin-top:3px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
  padding:11px 12px;margin-bottom:8px}
.row{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.sym{font-weight:650;font-size:15.5px}
.big{font-size:15.5px;font-weight:650;font-variant-numeric:tabular-nums}
.meta{color:var(--dim);font-size:12px;margin-top:5px;font-variant-numeric:tabular-nums}
.up{color:var(--up)}.dn{color:var(--dn)}.amber{color:var(--amber)}.dim{color:var(--dim)}
.tag{font-size:10px;padding:2px 6px;border-radius:5px;border:1px solid var(--line);
  color:var(--dim);text-transform:uppercase;letter-spacing:.5px}
.empty{color:var(--dim);font-size:13.5px;padding:14px;text-align:center;
  border:1px dashed var(--line);border-radius:10px}
table{width:100%;border-collapse:collapse;font-size:13px;
  font-variant-numeric:tabular-nums}
th{text-align:right;color:var(--dim);font-weight:500;font-size:10.5px;
  text-transform:uppercase;letter-spacing:.5px;padding:6px 5px;
  border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}
td{padding:7px 5px;border-bottom:1px solid var(--line)}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
footer{color:var(--dim);font-size:11.5px;margin-top:30px;line-height:1.7;
  border-top:1px solid var(--line);padding-top:14px}
"""


def _f(x, n=2):
    try:
        return f"{float(x):,.{n}f}"
    except (TypeError, ValueError):
        return "-"


def _cls(v):
    return "up" if v > 0 else ("dn" if v < 0 else "dim")


def _when(iso, fmt="%d %b %H:%M"):
    try:
        return dt.datetime.fromisoformat(str(iso)).astimezone(IST).strftime(fmt)
    except Exception:                                # noqa: BLE001
        return "-"


def build(book: dict) -> str:
    closed = book.get("closed", [])
    open_pos = list(book.get("open", {}).values())
    watch = list(book.get("watch", {}).values())

    wins = [t for t in closed if t.get("pct", 0) > 0]
    gp = sum(t["pct"] for t in wins)
    gl = abs(sum(t["pct"] for t in closed if t.get("pct", 0) <= 0))
    total = sum(t.get("pct", 0) for t in closed)
    win_rate = len(wins) / len(closed) * 100 if closed else 0
    avg_r = sum(t.get("r", 0) for t in closed) / len(closed) if closed else 0
    pf = gp / gl if gl > 0 else (float("inf") if gp > 0 else 0)
    open_pnl = sum((p["ltp"] - p["entry"]) / p["entry"] * 100 for p in open_pos)

    started = _when(book.get("started"), "%d %b %Y")
    days = "-"
    try:
        days = (dt.datetime.now(IST)
                - dt.datetime.fromisoformat(str(book["started"])).astimezone(IST)).days
    except Exception:                                # noqa: BLE001
        pass

    p = []
    p.append('<div class="row"><h1>Supertrend Paper Book</h1>'
             f'<span class="tag">{book.get("universe", 0)} stocks</span></div>')
    p.append(f'<div class="sub">Daily + 125-min Supertrend breakout &middot; '
             f'live since {started} ({days} days) &middot; '
             f'last scan {_when(book.get("last_scan"))} IST</div>')

    # ---- KPIs
    p.append('<div class="grid">')
    for label, val, cls in [
        ("Closed", str(len(closed)), ""),
        ("Win rate", f"{win_rate:.0f}%", ""),
        ("Total P&L", f"{total:+.2f}%", _cls(total)),
        ("Avg R", f"{avg_r:+.2f}", _cls(avg_r)),
        ("Profit factor", ("&infin;" if pf == float("inf") else f"{pf:.2f}"), ""),
        ("Open P&L", f"{open_pnl:+.2f}%", _cls(open_pnl)),
    ]:
        p.append(f'<div class="kpi"><div class="v {cls}">{val}</div>'
                 f'<div class="l">{label}</div></div>')
    p.append("</div>")

    # ---- open positions
    p.append(f"<h2>Open positions ({len(open_pos)})</h2>")
    if not open_pos:
        p.append('<div class="empty">No open paper trades.</div>')
    for x in sorted(open_pos, key=lambda z: (z["ltp"] - z["entry"]) / z["entry"],
                    reverse=True):
        pnl = (x["ltp"] - x["entry"]) / x["entry"] * 100
        r = (x["ltp"] - x["entry"]) / x["risk"] if x.get("risk") else 0
        p.append(
            f'<div class="card"><div class="row"><span class="sym">'
            f'{html.escape(x["symbol"])}</span>'
            f'<span class="big {_cls(pnl)}">{pnl:+.2f}%</span></div>'
            f'<div class="meta">Entry {_f(x["entry"])} &middot; LTP {_f(x["ltp"])} '
            f'&middot; SL {_f(x["stop"])} &middot; {r:+.2f} R</div>'
            f'<div class="meta">In since {_when(x["entry_time"])}</div></div>')

    # ---- watchlist
    p.append(f"<h2>Waiting for breakout ({len(watch)})</h2>")
    if not watch:
        p.append('<div class="empty">No pending setups. '
                 'A setup appears when the 125-min Supertrend turns green '
                 'while the daily is already green.</div>')
    for x in sorted(watch, key=lambda z: z["symbol"]):
        away = (x["trigger"] - x["ltp"]) / x["ltp"] * 100
        p.append(
            f'<div class="card"><div class="row"><span class="sym">'
            f'{html.escape(x["symbol"])}</span>'
            f'<span class="big amber">buy &gt; {_f(x["trigger"])}</span></div>'
            f'<div class="meta">LTP {_f(x["ltp"])} ({away:+.2f}% away) &middot; '
            f'SL {_f(x["stop"])} &middot; risk '
            f'{(x["trigger"] - x["stop"]) / x["trigger"] * 100:.2f}%</div>'
            f'<div class="meta">Signal {_when(x["signal_time"])} &middot; '
            f'{max(x["bars_left"], 0)} candle(s) left</div></div>')

    # ---- closed trades
    p.append(f"<h2>Closed trades ({len(closed)})</h2>")
    if not closed:
        p.append('<div class="empty">Nothing closed yet.</div>')
    else:
        p.append('<div class="scroll"><table><tr><th>Stock</th><th>Entry</th>'
                 '<th>Exit</th><th>R</th><th>P&amp;L</th><th>Why</th><th>Closed</th></tr>')
        for t in sorted(closed, key=lambda z: str(z.get("exit_time")), reverse=True):
            pct = t.get("pct", 0)
            p.append(
                f'<tr><td>{html.escape(t["symbol"])}</td><td>{_f(t["entry"])}</td>'
                f'<td>{_f(t["exit"])}</td><td>{t.get("r", 0):+.2f}</td>'
                f'<td class="{_cls(pct)}">{pct:+.2f}%</td>'
                f'<td class="dim">{"target" if t.get("reason") == "ST_FLIP" else "stop"}</td>'
                f'<td class="dim">{_when(t.get("exit_time"), "%d %b")}</td></tr>')
        p.append("</table></div>")

    p.append(
        '<footer>Paper trading only - no real orders, no brokerage or slippage '
        'modelled (budget ~0.1-0.2% per round trip). Prices are delayed Yahoo '
        'Finance data, not a broker feed. Entries assume a fill exactly at the '
        'trigger. Nothing here is investment advice.</footer>')

    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="refresh" content="300">'
            f'<meta name="color-scheme" content="dark">'
            f'<title>Supertrend Paper Book</title><style>{CSS}</style></head>'
            f'<body>{"".join(p)}</body></html>')


def main() -> None:
    book = json.load(open(BOOK_FILE, encoding="utf-8")) if os.path.exists(BOOK_FILE) \
        else {"watch": {}, "open": {}, "closed": []}
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(build(book))
    with open(os.path.join(OUT_DIR, "book.json"), "w", encoding="utf-8") as f:
        json.dump(book, f, indent=2, default=str)
    print(f"wrote {out} ({os.path.getsize(out)} bytes)")


if __name__ == "__main__":
    main()
