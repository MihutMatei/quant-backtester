"""Signal generation shared by the backtester and the live bot.

Contract: signals["signal"].iloc[-1] is the position to hold AFTER that bar closes.
"""
import numpy as np
import pandas as pd


def rsi_signals(df, period=14, buy_threshold=30, sell_threshold=70,
                long_only=True):
    """
    RSI strategy signals.

    long_only=True (the default, and what the bot runs) is a stateful band:
    enter long when RSI <= buy_threshold, hold through the middle, exit to flat
    when RSI >= sell_threshold. Both thresholds matter, and the signal is
    {0, 1}. Entry dominates on a bar that somehow satisfies both.

    long_only=False keeps the original stateless two-sided mapping used by the
    earlier research: +1 oversold, -1 overbought, 0 in between, with no memory
    of the previous bar. Preserved so old backtests still reproduce.
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

    warm = signals['rsi'].iloc[period:]

    if long_only:
        # Stateful band. NaN means "no instruction on this bar", so the
        # forward-fill carries the previous position through the middle - that
        # carry is what makes sell_threshold an exit rather than dead config.
        instruction = np.where(warm <= buy_threshold, 1.0,
                               np.where(warm >= sell_threshold, 0.0, np.nan))
        held = pd.Series(instruction, index=warm.index).ffill().fillna(0.0)
        signals.loc[warm.index, 'signal'] = held
    else:
        # Stateless two-sided: each bar judged on its own.
        signals.loc[warm.index, 'signal'] = np.where(
            warm <= buy_threshold, 1.0,
            np.where(warm >= sell_threshold, -1.0, 0.0)
        )

    signals['positions'] = signals['signal'].diff()

    return signals
