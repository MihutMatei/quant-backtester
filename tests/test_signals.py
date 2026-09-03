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

    def test_long_only_maps_short_to_flat_not_to_long(self):
        df = oscillating_frame()
        two = rsi_signals(df, long_only=False)["signal"]
        one = rsi_signals(df, long_only=True)["signal"]
        # every -1 becomes 0; every other value is untouched
        assert (one[two == -1.0] == 0.0).all()
        assert (one[two != -1.0] == two[two != -1.0]).all()

    def test_positions_derived_after_the_clip(self):
        out = rsi_signals(oscillating_frame())
        pd.testing.assert_series_equal(
            out["positions"], out["signal"].diff(), check_names=False)


class TestContract:
    def test_index_is_preserved(self):
        df = oscillating_frame()
        assert rsi_signals(df).index.equals(df.index)

    def test_latest_signal_is_a_scalar_position(self):
        # bot/run.py reads exactly this
        assert rsi_signals(oscillating_frame())["signal"].iloc[-1] in (0.0, 1.0)

    def test_thresholds_are_respected(self):
        df = oscillating_frame()
        out = rsi_signals(df, period=14, buy_threshold=30, sell_threshold=70)
        warm = out.iloc[15:]
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
