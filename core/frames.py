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
