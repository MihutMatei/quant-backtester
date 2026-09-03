"""Alpaca trading client wrapper."""


def get_position(symbol):
    """Current position size for `symbol`; 0.0 when flat."""
    raise NotImplementedError


def submit_order(intent):
    """Send an OrderIntent to Alpaca."""
    raise NotImplementedError
