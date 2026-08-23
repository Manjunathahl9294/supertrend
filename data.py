"""Nifty 50 universe + cached yfinance downloads."""

import os
import time

import pandas as pd
import yfinance as yf

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
os.makedirs(CACHE, exist_ok=True)

NIFTY50 = [
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

YF = [s + ".NS" for s in NIFTY50]


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()


def fetch(symbol: str, interval: str, period: str, max_age_h: float = 6.0) -> pd.DataFrame:
    """Download OHLCV with an on-disk parquet cache."""
    path = os.path.join(CACHE, f"{symbol}_{interval}_{period}.parquet")
    if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < max_age_h * 3600:
        return pd.read_parquet(path)

    for attempt in range(3):
        try:
            df = yf.download(symbol, period=period, interval=interval,
                             auto_adjust=False, progress=False, threads=False)
            if df is not None and not df.empty:
                df = _flatten(df)
                df.to_parquet(path)
                return df
        except Exception as e:                       # noqa: BLE001 - network flakiness
            print(f"  ! {symbol} {interval} attempt {attempt + 1}: {e}")
        time.sleep(2 * (attempt + 1))

    if os.path.exists(path):                          # stale cache beats nothing
        return pd.read_parquet(path)
    return pd.DataFrame()


def load_stock(symbol: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (5-min bars, daily bars)."""
    return fetch(symbol, "5m", "60d"), fetch(symbol, "1d", "3y")

# Note: Tata Motors trades as TMPV.NS on Yahoo after the CV/PV demerger;
# "TATAMOTORS.NS" no longer returns data.


def fetch_bulk(symbols: list[str], interval: str, period: str) -> dict[str, pd.DataFrame]:
    """Download many tickers in ONE request.

    The live scanner runs on a cold CI runner with no cache, so per-symbol
    downloads would mean ~100 requests and a rate-limit ban. This is 1 request.
    """
    df = yf.download(symbols, period=period, interval=interval, auto_adjust=False,
                     progress=False, threads=True, group_by="ticker")
    if df is None or df.empty:
        return {}

    out: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            sub = df[sym] if isinstance(df.columns, pd.MultiIndex) else df
        except KeyError:
            continue
        sub = sub[["Open", "High", "Low", "Close", "Volume"]].dropna()
        if not sub.empty:
            out[sym] = sub
    return out
