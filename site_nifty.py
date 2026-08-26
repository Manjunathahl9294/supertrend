"""Render paper_nifty_book.json -> docs/nifty.html (phone-friendly)."""

import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK = os.path.join(HERE, "paper_nifty_book.json")
OUT = os.path.join(HERE, "docs", "nifty.html")

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0e1117;--card:#171b23;--line:#262c38;--tx:#e6e9ef;--dim:#8b94a7;
 --up:#26a96c;--dn:#e5484d;--accent:#4c8dff}
body{background:var(--bg);color:var(--tx);font:15px/1.5 -apple-system,BlinkMacSystemFont,
 "Segoe UI",Roboto,sans-serif;padding:14px;max-width:900px;margin:0 auto;
 -webkit-text-size-adjust:100%}
h1{font-size:19px;letter-spacing:-.2px}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.8px;color:var(--dim);margin:24px 0 9px}
.sub{color:var(--dim);font-size:12.5px;margin-top:4px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:8px;margin-top:14px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px}
.kpi .v{font-size:19px;font-weight:650;letter-spacing:-.3px;font-variant-numeric:tabular-nums}
.kpi .l{font-size:10.5px;color:var(--dim);text-transform:uppercase;letter-spacing:.5px;margin-top:3px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:11px 12px;margin-bottom:8px}
.row{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.sym{font-weight:650;font-size:15px}
.meta{color:var(--dim);font-size:12px;margin-top:5px;font-variant-numeric:tabular-nums}
.up{color:var(--up)}.dn{color:var(--dn)}.dim{color:var(--dim)}
.tag{font-size:10px;padding:2px 6px;border-radius:5px;border:1px solid var(--line);
 color:var(--dim);text-transform:uppercase;letter-spacing:.5px}
.empty{color:var(--dim);font-size:13.5px;padding:14px;text-align:center;
 border:1px dashed var(--line);border-radius:10px}
.wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{width:100%;border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums;
 white-space:nowrap}
th{text-align:right;color:var(--dim);font-weight:500;font-size:10.5px;text-transform:uppercase;
 letter-spacing:.5px;padding:6px 5px;border-bottom:1px solid var(--line)}
td{text-align:right;padding:6px 5px;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}
.note{color:var(--dim);font-size:11.5px;margin-top:18px;line-height:1.6;
 border-top:1px solid var(--line);padding-top:12px}
"""


def rs(v):
    v = int(v)
    cls = "up" if v > 0 else ("dn" if v < 0 else "dim")
    return f'<span class="{cls}">{v:+,}</span>'


def esc(x):
    return html.escape(str(x))


def render(b):
    t = b["totals"]
    kpis = [
        (f'{b["spot"]:,.2f}', "Nifty spot"),
        (str(t["closed"]), "Closed"),
        (str(t["open"]), "Open"),
        (f'{t["best_rs"]:+,}', "Best struct ₹"),
    ]
    k = "".join(f'<div class="kpi"><div class="v">{v}</div><div class="l">{l}</div></div>'
                for v, l in kpis)

    # ---- open positions
    if b["open_positions"]:
        op = "".join(
            f'<div class="card"><div class="row"><span class="sym">{esc(p["structure"])}</span>'
            f'<span class="tag">{esc(p["side"])}</span></div>'
            f'<div class="meta">entry {p["entry_time"][:16]} &middot; spot {p["spot_entry"]} '
            f'&middot; SL {p["spot_stop"]} &middot; {p["strike"]} CE/PE '
            f'&middot; exp {p["expiry"][:10]}</div>'
            f'<div class="meta">running {rs(p["pnl_rs"])}</div></div>'
            for p in b["open_positions"])
    else:
        op = '<div class="empty">No open position &mdash; waiting for the next flip.</div>'

    # ---- structure summary
    if b["summary"]:
        head = ("<tr><th>Structure</th><th>N</th><th>Win%</th><th>Net ₹</th>"
                "<th>Avg ₹</th><th>PF</th><th>MaxDD ₹</th></tr>")
        body = "".join(
            f'<tr><td>{esc(s["structure"])}</td><td>{s["trades"]}</td>'
            f'<td>{s["win_rate_%"]}</td><td>{rs(s["total_pnl_rs"])}</td>'
            f'<td>{rs(s["avg_pnl_rs"])}</td><td>{s["profit_factor"]}</td>'
            f'<td class="dn">{int(s["max_dd_rs"]):,}</td></tr>'
            for s in b["summary"])
        summ = f'<div class="wrap"><table>{head}{body}</table></div>'
    else:
        summ = '<div class="empty">No closed trades yet.</div>'

    # ---- recent closed signals (one row per signal, not per leg)
    seen, rows = set(), []
    for c in sorted(b["closed_trades"], key=lambda x: x["exit_time"], reverse=True):
        if c["entry_time"] in seen:
            continue
        seen.add(c["entry_time"])
        pts = c["points"]
        cls = "up" if pts > 0 else "dn"
        rows.append(
            f'<tr><td>{c["entry_time"][5:16]}</td><td>{esc(c["side"])}</td>'
            f'<td>{c["spot_entry"]}</td><td>{c["spot_exit"]}</td>'
            f'<td class="{cls}">{pts:+.1f}</td><td>{c["r"]}</td>'
            f'<td>{esc(c["reason"])}</td></tr>')
        if len(rows) >= 30:
            break
    trades = ('<div class="wrap"><table><tr><th>Entry</th><th>Side</th><th>In</th>'
              '<th>Out</th><th>Pts</th><th>R</th><th>Exit</th></tr>'
              + "".join(rows) + "</table></div>") if rows else \
             '<div class="empty">No closed signals yet.</div>'

    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0e1117">
<title>Nifty Option Paper Book</title>
<style>{CSS}</style></head><body>
<h1>Nifty 50 &middot; 15-min Supertrend Flip</h1>
<div class="sub">Option paper book &middot; updated {esc(b["generated"][:16])} IST
&middot; last bar {esc(b["last_bar"][:16])} &middot; lot {b["lot"]}</div>
<div class="grid">{k}</div>
<h2>Open positions</h2>{op}
<h2>Structure performance</h2>{summ}
<h2>Recent signals</h2>{trades}
<div class="note">
Paper trading only &mdash; no orders are placed anywhere.
Option premiums are <b>Black&ndash;Scholes model prices</b> computed off the real index
path with IV estimated from realised volatility; yfinance carries no historical
NIFTY option chain, so absolute premiums are estimates while direction and payoff
shape are faithful. Costs modelled at 1% of premium per side.
Positions carried through Thursday expiry are settled and re-struck ATM.
</div></body></html>"""


if __name__ == "__main__":
    b = json.load(open(BOOK))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(render(b))
    print(f"wrote {OUT}")
