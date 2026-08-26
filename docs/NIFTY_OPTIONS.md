# Nifty 50 · 15-min Supertrend Flip · Option Paper Trading

## Strategy

Supertrend(10, 3) on 15-minute NIFTY 50 index candles.

**Long setup** — Supertrend flips red → green.
- Entry: break of the *flip candle's high*, within the next 3 candles
- Stop: flip candle's low
- Target: Supertrend flips back to red (exit at that candle's close)

**Short setup** — mirror image. Flip green → red, entry on break of the flip
candle's low, stop at its high, exit when Supertrend flips back to green.

If the setup invalidates (Supertrend flips back) before the trigger is hit, the
signal is dropped. One position at a time.

### Option structures

| Signal | Structures traded |
|---|---|
| LONG  | naked call buy · naked put sell · bull call spread · bull put spread |
| SHORT | naked put buy · naked call sell · bear call spread · bear put spread |

ATM strike (50-pt grid), nearest weekly expiry, lot 75, spreads 200 points wide.
All eight are tracked in parallel so they can be compared on identical signals —
they are not meant to be traded together.

## How premiums are modelled

**yfinance carries no historical NIFTY option chain.** Every premium here is a
Black–Scholes *model* price computed off the real index path, with IV estimated
from 20-day realised volatility × 1.15 (variance risk premium), clipped to
9–35%. Costs: 1% of premium per side. Positions carried through Thursday 15:30
expiry are settled at intrinsic and re-struck ATM in the next series.

Direction and payoff shape are faithful. Absolute premium of any single leg is
an estimate, not a fill.

## Files

| File | Purpose |
|---|---|
| `nifty_opt/signals.py` | 15-min Supertrend flip signal engine |
| `nifty_opt/options.py` | Black–Scholes overlay, expiry rolls, structures |
| `backtest_nifty_opt.py` | Backtest → `results/nifty_opt/` |
| `sweep_nifty_opt.py` | Parameter robustness sweep |
| `paper_nifty_opt.py` | Live paper book → `paper_nifty_book.json` |
| `site_nifty.py` | Renders the book → `docs/nifty.html` |

## Running it

```bash
pip install -r requirements.txt
python backtest_nifty_opt.py     # backtest + summary
python sweep_nifty_opt.py        # robustness across parameters
python paper_nifty_opt.py && python site_nifty.py   # update the paper book
```

## Phone access

`.github/workflows/nifty-paper.yml` runs every 15 minutes during market hours
(09:15–15:50 IST, Mon–Fri), recomputes the book and commits `docs/nifty.html`.

To read it on your phone:
1. Repo → **Settings → Pages** → Source: *Deploy from a branch*, branch `main`,
   folder `/docs`.
2. Open `https://<your-user>.github.io/<repo>/nifty.html` and add it to your home
   screen.
3. Optional: set a repo variable `PAPER_START` (Settings → Secrets and variables
   → Actions → Variables) to an ISO date, e.g. `2026-08-27`, so the book counts
   only trades from the day you start the one-month run.

The trader is stateless — it recomputes the full history from the 15-min feed on
every run, so a missed cron tick is harmless.

## Data limit

yfinance serves at most **60 days** of 15-minute history. The backtest window is
therefore always the trailing ~59 trading days and slides forward over time.
