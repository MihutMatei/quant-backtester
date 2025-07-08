from data_fetcher import fetch_data, fetch_data_legacy
from signals import *

def generate_moving_avg_crossover_strat(ticker, start_date=None, end_date=None, short_window=20, long_window=50, period=None, interval="1d"):
    """
    Generate moving average crossover strategy with flexible time control
    
    Args:
        ticker: Stock symbol
        start_date, end_date: Date range (mutually exclusive with period)
        short_window, long_window: Moving average windows
        period: Period string (1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max)
        interval: Data interval (1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo)
    """
    if start_date and end_date and not period:
        # Legacy mode - use start/end dates
        df = fetch_data_legacy(ticker, start_date, end_date)
    else:
        # New flexible mode
        df = fetch_data(ticker, start_date=start_date, end_date=end_date, period=period, interval=interval)
    
    signals = moving_average_signals(df, short_window, long_window)
    return df, signals

def generate_mean_reversal_strat(ticker, start_date=None, end_date=None, window=20, threshold=1.0, period=None, interval="1d"):
    """
    Generate mean reversion strategy with flexible time control
    
    Args:
        ticker: Stock symbol
        start_date, end_date: Date range (mutually exclusive with period)
        window: Rolling window for mean reversion
        threshold: Z-score threshold
        period: Period string (1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max)
        interval: Data interval (1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo)
    """
    if start_date and end_date and not period:
        # Legacy mode - use start/end dates
        df = fetch_data_legacy(ticker, start_date, end_date)
    else:
        # New flexible mode
        df = fetch_data(ticker, start_date=start_date, end_date=end_date, period=period, interval=interval)
    
    signals = mean_reversion_signals(df, window, threshold)
    return df, signals




def generate_williamsr_strat_long_and_short(
    ticker: str,
    start_date: str = None,
    end_date:   str = None,
    period:     str = None,
    interval:   str = "1d",
    wr_period:          int   = 14,
    long_entry_thresh:  float = -80.0,
    long_exit_thresh:   float = -50.0,
    short_entry_thresh: float = -20.0,
    short_exit_thresh:  float = -50.0
):
    """
    Returns price df and signals with explicit buy/sell/short/cover flags.
    """
    # 1) fetch data
    if start_date and end_date and not period:
        df = fetch_data_legacy(ticker, start_date, end_date)
    else:
        df = fetch_data(ticker,
                        start_date=start_date,
                        end_date=end_date,
                        period=period,
                        interval=interval)

    # 2) compute %R + stateful signal
    signals = williamsr_signals(
        df,
        period=wr_period,
        long_entry_thresh=long_entry_thresh,
        long_exit_thresh= long_exit_thresh,
        short_entry_thresh=short_entry_thresh,
        short_exit_thresh= short_exit_thresh
    )

    # 3) explicit event flags
    pos   = signals['positions']
    sig   = signals['signal']
    prev  = sig.shift(1).fillna(0.0)

    signals['long_entry']   = (pos ==  1.0) & (sig ==  1.0)
    signals['long_exit']    = (pos == -1.0) & (prev == 1.0)
    signals['short_entry']  = (pos == -1.0) & (sig == -1.0)
    signals['short_exit']   = (pos ==  1.0) & (prev == -1.0)

    return df, signals