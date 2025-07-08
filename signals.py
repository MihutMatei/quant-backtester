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