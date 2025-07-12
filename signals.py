import pandas as pd
import numpy as np

def moving_average_signals(df, short_window, long_window):
    signals = pd.DataFrame(index=df.index)
    signals['signal'] = 0.0

    price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'

    signals['short_mavg'] = df[price_col].rolling(window=short_window, min_periods=1).mean()
    signals['long_mavg'] = df[price_col].rolling(window=long_window, min_periods=1).mean()

    signals.loc[signals.index[short_window:], 'signal'] = np.where(
        signals['short_mavg'][short_window:] > signals['long_mavg'][short_window:], 1.0, -1.0
    )

    signals['positions'] = signals['signal'].diff()

    return signals

def mean_reversion_signals(df, window, threshold):
    signals = pd.DataFrame(index=df.index)
    signals['signal'] = 0.0

    price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
    price = df[price_col]
    # rolling stats
    rolling_mean = price.rolling(window=window, min_periods=1).mean()
    rolling_std  = price.rolling(window=window, min_periods=1).std()
    signals['zscore'] = (price - rolling_mean) / rolling_std

    # only assign from the first full window onward
    signals.loc[signals.index[window:], 'signal'] = np.where(
        signals['zscore'][window:] < -threshold, 1.0,
        np.where(signals['zscore'][window:] > threshold, -1.0, 0.0)
    )

    signals['positions'] = signals['signal'].diff()
    return signals

import pandas as pd
import numpy as np

def williamsr_signals(
    df: pd.DataFrame,
    period: int = 14,
    long_entry_thresh: float = -80.0,
    long_exit_thresh: float = -50.0,
    short_entry_thresh: float = -20.0,
    short_exit_thresh: float = -50.0
) -> pd.DataFrame:
    """
    Compute stateful Williams %R signals with separate long/short entry & exit.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain 'High', 'Low', and either 'Adj Close' or 'Close'.
    period : int
        Look-back window for %R.
    long_entry_thresh : float
        Go long when %R ≤ this (e.g. -80).
    long_exit_thresh : float
        Exit long when %R ≥ this (e.g. -50).
    short_entry_thresh : float
        Go short when %R ≥ this (e.g. -20).
    short_exit_thresh : float
        Exit short when %R ≤ this (e.g. -50).

    Returns
    -------
    signals : pd.DataFrame
        Columns:
          • wr          : the Williams %R series  
          • signal      : +1 long, -1 short, 0 flat (stateful)  
          • positions   : signal.diff()  
    """
    price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
    hh = df['High'].rolling(period, min_periods=period).max()
    ll = df['Low'] .rolling(period, min_periods=period).min()
    rng = (hh - ll).replace(0, np.nan)
    wr = -100.0 * (hh - df[price_col]) / rng

    # build stateful signal series
    signal = pd.Series(0.0, index=df.index)
    prev = 0.0
    for t in df.index:
        v = wr.loc[t]
        if np.isnan(v):
            curr = prev
        else:
            if prev != 1.0 and v <= long_entry_thresh:
                curr = 1.0
            elif prev == 1.0 and v >= long_exit_thresh:
                curr = 0.0
            elif prev != -1.0 and v >= short_entry_thresh:
                curr = -1.0
            elif prev == -1.0 and v <= short_exit_thresh:
                curr = 0.0
            else:
                curr = prev
        signal.loc[t] = curr
        prev = curr

    signals = pd.DataFrame({
        'wr':        wr,
        'signal':   signal,
    })
    signals['positions'] = signals['signal'].diff().fillna(0.0)
    return signals

def rsi_signals(df, period=14, buy_threshold=30, sell_threshold=70):
    """
    Pure RSI strategy signals
    
    Buy when RSI <= buy_threshold (oversold)
    Sell when RSI >= sell_threshold (overbought)
    """
    signals = pd.DataFrame(index=df.index)
    signals['signal'] = 0.0
    
    price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
    
    # Calculate RSI
    delta = df[price_col].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss
    signals['rsi'] = 100 - (100 / (1 + rs))
    
    # Generate signals using the consistent indexing pattern
    signals.loc[signals.index[period:], 'signal'] = np.where(
        signals['rsi'][period:] <= buy_threshold, 1.0,
        np.where(signals['rsi'][period:] >= sell_threshold, -1.0, 0.0)
    )
    
    signals['positions'] = signals['signal'].diff()
    
    return signals

def matei_signals(
    df,
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
    Matei's triple indicator strategy: RSI + Williams %R + Volatility filter
    
    Optimized with stateful logic similar to Williams %R:
    - Enter long when: RSI <= rsi_buy_th AND Williams %R <= wr_buy_th AND Volatility <= vol_buy_th
    - Exit long when: RSI >= rsi_sell_th OR Williams %R >= wr_sell_th OR Volatility >= vol_sell_th
    - Enter short when: RSI >= rsi_sell_th AND Williams %R >= wr_sell_th AND Volatility >= vol_sell_th
    - Exit short when: RSI <= rsi_buy_th OR Williams %R <= wr_buy_th OR Volatility <= vol_buy_th
    """
    signals = pd.DataFrame(index=df.index)
    signals['signal'] = 0.0
    
    price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
    
    # Calculate RSI
    delta = df[price_col].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=rsi_period, min_periods=1).mean()
    avg_loss = loss.rolling(window=rsi_period, min_periods=1).mean()
    rs = avg_gain / avg_loss
    signals['rsi'] = 100 - (100 / (1 + rs))
    
    # Calculate Williams %R
    highest_high = df['High'].rolling(window=wr_period, min_periods=1).max()
    lowest_low = df['Low'].rolling(window=wr_period, min_periods=1).min()
    price_range = highest_high - lowest_low
    price_range[price_range == 0] = np.nan
    signals['wr'] = (highest_high - df[price_col]) / price_range * -100
    
    # Calculate Volatility
    signals['vol'] = df[price_col].pct_change().rolling(window=vol_lookback, min_periods=1).std()
    
    # Build stateful signal series (similar to Williams %R approach)
    signal = pd.Series(0.0, index=df.index)
    prev = 0.0
    max_period = max(rsi_period, wr_period, vol_lookback)
    
    for i, t in enumerate(df.index):
        if i < max_period:
            # Not enough data for reliable signals
            signal.loc[t] = 0.0
            prev = 0.0
            continue
            
        rsi_val = signals.loc[t, 'rsi']
        wr_val = signals.loc[t, 'wr']
        vol_val = signals.loc[t, 'vol']
        
        # Skip if any indicator has NaN values
        if pd.isna(rsi_val) or pd.isna(wr_val) or pd.isna(vol_val):
            signal.loc[t] = prev
            continue
        
        # Long entry conditions (all must be true)
        long_entry = (
            prev != 1.0 and  # Not already long
            rsi_val <= rsi_buy_th and
            wr_val <= wr_buy_th and
            vol_val <= vol_buy_th
        )
        
        # Long exit conditions (any can be true)
        long_exit = (
            prev == 1.0 and  # Currently long
            (rsi_val >= rsi_sell_th or
             wr_val >= wr_sell_th or
             vol_val >= vol_sell_th)
        )
        
        # Short entry conditions (all must be true)
        short_entry = (
            prev != -1.0 and  # Not already short
            rsi_val >= rsi_sell_th and
            wr_val >= wr_sell_th and
            vol_val >= vol_sell_th
        )
        
        # Short exit conditions (any can be true)
        short_exit = (
            prev == -1.0 and  # Currently short
            (rsi_val <= rsi_buy_th or
             wr_val <= wr_buy_th or
             vol_val <= vol_buy_th)
        )
        
        # Apply state transitions (optimized for better signal flow)
        if long_entry:
            curr = 1.0
        elif short_entry:
            curr = -1.0
        elif long_exit:
            curr = -1.0  # Exit long and immediately enter short
        elif short_exit:
            curr = 1.0   # Exit short and immediately enter long (triggers COVER)
        else:
            curr = prev  # Hold current position
        
        signal.loc[t] = curr
        prev = curr
    
    signals['signal'] = signal
    signals['positions'] = signals['signal'].diff()
    
    return signals