"""Live bar data from Alpaca, normalized through core.frames."""
import re
from datetime import UTC, datetime, timedelta

from core.alpaca_source import fetch_alpaca

_UNITS = {"m": "minutes", "h": "hours", "d": "days"}


def interval_delta(interval):
    """'1h' -> timedelta(hours=1). The width of one bar."""
    match = re.fullmatch(r"(\d+)(m|h|d)", interval.strip().lower())
    if not match:
        raise ValueError(f"Unsupported interval {interval!r}; use e.g. '5m', '1h', '1d'")
    return timedelta(**{_UNITS[match.group(2)]: int(match.group(1))})


def drop_unclosed(df, interval, now=None):
    """Drop bars whose interval has not elapsed yet.

    Alpaca stamps a bar at its START and returns it while it is still forming,
    so the most recent row is usually partial. Acting on it means trading on
    incomplete data - a live-only failure the backtest cannot reproduce,
    because history only ever contains closed bars.
    """
    now = now or datetime.now(UTC)
    width = interval_delta(interval)
    return df[df.index + width <= now]


def get_bars(config, now=None):
    """Fetch recent closed bars as an OHLCV frame matching core.frames."""
    df = fetch_alpaca(
        config.symbol,
        period=f"{config.lookback_days}d",
        interval=config.interval,
        feed=config.feed,
    )
    closed = drop_unclosed(df, config.interval, now=now)

    if closed.empty:
        raise ValueError(
            f"No closed {config.interval} bars for {config.symbol} in the last "
            f"{config.lookback_days} days"
        )

    needed = config.rsi_period + 1
    if len(closed) < needed:
        raise ValueError(
            f"Only {len(closed)} closed bars for {config.symbol}; RSI-"
            f"{config.rsi_period} needs at least {needed}. Raise BOT_LOOKBACK_DAYS."
        )
    return closed
