"""The unclosed-bar guard: acting on a partial bar is a live-only failure."""
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from bot.data import drop_unclosed, get_bars, interval_delta


def frame(n=30, freq="1h", start="2026-09-03 10:00"):
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    close = pd.Series(range(n), dtype=float) + 100
    return pd.DataFrame(
        {"Open": close.values, "High": close.values + 1, "Low": close.values - 1,
         "Close": close.values, "Volume": 1000.0},
        index=idx,
    )


class TestIntervalDelta:
    @pytest.mark.parametrize("interval,expected", [
        ("1h", timedelta(hours=1)), ("5m", timedelta(minutes=5)),
        ("15m", timedelta(minutes=15)), ("1d", timedelta(days=1))])
    def test_parses(self, interval, expected):
        assert interval_delta(interval) == expected

    def test_rejects_nonsense(self):
        with pytest.raises(ValueError, match="Unsupported interval"):
            interval_delta("1week")


class TestDropUnclosed:
    def test_drops_the_bar_still_forming(self):
        df = frame(n=3, start="2026-09-03 10:00")   # 10:00, 11:00, 12:00
        # 12:40 -> the 12:00 bar closes at 13:00 and is still open.
        now = datetime(2026, 9, 3, 12, 40, tzinfo=UTC)
        out = drop_unclosed(df, "1h", now=now)
        assert len(out) == 2
        assert out.index[-1] == pd.Timestamp("2026-09-03 11:00", tz="UTC")

    def test_keeps_a_bar_that_closed_exactly_now(self):
        df = frame(n=3, start="2026-09-03 10:00")
        now = datetime(2026, 9, 3, 13, 0, tzinfo=UTC)
        assert len(drop_unclosed(df, "1h", now=now)) == 3

    def test_keeps_everything_when_all_bars_are_old(self):
        df = frame(n=5)
        now = datetime(2026, 9, 4, tzinfo=UTC)
        assert len(drop_unclosed(df, "1h", now=now)) == 5

    def test_can_drop_everything(self):
        df = frame(n=2, start="2026-09-03 10:00")
        now = datetime(2026, 9, 3, 10, 30, tzinfo=UTC)
        assert drop_unclosed(df, "1h", now=now).empty

    def test_respects_the_interval_width(self):
        df = frame(n=3, freq="5min", start="2026-09-03 10:00")  # 10:00,10:05,10:10
        now = datetime(2026, 9, 3, 10, 12, tzinfo=UTC)
        assert len(drop_unclosed(df, "5m", now=now)) == 2


class Config:
    symbol, interval, feed = "SPY", "1h", "sip"
    lookback_days, rsi_period = 10, 14


class TestGetBars:
    def test_returns_only_closed_bars(self, monkeypatch):
        monkeypatch.setattr("bot.data.fetch_alpaca", lambda *a, **k: frame(n=30))
        now = datetime(2026, 9, 4, 15, 30, tzinfo=UTC)
        out = get_bars(Config(), now=now)
        assert (out.index + timedelta(hours=1) <= now).all()

    def test_raises_when_everything_is_unclosed(self, monkeypatch):
        monkeypatch.setattr("bot.data.fetch_alpaca",
                            lambda *a, **k: frame(n=2, start="2026-09-03 10:00"))
        with pytest.raises(ValueError, match="No closed"):
            get_bars(Config(), now=datetime(2026, 9, 3, 10, 30, tzinfo=UTC))

    def test_raises_when_too_few_bars_for_the_rsi_period(self, monkeypatch):
        monkeypatch.setattr("bot.data.fetch_alpaca", lambda *a, **k: frame(n=10))
        with pytest.raises(ValueError, match="BOT_LOOKBACK_DAYS"):
            get_bars(Config(), now=datetime(2026, 9, 4, tzinfo=UTC))
