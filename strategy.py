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




def generate_williamsr_strat(
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

def generate_rsi_strat(
    ticker,
    start_date=None,
    end_date=None,
    period=None,
    interval="1d",
    rsi_period=14,
    buy_threshold=30,
    sell_threshold=70
):
    """
    Generate pure RSI strategy
    
    Args:
        ticker: Stock symbol
        start_date, end_date: Date range (mutually exclusive with period)
        period: Period string (1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max)
        interval: Data interval (1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo)
        rsi_period: RSI calculation period
        buy_threshold: Buy when RSI <= this value (oversold)
        sell_threshold: Sell when RSI >= this value (overbought)
    """
    if start_date and end_date and not period:
        df = fetch_data_legacy(ticker, start_date, end_date)
    else:
        df = fetch_data(ticker, start_date=start_date, end_date=end_date, period=period, interval=interval)
    
    signals = rsi_signals(df, rsi_period, buy_threshold, sell_threshold)
    return df, signals

def generate_matei_strat(
    ticker,
    start_date=None,
    end_date=None,
    period=None,
    interval="5m",
    rsi_period=72,
    wr_period=72,
    vol_lookback=72,
    rsi_buy_th=60,
    rsi_sell_th=40,
    wr_buy_th=-85,
    wr_sell_th=-15,
    vol_buy_th=0.007,
    vol_sell_th=0.000
):
    """
    Generate Matei's triple indicator strategy with RSI, Williams %R, and volatility filters
    
    Args:
        ticker: Stock symbol
        start_date, end_date: Date range (mutually exclusive with period)
        period: Period string (1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max)
        interval: Data interval (1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo)
        rsi_period: RSI calculation period
        wr_period: Williams %R calculation period
        vol_lookback: Volatility lookback period
        rsi_buy_th: RSI buy threshold
        rsi_sell_th: RSI sell threshold
        wr_buy_th: Williams %R buy threshold
        wr_sell_th: Williams %R sell threshold
        vol_buy_th: Volatility buy threshold
        vol_sell_th: Volatility sell threshold
    """
    # Fetch data using existing infrastructure
    if start_date and end_date and not period:
        df = fetch_data_legacy(ticker, start_date, end_date)
    else:
        df = fetch_data(ticker, start_date=start_date, end_date=end_date, period=period, interval=interval)
    
    # Generate signals using the Matei strategy
    signals = matei_signals(
        df,
        rsi_period=rsi_period,
        wr_period=wr_period,
        vol_lookback=vol_lookback,
        rsi_buy_th=rsi_buy_th,
        rsi_sell_th=rsi_sell_th,
        wr_buy_th=wr_buy_th,
        wr_sell_th=wr_sell_th,
        vol_buy_th=vol_buy_th,
        vol_sell_th=vol_sell_th
    )
    
    return df, signals