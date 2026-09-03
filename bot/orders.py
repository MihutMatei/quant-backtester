"""Order decision logic.

Pure functions: no I/O, no broker calls. This is the live-trading counterpart to
the backtest loop, and the only piece of the bot that is trivially unit-testable.
"""
from dataclasses import dataclass

BUY = "buy"
SELL = "sell"

# Fractional share quantities are floats, so "flat" needs a tolerance rather
# than an equality test against zero.
POSITION_EPSILON = 1e-6


@dataclass(frozen=True)
class OrderIntent:
    """What the bot wants to do. Translated to a broker call by bot.broker."""

    symbol: str
    side: str
    qty: float
    reason: str


def is_flat(position, epsilon=POSITION_EPSILON):
    return abs(position) <= epsilon


def decide(current_position, target_signal, notional, price, symbol="SPY",
           epsilon=POSITION_EPSILON):
    """Map (held position, desired signal) to an OrderIntent, or None.

    Long/flat only - core.signals.rsi_signals defaults to long_only=True, so a
    target of -1 should never arrive. It is rejected rather than silently
    treated as flat, because reaching here means the caller changed the signal
    contract without updating the bot.

        position | signal | action
        ---------+--------+---------------------------
        flat     |   1    | BUY notional / price
        flat     |   0    | none
        long     |   1    | none (hold)
        long     |   0    | SELL the entire position
    """
    if target_signal not in (0.0, 1.0):
        raise ValueError(
            f"expected a long/flat signal (0 or 1), got {target_signal!r}; "
            "the bot cannot act on a short signal"
        )
    if price is None or price <= 0:
        raise ValueError(f"price must be positive, got {price!r}")

    flat = is_flat(current_position, epsilon)

    if flat and target_signal == 1.0:
        qty = notional / price
        if qty <= epsilon:
            return None
        return OrderIntent(symbol, BUY, qty, f"signal 1 while flat: buy ${notional:,.0f}")

    if not flat and target_signal == 0.0:
        if current_position < 0:
            raise ValueError(
                f"unexpected short position of {current_position}; the bot only "
                "opens long positions and will not net one out automatically"
            )
        return OrderIntent(symbol, SELL, current_position,
                           "signal 0 while long: close the position")

    return None
