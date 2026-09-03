"""Signal generation shared by the backtester and the live bot.

Contract: signals["signal"].iloc[-1] is the position to hold AFTER that bar closes.
"""
import pandas as pd
import numpy as np


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
