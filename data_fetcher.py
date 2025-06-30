import yfinance as yf
import pandas as pd
import os

# Default configuration constants
DEFAULT_PERIOD = "2y"  # Default period for data fetching
DEFAULT_INTERVAL = "1d"  # Default interval (daily)

def fetch_data(ticker, start_date=None, end_date=None, period=None, interval=DEFAULT_INTERVAL, save_to_csv=False, progress=True):
    """
    Enhanced data fetcher with flexible time control
    
    Args:
        ticker: Stock ticker symbol
        start_date: Start date (YYYY-MM-DD) - mutually exclusive with period
        end_date: End date (YYYY-MM-DD) - mutually exclusive with period
        period: Period string (1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max) - mutually exclusive with start/end dates
        interval: Data interval (1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo)
        save_to_csv: Whether to save data to CSV file
        progress: Show download progress
    
    Returns:
        DataFrame with OHLCV data
    """
    
    # Validate inputs
    if (start_date or end_date) and period:
        raise ValueError("Cannot specify both period and start/end dates")
    
    if not period and not (start_date and end_date):
        period = DEFAULT_PERIOD
        print(f"No date range or period specified, using default period: {period}")
    
    # Download data
    if period:
        df = yf.download(
            ticker,
            period=period,
            interval=interval,
            auto_adjust=True,
            progress=progress,
        )
    else:
        df = yf.download(
            ticker,
            start=start_date,
            end=end_date,
            interval=interval,
            auto_adjust=True,
            progress=progress,
        )
    
    if df.empty:
        raise ValueError(f"No data downloaded for ticker: {ticker}")
    
    # Handle MultiIndex columns (occurs with multiple tickers)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # Ensure proper index name
    df.index.name = "Date"
    
    # Filter to expected columns
    expected_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    if 'Adj Close' in df.columns:
        expected_cols.append('Adj Close')
    df = df[[col for col in expected_cols if col in df.columns]]
    
    # Save to CSV if requested
    if save_to_csv:
        filename = f"{ticker}_{interval}.csv"
        df.to_csv(filename)
        print(f"Data saved to {filename}")
    
    return df

def fetch_5m(ticker, period=DEFAULT_PERIOD):
    """
    Convenience function for 5-minute data (similar to your example)
    """
    return fetch_data(ticker, period=period, interval="5m", save_to_csv=True, progress=False)

def fetch_1m(ticker, period="7d"):
    """
    Convenience function for 1-minute data (limited to 7 days max by yfinance)
    """
    return fetch_data(ticker, period=period, interval="1m", save_to_csv=True, progress=False)

def fetch_hourly(ticker, period="60d"):
    """
    Convenience function for hourly data
    """
    return fetch_data(ticker, period=period, interval="1h", save_to_csv=True, progress=False)

# Legacy function for backward compatibility
def fetch_data_legacy(ticker, start_date, end_date):
    """Legacy function to maintain backward compatibility"""
    return fetch_data(ticker, start_date=start_date, end_date=end_date)

