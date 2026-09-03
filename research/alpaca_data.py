"""Historical bars from Alpaca, for backtesting on the data the bot will trade.

yfinance caps hourly history at 730 days; Alpaca serves 6+ years of hourly SIP
bars. Using it here means the backtest and the live bot aggregate identical
bars instead of windows offset by 30 minutes.
"""
import os
import re
from datetime import datetime, timedelta, timezone

from core.env import load_dotenv
from core.frames import filter_regular_session, from_alpaca_bars, validate_ohlcv

# Recent SIP data is withheld from free accounts; stay clear of the boundary.
_SIP_DELAY = timedelta(minutes=20)

_PERIOD_UNITS = {"d": 1, "mo": 30, "y": 365}


def _period_to_timedelta(period):
    """'30d' / '6mo' / '2y' -> timedelta. Mirrors the yfinance period strings."""
    match = re.fullmatch(r"(\d+)(d|mo|y)", period.strip().lower())
    if not match:
        raise ValueError(f"Unsupported period {period!r}; use e.g. '30d', '6mo', '2y'")
    amount, unit = int(match.group(1)), match.group(2)
    return timedelta(days=amount * _PERIOD_UNITS[unit])


def _timeframe(interval):
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    units = {"m": TimeFrameUnit.Minute, "h": TimeFrameUnit.Hour, "d": TimeFrameUnit.Day}
    match = re.fullmatch(r"(\d+)(m|h|d)", interval.strip().lower())
    if not match:
        raise ValueError(f"Unsupported interval {interval!r}; use e.g. '5m', '1h', '1d'")
    return TimeFrame(int(match.group(1)), units[match.group(2)])


def _client():
    from alpaca.data.historical import StockHistoricalDataClient
    load_dotenv()
    key, secret = os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY")
    if not key or not secret:
        raise RuntimeError(
            "APCA_API_KEY_ID / APCA_API_SECRET_KEY not set. Put them in .env and "
            "load it, or export them before running."
        )
    return StockHistoricalDataClient(key, secret)


def fetch_alpaca(ticker, start_date=None, end_date=None, period=None,
                 interval="1h", feed="sip", regular_session=True,
                 save_to_csv=False):
    """Fetch historical bars from Alpaca as an OHLCV frame.

    Signature mirrors research.data_fetcher.fetch_data so the two are
    interchangeable. `regular_session` drops extended-hours bars, which yfinance
    never includes.
    """
    from alpaca.data.enums import DataFeed
    from alpaca.data.requests import StockBarsRequest

    if (start_date or end_date) and period:
        raise ValueError("Cannot specify both period and start/end dates")

    end = (datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
           if end_date else datetime.now(timezone.utc) - _SIP_DELAY)
    if start_date:
        start = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
    else:
        start = end - _period_to_timedelta(period or "30d")

    bars = _client().get_stock_bars(StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=_timeframe(interval),
        start=start,
        end=end,
        feed=DataFeed(feed.lower()),
    )).df

    if bars.empty:
        raise ValueError(f"No Alpaca data for {ticker} ({interval}, {feed})")

    df = from_alpaca_bars(bars)
    if regular_session:
        df = filter_regular_session(df)
    validate_ohlcv(df, context=f"{ticker} via Alpaca {feed}")

    if save_to_csv:
        filename = f"{ticker}_{interval}_alpaca.csv"
        df.to_csv(filename)
        print(f"Data saved to {filename}")

    return df
