"""Stock universe, pulled live from NSE's own index constituent files.

Default is NIFTY 500. That is not the whole exchange (~2000 listings) by choice:
below the 500 the 5-minute data is patchy and the stocks are too illiquid to
enter on a breakout without heavy slippage, so signals there would not be
tradeable. Override with the UNIVERSE env var: nifty50 | nifty200 | nifty500.
"""

import io
import os

import pandas as pd
import requests

INDEX_CSV = {
    "nifty50": "ind_nifty50list.csv",
    "nifty100": "ind_nifty100list.csv",
    "nifty200": "ind_nifty200list.csv",
    "nifty500": "ind_nifty500list.csv",
}
BASE = "https://nsearchives.nseindia.com/content/indices/"

# Yahoo renamed a few tickers after corporate actions.
YF_OVERRIDE = {"TATAMOTORS": "TMPV"}

FALLBACK = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BHARTIARTL",
    "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "ETERNAL",
    "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO",
    "HINDALCO", "HINDUNILVR", "ICICIBANK", "INDUSINDBK", "INFY",
    "ITC", "JIOFIN", "JSWSTEEL", "KOTAKBANK", "LT",
    "M&M", "MARUTI", "NESTLEIND", "NTPC", "ONGC",
    "POWERGRID", "RELIANCE", "SBILIFE", "SBIN", "SHRIRAMFIN",
    "SUNPHARMA", "TATACONSUM", "TMPV", "TATASTEEL", "TCS",
    "TECHM", "TITAN", "TRENT", "ULTRACEMCO", "WIPRO",
]


def get_universe(name: str | None = None) -> list[str]:
    """Yahoo tickers for the requested index, falling back to a bundled list."""
    name = (name or os.environ.get("UNIVERSE", "nifty500")).lower()
    csv = INDEX_CSV.get(name)
    if csv:
        try:
            r = requests.get(BASE + csv, headers={"User-Agent": "Mozilla/5.0"},
                             timeout=30)
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.text))
            syms = [str(s).strip() for s in df["Symbol"] if str(s).strip()]
            if len(syms) >= 40:
                return [YF_OVERRIDE.get(s, s) + ".NS" for s in syms]
        except Exception as e:                       # noqa: BLE001
            print(f"  ! NSE list fetch failed ({e}); using bundled fallback")
    return [s + ".NS" for s in FALLBACK]
