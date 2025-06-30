from data_fetcher import fetch_data
from signals import *

def generate_moving_avg_corssorver_strat(ticker, start_date, end_date, short_window, long_window):
    df = fetch_data(ticker, start_date, end_date)
    signals = moving_average_signals(df, short_window, long_window)
    return df, signals

def generate_mean_reversal_strat(ticker, start_date, end_date, window, treshold):
    df = fetch_data(ticker, start_date, end_date)
    signals = mean_reversion_signals(df, window, treshold)
    return df, signals
