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


def from_alpaca_bars(df):
    """Convert a raw alpaca-py bars frame to the OHLCV contract.

    Alpaca returns a (symbol, timestamp) MultiIndex with lowercase columns plus
    trade_count and vwap. Kept here rather than in bot/ so the backtester and
    the bot shape Alpaca data identically. Pure pandas - no alpaca import.
    """
    if getattr(df.index, "nlevels", 1) > 1:
        df = df.droplevel("symbol")
    df = df.rename(columns={col: col.capitalize() for col in df.columns})
    return normalize_ohlcv(df)


def filter_regular_session(df, tz="America/New_York", start="09:30", end="16:00"):
    """Drop pre- and post-market bars, keeping [start, end) in `tz`.

    Alpaca includes extended hours by default; yfinance does not. Filtering
    makes the two comparable. No-op for daily-or-coarser bars, where the
    concept does not apply.
    """
    if df.empty or not isinstance(df.index, pd.DatetimeIndex) or df.index.tz is None:
        return df

    # Daily and coarser bars have no intraday session to filter.
    if len(df) > 1 and df.index.to_series().diff().median() >= pd.Timedelta(days=1):
        return df

    local = df.tz_convert(tz)
    return local.between_time(start, end, inclusive="left").tz_convert(df.index.tz)
