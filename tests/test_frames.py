"""core.frames is the contract every data source must satisfy."""
import pandas as pd
import pytest

from core.frames import (
    OHLCV,
    filter_regular_session,
    from_alpaca_bars,
    normalize_ohlcv,
    validate_ohlcv,
)


def make_frame(n=5, tz="UTC", freq="1h", start="2026-01-05 14:00"):
    idx = pd.date_range(start, periods=n, freq=freq, tz=tz)
    return pd.DataFrame(
        {"Open": range(n), "High": range(n), "Low": range(n),
         "Close": range(n), "Volume": range(n)},
        index=idx, dtype=float,
    )


class TestNormalize:
    def test_flattens_multiindex_columns(self):
        df = make_frame()
        df.columns = pd.MultiIndex.from_product([df.columns, ["SPY"]])
        assert list(normalize_ohlcv(df).columns) == OHLCV

    def test_names_the_index(self):
        assert normalize_ohlcv(make_frame()).index.name == "Date"

    def test_drops_unexpected_columns(self):
        df = make_frame().assign(vwap=1.0, trade_count=2)
        assert list(normalize_ohlcv(df).columns) == OHLCV

    def test_keeps_adj_close_when_present(self):
        df = make_frame().assign(**{"Adj Close": 1.0})
        assert "Adj Close" in normalize_ohlcv(df).columns


class TestValidate:
    def test_accepts_and_returns_a_good_frame(self):
        df = make_frame()
        assert validate_ohlcv(df) is df

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="Empty"):
            validate_ohlcv(make_frame().iloc[0:0])

    def test_rejects_missing_columns(self):
        with pytest.raises(ValueError, match="missing columns"):
            validate_ohlcv(make_frame().drop(columns=["Volume"]))

    def test_rejects_non_datetime_index(self):
        df = make_frame().reset_index(drop=True)
        with pytest.raises(ValueError, match="DatetimeIndex"):
            validate_ohlcv(df)

    def test_rejects_unsorted(self):
        with pytest.raises(ValueError, match="not sorted"):
            validate_ohlcv(make_frame().iloc[::-1])

    def test_rejects_nan_close(self):
        df = make_frame()
        df.loc[df.index[2], "Close"] = float("nan")
        with pytest.raises(ValueError, match="NaN Close"):
            validate_ohlcv(df)

    def test_context_appears_in_the_message(self):
        with pytest.raises(ValueError, match="for SPY"):
            validate_ohlcv(make_frame().iloc[0:0], context="SPY")


class TestFromAlpacaBars:
    def test_drops_symbol_level_and_titlecases(self):
        idx = pd.MultiIndex.from_product(
            [["SPY"], pd.date_range("2026-01-05 14:00", periods=3, freq="1h", tz="UTC")],
            names=["symbol", "timestamp"],
        )
        raw = pd.DataFrame(
            {"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5,
             "volume": 100.0, "trade_count": 5.0, "vwap": 1.4},
            index=idx,
        )
        out = from_alpaca_bars(raw)
        assert list(out.columns) == OHLCV       # trade_count and vwap dropped
        assert out.index.nlevels == 1
        assert out.index.name == "Date"


class TestRegularSession:
    def test_keeps_only_regular_session_hours(self):
        # 08:00 -> 21:00 UTC covers pre-market, session, and after-hours.
        df = make_frame(n=14, start="2026-01-05 08:00")
        kept = filter_regular_session(df)
        hours = {t.hour for t in kept.index.tz_convert("America/New_York")}
        assert hours == {10, 11, 12, 13, 14, 15}

    def test_drops_the_bar_straddling_the_open(self):
        df = make_frame(n=14, start="2026-01-05 08:00")
        et = filter_regular_session(df).index.tz_convert("America/New_York")
        assert 9 not in {t.hour for t in et}

    def test_start_is_configurable(self):
        df = make_frame(n=14, start="2026-01-05 08:00")
        et = filter_regular_session(df, start="09:00").index.tz_convert("America/New_York")
        assert 9 in {t.hour for t in et}

    def test_noop_for_daily_bars(self):
        df = make_frame(n=10, freq="1D", start="2026-01-05 00:00")
        assert len(filter_regular_session(df)) == len(df)

    def test_noop_for_tz_naive(self):
        df = make_frame(tz=None)
        assert filter_regular_session(df) is df

    def test_noop_for_empty(self):
        df = make_frame().iloc[0:0]
        assert filter_regular_session(df) is df
