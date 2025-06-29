import yfinance as yf
import pandas as pd

def fetch_data(ticker, start_date, end_date):
    df = yf.download(ticker, start=start_date, end=end_date, auto_adjust=True)
    if df.empty:
        raise ValueError(f"No data downloaded for ticker: {ticker}")
    expected_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    # Keep Adj Close if it exists (though with auto_adjust=True it might not)
    if 'Adj Close' in df.columns:
        expected_cols.append('Adj Close')
    df = df[[col for col in expected_cols if col in df.columns]]
    return df

