"""Order decision logic.

Pure function: no I/O, no broker calls. This is the live-trading counterpart to
the backtest loop, and the only piece of the bot that is trivially unit-testable.
"""


def decide(current_position, target_signal):
    """Map (held position, desired signal) to an OrderIntent, or None to do nothing."""
    raise NotImplementedError
