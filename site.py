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
  --bg:#0e1117;
  --card:#171b23;
  --line:#262c38;
  --tx:#e6e9ef;
  --dim:#8b94a7;
  --up:#26a96c;
  --dn:#e5484d;
  --amber:#e8a33d;
  --accent:#4c8dff;
}

body{
  background:var(--bg);
  color:var(--tx);
  font:15px/1.5 -apple-system,BlinkMacSystemFont,
  "Segoe UI",Roboto,sans-serif;
  padding:14px;
  max-width:900px;
  margin:0 auto;
  -webkit-text-size-adjust:100%
}

h1{
  font-size:19px;
  letter-spacing:-.2px
}

h2{
  font-size:14px;
  text-transform:uppercase;
  letter-spacing:.8px;
  color:var(--dim);
  margin:26px 0 10px
}

.sub{
  color:var(--dim);
  font-size:12.5px;
  margin-top:4px
}

/* Header */

.header{
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:12px;
  margin-bottom:4px
}

.header-title{
  min-width:0
}

.refresh-btn{
  background:var(--accent);
  color:white;
  border:0;
  border-radius:8px;
  padding:9px 14px;
  font-size:13px;
  font-weight:600;
  cursor:pointer;
  white-space:nowrap;
  transition:opacity .15s,transform .05s
}

.refresh-btn:hover{
  opacity:.88
}

.refresh-btn:active{
  transform:scale(.97)
}

/* KPI */

.grid{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(94px,1fr));
  gap:8px;
  margin-top:14px
}

.kpi{
  background:var(--card);
  border:1px solid var(--line);
  border-radius:10px;
  padding:10px
}

.kpi .v{
  font-size:19px;
  font-weight:650;
  letter-spacing:-.3px
}

.kpi .l{
  font-size:10.5px;
  color:var(--dim);
  text-transform:uppercase;
  letter-spacing:.5px;
  margin-top:3px
}

/* Cards */

.card{
  background:var(--card);
  border:1px solid var(--line);
  border-radius:10px;
  padding:11px 12px;
  margin-bottom:8px
}

.row{
  display:flex;
  justify-content:space-between;
  align-items:baseline;
  gap:8px
}

.sym{
  font-weight:650;
  font-size:15.5px
}

.big{
  font-size:15.5px;
  font-weight:650;
  font-variant-numeric:tabular-nums
}

.meta{
  color:var(--dim);
  font-size:12px;
  margin-top:5px;
  font-variant-numeric:tabular-nums
}

.up{
  color:var(--up)
}

.dn{
  color:var(--dn)
}

.amber{
  color:var(--amber)
}

.dim{
  color:var(--dim)
}

.tag{
  font-size:10px;
  padding:2px 6px;
  border-radius:5px;
  border:1px solid var(--line);
  color:var(--dim);
  text-transform:uppercase;
  letter-spacing:.5px
}

.empty{
  color:var(--dim);
  font-size:13.5px;
  padding:14px;
  text-align:center;
  border:1px dashed var(--line);
  border-radius:10px
}

/* Table */

table{
  width:100%;
  border-collapse:collapse;
  font-size:13px;
  font-variant-numeric:tabular-nums
}

th{
  text-align:right;
  color:var(--dim);
  font-weight:500;
  font-size:10.5px;
  text-transform:uppercase;
  letter-spacing:.5px;
  padding:6px 5px;
  border-bottom:1px solid var(--line)
}

th:first-child,
td:first-child{
  text-align:left
}

td{
  padding:7px 5px;
  border-bottom:1px solid var(--line)
}

.scroll{
  overflow-x:auto;
  -webkit-overflow-scrolling:touch
}

/* Footer */

footer{
  color:var(--dim);
  font-size:11.5px;
  margin-top:30px;
  line-height:1.7;
  border-top:1px solid var(--line);
  padding-top:14px
}

/* Mobile */

@media(max-width:500px){

  body{
    padding:10px
  }

  .header{
    align-items:flex-start
  }

  h1{
    font-size:18px
  }

  .refresh-btn{
    padding:8px 11px;
    font-size:12px
  }

  .grid{
    grid-template-columns:repeat(2,1fr)
  }

  .card{
    padding:10px
  }
}
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
        return (
            dt.datetime
            .fromisoformat(str(iso))
            .astimezone(IST)
            .strftime(fmt)
        )
    except Exception:  # noqa: BLE001
        return "-"


def build(book: dict) -> str:

    closed = book.get("closed", [])
    open_pos = list(book.get("open", {}).values())
    watch = list(book.get("watch", {}).values())

    # ------------------------------------------------------------------
    # Performance calculations
    # ------------------------------------------------------------------

    wins = [t for t in closed if t.get("pct", 0) > 0]

    gp = sum(t.get("pct", 0) for t in wins)

    gl = abs(
        sum(
            t.get("pct", 0)
            for t in closed
            if t.get("pct", 0) <= 0
        )
    )

    total = sum(t.get("pct", 0) for t in closed)

    win_rate = (
        len(wins) / len(closed) * 100
        if closed
        else 0
    )

    avg_r = (
        sum(t.get("r", 0) for t in closed) / len(closed)
        if closed
        else 0
    )

    pf = (
        gp / gl
        if gl > 0
        else (float("inf") if gp > 0 else 0)
    )

    open_pnl = sum(
        (
            (p.get("ltp", p.get("entry", 0)) - p.get("entry", 0))
            / p.get("entry", 1)
            * 100
        )
        for p in open_pos
        if p.get("entry")
    )

    # ------------------------------------------------------------------
    # Scanner age
    # ------------------------------------------------------------------

    started = _when(
        book.get("started"),
        "%d %b %Y"
    )

    days = "-"

    try:
        days = (
            dt.datetime.now(IST)
            - dt.datetime.fromisoformat(
                str(book["started"])
            ).astimezone(IST)
        ).days
    except Exception:  # noqa: BLE001
        pass

    # ------------------------------------------------------------------
    # Page content
    # ------------------------------------------------------------------

    p = []

    # ------------------------------------------------------------------
    # Header + Refresh button
    # ------------------------------------------------------------------

    p.append(
        '<div class="header">'
        '<div class="header-title">'
        '<h1>Supertrend Paper Book</h1>'
        f'<div class="sub">'
        f'{book.get("universe", 0)} stocks'
        f'</div>'
        '</div>'
        '<button class="refresh-btn" '
        'onclick="location.reload()">'
        '🔄 Refresh'
        '</button>'
        '</div>'
    )

    # ------------------------------------------------------------------
    # Scanner information
    # ------------------------------------------------------------------

    p.append(
        f'<div class="sub">'
        f'Daily + 125-min Supertrend breakout '
        f'&middot; live since {started} ({days} days) '
        f'&middot; last scan {_when(book.get("last_scan"))} IST'
        f'</div>'
    )

    # ------------------------------------------------------------------
    # KPIs
    # ------------------------------------------------------------------

    p.append('<div class="grid">')

    for label, val, cls in [
        ("Closed", str(len(closed)), ""),
        ("Win rate", f"{win_rate:.0f}%", ""),
        ("Total P&L", f"{total:+.2f}%", _cls(total)),
        ("Avg R", f"{avg_r:+.2f}", _cls(avg_r)),
        (
            "Profit factor",
            (
                "&infin;"
                if pf == float("inf")
                else f"{pf:.2f}"
            ),
            "",
        ),
        (
            "Open P&L",
            f"{open_pnl:+.2f}%",
            _cls(open_pnl),
        ),
    ]:

        p.append(
            f'<div class="kpi">'
            f'<div class="v {cls}">{val}</div>'
            f'<div class="l">{label}</div>'
            f'</div>'
        )

    p.append("</div>")

    # ------------------------------------------------------------------
    # Open positions
    # ------------------------------------------------------------------

    p.append(
        f"<h2>Open positions ({len(open_pos)})</h2>"
    )

    if not open_pos:
        p.append(
            '<div class="empty">'
            'No open paper trades.'
            '</div>'
        )

    for x in sorted(
        open_pos,
        key=lambda z: (
            z.get("ltp", z.get("entry", 0))
            - z.get("entry", 0)
        ) / z.get("entry", 1)
        if z.get("entry")
        else 0,
        reverse=True,
    ):

        entry = x.get("entry", 0)
        ltp = x.get("ltp", entry)
        stop = x.get("stop", 0)

        pnl = (
            (ltp - entry) / entry * 100
            if entry
            else 0
        )

        r = (
            (ltp - entry) / x["risk"]
            if x.get("risk")
            else 0
        )

        p.append(
            f'<div class="card">'
            f'<div class="row">'
            f'<span class="sym">'
            f'{html.escape(str(x.get("symbol", "-")))}'
            f'</span>'
            f'<span class="big {_cls(pnl)}">'
            f'{pnl:+.2f}%'
            f'</span>'
            f'</div>'

            f'<div class="meta">'
            f'Entry {_f(entry)} '
            f'&middot; LTP {_f(ltp)} '
            f'&middot; SL {_f(stop)} '
            f'&middot; {r:+.2f} R'
            f'</div>'

            f'<div class="meta">'
            f'In since {_when(x.get("entry_time"))}'
            f'</div>'

            f'</div>'
        )

    # ------------------------------------------------------------------
    # Watchlist
    # ------------------------------------------------------------------

    p.append(
        f"<h2>Waiting for breakout ({len(watch)})</h2>"
    )

    if not watch:

        p.append(
            '<div class="empty">'
            'No pending setups. '
            'A setup appears when the 125-min Supertrend '
            'turns green while the daily is already green.'
            '</div>'
        )

    for x in sorted(
        watch,
        key=lambda z: z.get("symbol", "")
    ):

        trigger = x.get("trigger", 0)
        ltp = x.get("ltp", 0)
        stop = x.get("stop", 0)

        away = (
            (trigger - ltp) / ltp * 100
            if ltp
            else 0
        )

        risk_pct = (
            (trigger - stop) / trigger * 100
            if trigger
            else 0
        )

        p.append(
            f'<div class="card">'
            f'<div class="row">'
            f'<span class="sym">'
            f'{html.escape(str(x.get("symbol", "-")))}'
            f'</span>'
            f'<span class="big amber">'
            f'buy &gt; {_f(trigger)}'
            f'</span>'
            f'</div>'

            f'<div class="meta">'
            f'LTP {_f(ltp)} '
            f'({away:+.2f}% away) '
            f'&middot; SL {_f(stop)} '
            f'&middot; risk {risk_pct:.2f}%'
            f'</div>'

            f'<div class="meta">'
            f'Signal {_when(x.get("signal_time"))} '
            f'&middot; '
            f'{max(x.get("bars_left", 0), 0)} candle(s) left'
            f'</div>'

            f'</div>'
        )

    # ------------------------------------------------------------------
    # Closed trades
    # ------------------------------------------------------------------

    p.append(
        f"<h2>Closed trades ({len(closed)})</h2>"
    )

    if not closed:

        p.append(
            '<div class="empty">'
            'Nothing closed yet.'
            '</div>'
        )

    else:

        p.append(
            '<div class="scroll">'
            '<table>'
            '<tr>'
            '<th>Stock</th>'
            '<th>Entry</th>'
            '<th>Exit</th>'
            '<th>R</th>'
            '<th>P&amp;L</th>'
            '<th>Why</th>'
            '<th>Closed</th>'
            '</tr>'
        )

        for t in sorted(
            closed,
            key=lambda z: str(z.get("exit_time")),
            reverse=True,
        ):

            pct = t.get("pct", 0)

            reason = (
                "target"
                if t.get("reason") == "ST_FLIP"
                else "stop"
            )

            p.append(
                f'<tr>'
                f'<td>{html.escape(str(t.get("symbol", "-")))}</td>'
                f'<td>{_f(t.get("entry"))}</td>'
                f'<td>{_f(t.get("exit"))}</td>'
                f'<td>{t.get("r", 0):+.2f}</td>'
                f'<td class="{_cls(pct)}">'
                f'{pct:+.2f}%'
                f'</td>'
                f'<td class="dim">{reason}</td>'
                f'<td class="dim">'
                f'{_when(t.get("exit_time"), "%d %b")}'
                f'</td>'
                f'</tr>'
            )

        p.append(
            '</table>'
            '</div>'
        )

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------

    p.append(
        '<footer>'
        'Paper trading only - no real orders, no brokerage or slippage '
        'modelled (budget ~0.1-0.2% per round trip). Prices are delayed '
        'Yahoo Finance data, not a broker feed. Entries assume a fill '
        'exactly at the trigger. Nothing here is investment advice.'
        '</footer>'
    )

    # ------------------------------------------------------------------
    # Complete HTML
    # ------------------------------------------------------------------

    return (
        '<!doctype html>'
        '<html lang="en">'
        '<head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<meta http-equiv="refresh" content="300">'
        '<meta name="color-scheme" content="dark">'
        '<title>Supertrend Paper Book</title>'
        f'<style>{CSS}</style>'
        '</head>'
        '<body>'
        f'{"".join(p)}'
        '</body>'
        '</html>'
    )


def main() -> None:

    # ------------------------------------------------------------------
    # Load paper book
    # ------------------------------------------------------------------

    if os.path.exists(BOOK_FILE):

        with open(
            BOOK_FILE,
            encoding="utf-8"
        ) as f:

            book = json.load(f)

    else:

        book = {
            "watch": {},
            "open": {},
            "closed": [],
        }

    # ------------------------------------------------------------------
    # Create docs directory
    # ------------------------------------------------------------------

    os.makedirs(
        OUT_DIR,
        exist_ok=True
    )

    # ------------------------------------------------------------------
    # Generate index.html
    # ------------------------------------------------------------------

    out = os.path.join(
        OUT_DIR,
        "index.html"
    )

    with open(
        out,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            build(book)
        )

    # ------------------------------------------------------------------
    # Copy book.json to docs
    # ------------------------------------------------------------------

    with open(
        os.path.join(OUT_DIR, "book.json"),
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            book,
            f,
            indent=2,
            default=str
        )

    # ------------------------------------------------------------------
    # Done
    # ------------------------------------------------------------------

    print(
        f"wrote {out} "
        f"({os.path.getsize(out)} bytes)"
    )


if __name__ == "__main__":
    main()
