"""OHLCV frame normalization.

Shared so that every data source - yfinance in research, Alpaca in the bot -
yields structurally identical frames by construction rather than by luck.
"""
import pandas as pd

OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def normalize_ohlcv(df):
    """Flatten MultiIndex columns, name the index, filter to OHLCV (+ Adj Close)."""
    # Handle MultiIndex columns (occurs with multiple tickers)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Ensure proper index name
    df.index.name = "Date"

    # Filter to expected columns
    expected_cols = list(OHLCV)
    if "Adj Close" in df.columns:
        expected_cols.append("Adj Close")
    return df[[col for col in expected_cols if col in df.columns]]


def validate_ohlcv(df, context=""):
    """Raise if `df` is not a usable OHLCV frame.

    The bot acts on the last bar of whatever it is handed, so a malformed or
    stale frame must fail loudly here rather than silently produce a signal.
    """
    where = f" for {context}" if context else ""

    if df is None or df.empty:
        raise ValueError(f"Empty OHLCV frame{where}")

    missing = [col for col in OHLCV if col not in df.columns]
    if missing:
        raise ValueError(f"OHLCV frame{where} missing columns: {missing}")

    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(f"OHLCV frame{where} needs a DatetimeIndex")

    if not df.index.is_monotonic_increasing:
        raise ValueError(f"OHLCV frame{where} is not sorted by time")

    if df["Close"].isna().any():
        n = int(df["Close"].isna().sum())
        raise ValueError(f"OHLCV frame{where} has {n} NaN Close value(s)")

    return df
