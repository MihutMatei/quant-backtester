"""Signal generation shared by the backtester and the live bot.

Contract: signals["signal"].iloc[-1] is the position to hold AFTER that bar closes.
"""
import numpy as np
import pandas as pd


def rsi_signals(df, period=14, buy_threshold=30, sell_threshold=70,
                long_only=True):
    """
    Pure RSI strategy signals

    Buy when RSI <= buy_threshold (oversold)
    Sell when RSI >= sell_threshold (overbought)

    With long_only (the default), the short leg is mapped to flat so the
    signal is {0, 1}. Pass long_only=False to reproduce the two-sided
    research behaviour.

    NOTE: sell_threshold has no effect when long_only=True. Overbought maps to
    -1 and then clips to 0, which is the same value the neutral band already
    produces, so the position is held exactly while RSI <= buy_threshold and
    buy_threshold alone controls both entry and exit. It is not an
    enter-at-30 / exit-at-70 system. sell_threshold only bites two-sided.
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

    if long_only:
        # -1 (short) becomes 0 (flat); positions must be derived after this.
        signals['signal'] = signals['signal'].clip(lower=0.0)

    signals['positions'] = signals['signal'].diff()

    return signals
