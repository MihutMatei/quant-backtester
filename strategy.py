from data_fetcher import fetch_data
from signals import moving_average_signals

def generate_strategy(ticker, start_date, end_date, short_window, long_window):
    df = fetch_data(ticker, start_date, end_date)
    signals = moving_average_signals(df, short_window, long_window)
    return df, signals
