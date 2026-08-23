"""Live scanner + paper-trading book for the daily+125min Supertrend breakout.

    python live_alert.py            # poll every 60s during market hours
    python live_alert.py --once     # single pass (GitHub Actions / Task Scheduler)
    python live_alert.py --test     # send one test alert

Every signal is paper-traded into paper_book.json: setups become open positions
on the breakout, and close on the stop-loss or the Supertrend flip, exactly as
backtest.py simulates them. site.py renders that book as a web page.

Telegram alerts (optional): set TELEGRAM_TOKEN and TELEGRAM_CHAT_ID.
"""

import argparse
import datetime as dt
import json
import os
import time

import pandas as pd

from data import fetch_bulk
from st_core import BAR_MINUTES, daily_green_map, supertrend, to_125min
from universe import get_universe

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK_FILE = os.path.join(HERE, "paper_book.json")
LOG_FILE = os.path.join(HERE, "alerts.log")

ATR_PERIOD = int(os.environ.get("ST_ATR", 14))
ATR_MULT = float(os.environ.get("ST_MULT", 2.0))
ENTRY_WINDOW = int(os.environ.get("ST_WINDOW", 3))

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
MKT_OPEN = dt.time(9, 15)
MKT_CLOSE = dt.time(15, 30)


def now_ist() -> dt.datetime:
    return dt.datetime.now(IST)


# ---------------------------------------------------------------- notifying
def notify(title: str, body: str) -> None:
    line = f"[{now_ist():%Y-%m-%d %H:%M:%S}] {title} | {body}"
    print("\a" + line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat:
        try:
            import requests
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": f"{title}\n{body}"},
                          timeout=10)
        except Exception as e:                       # noqa: BLE001
            print(f"  ! telegram failed: {e}")


# ---------------------------------------------------------------- the book
def empty_book() -> dict:
    return {"watch": {}, "open": {}, "closed": [], "started": now_ist().isoformat(),
            "last_scan": None, "universe": 0}


def load_book() -> dict:
    if os.path.exists(BOOK_FILE):
        with open(BOOK_FILE, encoding="utf-8") as f:
            b = json.load(f)
        for k, v in empty_book().items():
            b.setdefault(k, v)
        return b
    return empty_book()


def save_book(book: dict) -> None:
    with open(BOOK_FILE, "w", encoding="utf-8") as f:
        json.dump(book, f, indent=2, default=str)


def market_open_now() -> bool:
    n = now_ist()
    return n.weekday() < 5 and MKT_OPEN <= n.time() <= MKT_CLOSE


# ---------------------------------------------------------------- scan
def scan_symbol(sym: str, five: pd.DataFrame, daily: pd.DataFrame, book: dict) -> None:
    if five.empty or daily.empty or len(five) < 30:
        return

    bars = to_125min(five)
    if len(bars) < ATR_PERIOD + 3:
        return

    name = sym.replace(".NS", "")
    # The newest 125-min bar is still forming unless the session moved past it.
    forming = (now_ist() - bars.index[-1].to_pydatetime()).total_seconds() < BAR_MINUTES * 60
    closed_bars = bars.iloc[:-1] if forming else bars
    if len(closed_bars) < ATR_PERIOD + 3:
        return

    st = supertrend(closed_bars, ATR_PERIOD, ATR_MULT)
    d = st["dir"].to_numpy(int)
    green, last_bar_ts = d[-1] == 1, closed_bars.index[-1]
    ltp = float(five["Close"].iloc[-1])

    # ---- 1. new setup on the most recently completed 125-min bar
    if green and d[-2] == -1:
        dg = daily_green_map(daily, ATR_PERIOD, ATR_MULT)
        if dg.get(last_bar_ts.date(), 0) == 1:
            key = f"{name}|{last_bar_ts.isoformat()}"
            trigger = float(closed_bars["High"].iloc[-1])
            stop = float(closed_bars["Low"].iloc[-1])
            if key not in book["watch"] and key not in book["open"] and stop < trigger:
                book["watch"][key] = {
                    "symbol": name, "signal_time": last_bar_ts.isoformat(),
                    "trigger": trigger, "stop": stop,
                    "bars_left": ENTRY_WINDOW, "last_bar": last_bar_ts.isoformat(),
                    "ltp": ltp,
                }
                notify(f"SETUP  {name}",
                       f"125m Supertrend turned GREEN (daily green too).\n"
                       f"Buy above {trigger:.2f} | SL {stop:.2f} "
                       f"(risk {(trigger - stop) / trigger * 100:.2f}%) | LTP {ltp:.2f}\n"
                       f"Valid for the next {ENTRY_WINDOW} x 125-min candles.")

    # ---- 2. pending setups: has the high broken?
    for key, w in list(book["watch"].items()):
        if w["symbol"] != name:
            continue
        w["ltp"] = ltp

        if last_bar_ts.isoformat() != w["last_bar"]:      # a candle completed
            w["last_bar"] = last_bar_ts.isoformat()
            w["bars_left"] -= 1

        if not green:
            notify(f"CANCEL {name}", "125m Supertrend flipped red before entry.")
            book["watch"].pop(key)
            continue

        # Window opens when the SIGNAL CANDLE CLOSES - starting at signal_time
        # would include that candle's own 5-min bars, whose high IS the trigger.
        wstart = pd.Timestamp(w["signal_time"]) + pd.Timedelta(minutes=BAR_MINUTES)
        after = five[five.index >= wstart]
        run_high = float(after["High"].max()) if not after.empty else 0.0

        if run_high >= w["trigger"]:
            fill = w["trigger"]                          # assume a fill at the trigger
            risk = fill - w["stop"]
            book["open"][key] = {
                "symbol": name, "signal_time": w["signal_time"],
                "entry_time": now_ist().isoformat(), "entry": fill, "stop": w["stop"],
                "ltp": ltp, "risk": risk,
            }
            book["watch"].pop(key)
            pull = "" if ltp >= fill else (
                f"\nNOTE: price has pulled back to {ltp:.2f} - the trigger was "
                f"hit earlier, between scans.")
            notify(f">>> ENTRY {name} <<<",
                   f"Broke {fill:.2f}. LTP {ltp:.2f}\n"
                   f"STOP LOSS {w['stop']:.2f}  (risk {risk / fill * 100:.2f}%)\n"
                   f"Exit when the 125-min Supertrend turns red. "
                   f"1R = {fill + risk:.2f}, 2R = {fill + 2 * risk:.2f}{pull}")
        elif w["bars_left"] < 0:
            notify(f"EXPIRE {name}",
                   f"No breakout of {w['trigger']:.2f} within {ENTRY_WINDOW} candles.")
            book["watch"].pop(key)

    # ---- 3. open positions: stop-loss first, then the Supertrend flip
    for key, p in list(book["open"].items()):
        if p["symbol"] != name:
            continue
        p["ltp"] = ltp

        since = five[five.index >= pd.Timestamp(p["entry_time"])]
        low_since = float(since["Low"].min()) if not since.empty else ltp
        p["mae"] = min(p.get("mae", low_since), low_since)
        p["mfe"] = max(p.get("mfe", ltp), float(since["High"].max()) if not since.empty else ltp)

        exit_px = reason = None
        if low_since <= p["stop"]:
            exit_px, reason = p["stop"], "SL"
        elif not green:
            exit_px, reason = float(closed_bars["Close"].iloc[-1]), "ST_FLIP"
        if exit_px is None:
            continue

        pct = (exit_px - p["entry"]) / p["entry"] * 100
        book["closed"].append({**p, "exit_time": now_ist().isoformat(),
                               "exit": exit_px, "reason": reason,
                               "pct": pct, "r": (exit_px - p["entry"]) / p["risk"]})
        book["open"].pop(key)
        verdict = "TARGET" if reason == "ST_FLIP" else "STOPPED OUT"
        notify(f"EXIT   {name} ({verdict})",
               f"{'125m Supertrend turned RED' if reason == 'ST_FLIP' else 'Stop-loss hit'}"
               f" - book out near {exit_px:.2f}\n"
               f"Entry {p['entry']:.2f} -> {exit_px:.2f} = {pct:+.2f}% "
               f"({(exit_px - p['entry']) / p['risk']:+.2f} R)")


def scan_all() -> dict:
    book = load_book()
    syms = get_universe()
    print(f"--- scan {now_ist():%Y-%m-%d %H:%M:%S} | {len(syms)} stocks | "
          f"ATR {ATR_PERIOD}, mult {ATR_MULT}, window {ENTRY_WINDOW} ---")

    five_all = fetch_bulk(syms, "5m", "20d")
    daily_all = fetch_bulk(syms, "1d", "6mo")
    if not five_all:
        print("  ! no intraday data returned - skipping this pass")
        return book

    for sym in syms:
        try:
            scan_symbol(sym, five_all.get(sym, pd.DataFrame()),
                        daily_all.get(sym, pd.DataFrame()), book)
        except Exception as e:                       # noqa: BLE001 - never kill the loop
            print(f"  ! {sym}: {e}")

    book["last_scan"] = now_ist().isoformat()
    book["universe"] = len(five_all)
    save_book(book)
    print(f"    watching {len(book['watch'])} | open {len(book['open'])} | "
          f"closed {len(book['closed'])}")
    return book


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--force", action="store_true", help="scan even when market is shut")
    ap.add_argument("--test", action="store_true", help="send one test alert")
    args = ap.parse_args()

    if args.test:
        ok = bool(os.environ.get("TELEGRAM_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))
        notify("TEST", "Supertrend scanner is alive. If this reached your phone, "
                       "alerts are working.")
        print("Telegram configured." if ok else
              "Telegram NOT configured - set TELEGRAM_TOKEN and TELEGRAM_CHAT_ID.")
        return

    if args.once:
        scan_all()
        return

    print("Live scanner started. Ctrl+C to stop.")
    while True:
        if market_open_now() or args.force:
            scan_all()
        else:
            print(f"{now_ist():%H:%M:%S} market closed - idling")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
