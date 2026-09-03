"""core.signals is what the live bot acts on, so the contract matters."""
import numpy as np
import pandas as pd

from core.signals import rsi_signals


def oscillating_frame(n=120):
    """Prices that swing far enough to drive RSI through both thresholds."""
    idx = pd.date_range("2026-01-05", periods=n, freq="1h", tz="UTC")
    close = 100 + 20 * np.sin(np.linspace(0, 8 * np.pi, n))
    return pd.DataFrame(
        {"Open": close, "High": close + 1, "Low": close - 1,
         "Close": close, "Volume": 1000.0},
        index=idx,
    )


class TestLongOnly:
    def test_default_emits_only_long_or_flat(self):
        sig = rsi_signals(oscillating_frame())["signal"]
        assert set(sig.unique()) <= {0.0, 1.0}

    def test_two_sided_can_emit_short(self):
        sig = rsi_signals(oscillating_frame(), long_only=False)["signal"]
        assert -1.0 in set(sig.unique())

    def test_long_only_never_goes_short(self):
        df = oscillating_frame()
        assert (rsi_signals(df, long_only=True)["signal"] >= 0).all()

    def test_positions_derived_after_the_clip(self):
        out = rsi_signals(oscillating_frame())
        pd.testing.assert_series_equal(
            out["positions"], out["signal"].diff(), check_names=False)


class TestHysteresis:
    """long_only is a stateful band: enter at buy, hold, exit at sell."""

    def test_sell_threshold_changes_the_signal(self):
        # This is the whole point of the band; it used to be inert.
        df = oscillating_frame()
        base = rsi_signals(df, 14, 45, 50)["signal"]
        assert not rsi_signals(df, 14, 45, 70)["signal"].equals(base)

    def test_entry_when_rsi_at_or_below_buy(self):
        out = rsi_signals(oscillating_frame(), 14, 45, 55).iloc[15:]
        assert (out.loc[out["rsi"] <= 45, "signal"] == 1.0).all()

    def test_exit_when_rsi_at_or_above_sell(self):
        out = rsi_signals(oscillating_frame(), 14, 45, 55).iloc[15:]
        assert (out.loc[out["rsi"] >= 55, "signal"] == 0.0).all()

    def test_position_is_held_through_the_middle_band(self):
        """The carry is what distinguishes a band from a threshold."""
        df = oscillating_frame()
        out = rsi_signals(df, 14, 45, 55).iloc[15:]
        middle = out[(out["rsi"] > 45) & (out["rsi"] < 55)]
        # in the middle band the signal must equal the previous bar's
        prev = out["signal"].shift(1).loc[middle.index]
        pd.testing.assert_series_equal(middle["signal"], prev, check_names=False)

    def test_a_wider_band_holds_longer(self):
        df = oscillating_frame()
        narrow = rsi_signals(df, 14, 45, 50)["signal"]
        wide = rsi_signals(df, 14, 45, 70)["signal"]
        assert wide.mean() > narrow.mean()
        assert wide.diff().abs().sum() < narrow.diff().abs().sum()

    def test_starts_flat_before_any_entry(self):
        assert rsi_signals(oscillating_frame(), 14, 45, 50)["signal"].iloc[0] == 0.0

    def test_two_sided_remains_stateless(self):
        """long_only=False must still reproduce the old research behaviour."""
        df = oscillating_frame()
        out = rsi_signals(df, 14, 30, 70, long_only=False).iloc[15:]
        expected = np.where(out["rsi"] <= 30, 1.0,
                            np.where(out["rsi"] >= 70, -1.0, 0.0))
        assert (out["signal"].values == expected).all()


class TestContract:
    def test_index_is_preserved(self):
        df = oscillating_frame()
        assert rsi_signals(df).index.equals(df.index)

    def test_latest_signal_is_a_scalar_position(self):
        # bot/run.py reads exactly this
        assert rsi_signals(oscillating_frame())["signal"].iloc[-1] in (0.0, 1.0)

    def test_entry_threshold_is_respected(self):
        df = oscillating_frame()
        warm = rsi_signals(df, period=14, buy_threshold=30,
                           sell_threshold=70).iloc[15:]
        assert (warm.loc[warm["rsi"] <= 30, "signal"] == 1.0).all()

    def test_rsi_is_scale_invariant(self):
        """RSI is a ratio of gains to losses, so a constant factor cancels."""
        df = oscillating_frame()
        doubled = df.assign(Close=df["Close"] * 2)
        pd.testing.assert_series_equal(
            rsi_signals(df)["rsi"], rsi_signals(doubled)["rsi"])

    def test_uses_adj_close_when_available(self):
        df = oscillating_frame()
        # A monotonic series has no losses at all, so RSI pins to 100.
        trending = df.assign(**{"Adj Close": np.arange(len(df), dtype=float) + 1})
        rsi = rsi_signals(trending)["rsi"].dropna()
        assert (rsi == 100.0).all()
        assert not rsi_signals(trending)["rsi"].equals(rsi_signals(df)["rsi"])
