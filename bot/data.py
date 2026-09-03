"""Live bar data from Alpaca, normalized through core.frames."""


def get_bars(symbol, interval, lookback):
    """Fetch recent bars and return a frame matching core.frames.OHLCV."""
    raise NotImplementedError
