# Daily + 125-min Supertrend breakout — Nifty 50

## The strategy

| | |
|---|---|
| **Filter** | Daily Supertrend is GREEN (uses the *previous* completed daily candle — no lookahead) |
| **Signal** | 125-min Supertrend flips RED → GREEN |
| **Entry** | Break above the signal candle's HIGH, within the next 3 × 125-min candles |
| **Stop** | The signal candle's LOW |
| **Target** | Exit when the 125-min Supertrend flips back to RED |

125-min bars are built from 5-min data, anchored at 09:15 — exactly 3 bars per NSE
session (09:15, 11:20, 13:25).

## Files

- `st_core.py` — Supertrend, 125-min resampling, trade simulation
- `data.py` — Nifty 50 list + cached yfinance downloads (`cache/`)
- `backtest.py` — parameter sweep over the universe → `results/`
- `live_alert.py` — live scanner that alerts on setups, entries and exits

## Run

```bash
python backtest.py
```

```bash
python live_alert.py
```

`--once` for a single pass (Task Scheduler), `--interval 300` to slow the polling,
`--force` to scan outside market hours.

Telegram alerts are optional — set `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` and the
scanner pushes to your phone. Otherwise alerts go to the console and `alerts.log`.

Override params without editing code:

```bash
ST_ATR=7 ST_MULT=1.5 ST_WINDOW=1 python live_alert.py
```

## Backtest result (49 stocks, 01-Jun-2026 → 21-Aug-2026)

Best by expectancy, of 27 parameter combinations:

| ATR | Mult | Window | Trades | Win % | Expectancy | Profit factor |
|---|---|---|---|---|---|---|
| 14 | 2.0 | 1 | 39 | 35.9 | +0.45 R | 1.92 |
| 14 | 2.0 | 3 | 55 | 36.4 | +0.39 R | 1.93 |
| 7 | 1.5 | 1 | 51 | 47.1 | +0.36 R | 1.78 |
| 10 | 3.0 | 3 | 19 | 26.3 | −0.38 R | 0.92 |

The shape is consistent: low win rate, large winners (avg +4%) against small,
tightly-capped losers (avg −1.2%). Mult 3.0 is too slow for a 125-min chart — it
gives too few signals and the stop sits too far away. `live_alert.py` defaults to
ATR 14 / mult 2.0 / window 3.

Full output: `results/sweep.csv`, `results/trades_best.csv`, `results/per_stock_best.csv`.

## Running it from your phone (GitHub Actions + Telegram)

Your laptop stays shut. A free GitHub Actions cron runs the scan; alerts arrive as
Telegram push notifications.

### 1. Telegram bot (5 minutes, one time)

1. Message **@BotFather** on Telegram -> `/newbot` -> pick a name. Copy the token.
2. Message your new bot anything (a bot cannot message you first).
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `chat.id`.

Verify locally:

```bash
python live_alert.py --test
```

### 2. Push the repo to GitHub

A **private** repo is fine - Actions minutes are free for public repos and
generous for private ones.

### 3. Add the secrets

Repo -> Settings -> Secrets and variables -> Actions -> New repository secret:

| Name | Value |
|---|---|
| `TELEGRAM_TOKEN` | the BotFather token |
| `TELEGRAM_CHAT_ID` | your chat id |

### 4. Turn on the web page

Repo -> Settings -> Pages -> Source: **Deploy from a branch**, Branch: **main**,
Folder: **/docs** -> Save. After the next scan your page is live at:

```
https://<your-github-username>.github.io/<repo-name>/
```

Bookmark that on your phone's home screen. It self-refreshes every 5 minutes and
shows:

- **KPIs** - closed trades, win rate, total P&L, average R, profit factor, open P&L
- **Open positions** - live P&L and R on every paper trade currently running
- **Waiting for breakout** - stocks that signalled, with the buy-above and SL levels
- **Closed trades** - the full history, newest first, with why each one exited

### 5. Done

[.github/workflows/scan.yml](.github/workflows/scan.yml) then runs every 5 minutes,
09:15-15:30 IST, Mon-Fri. Each run:

- pulls the whole universe in **2 bulk requests** (~14 s, no rate-limit risk)
- alerts on SETUP / ENTRY / EXIT / CANCEL / EXPIRE
- commits `live_state.json` back to the repo, so pending setups survive between runs

You can also trigger a scan by hand from the phone: repo -> Actions ->
*Supertrend scan* -> **Run workflow**.

### Latency caveat

GitHub's cron is best-effort and often fires 5-15 minutes late. This is handled,
not ignored: the entry check compares the trigger against the **running high of
every 5-min bar since the signal candle closed**, not just the latest price. A
breakout that spikes and pulls back between two runs still alerts, and the message
tells you the trigger was hit earlier so you can decide whether the fill is still
valid. If you need tick-accurate entries, move to an always-on host and a broker
websocket feed.

## Paper trading

Every signal is paper-traded automatically into `paper_book.json` using exactly
the backtest's rules: a setup becomes an open position when the high breaks,
and closes on the stop-loss or the Supertrend flip, whichever comes first.
Nothing is ever ordered - there is no broker connection in this project.

To review after a month, just open the page: the KPI row is the answer. Compare
it against the backtest's +0.45 R expectancy / 1.92 profit factor. Expect the
live numbers to come in **worse**, because the backtest has no costs and assumes
perfect fills at the trigger.

Reset the book and start a fresh month:

```bash
rm paper_book.json && python site.py
```

## Universe

Defaults to **NIFTY 500**, pulled live from NSE's own constituent file, so it
tracks index changes on its own. A full scan of 500 stocks takes ~1m45s.

Not the entire ~2000-stock exchange, deliberately: below the 500 the 5-minute
data is patchy and the stocks are too illiquid to enter on a breakout without
heavy slippage, so those signals would not be tradeable. Override if you disagree:

```bash
UNIVERSE=nifty200 python live_alert.py --once
```

## Limitations you should know about

1. **Only ~60 days of history.** Yahoo caps 5-min intraday data at 60 days, so the
   125-min backtest covers Jun–Aug 2026 — 177 bars per stock. 39–55 trades is a
   thin sample; the top of that sweep table is partly luck. Treat it as a sanity
   check, not proof of edge. For a multi-year test you need a broker feed
   (Zerodha Kite, Dhan, Fyers) — swap `data.fetch()` and everything else works.
2. **No costs modelled.** Brokerage, STT and slippage will eat roughly 0.1–0.2%
   per round trip, which is meaningful against a +0.7% average trade.
3. **Yahoo is not a trading feed.** It lags and occasionally drops bars. Fine for
   a heads-up alert; do not automate orders off it.
4. Long-only, one position at a time per stock, no position sizing.
