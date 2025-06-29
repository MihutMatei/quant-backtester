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
