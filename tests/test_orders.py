"""bot.orders is pure, so the whole decision table can be pinned exactly."""
import dataclasses

import pytest

from bot.orders import BUY, SELL, OrderIntent, decide, is_flat

NOTIONAL = 50_000.0
PRICE = 500.0


class TestDecisionTable:
    def test_flat_and_signal_long_buys(self):
        intent = decide(0.0, 1.0, NOTIONAL, PRICE)
        assert intent.side == BUY
        assert intent.qty == pytest.approx(NOTIONAL / PRICE)

    def test_flat_and_signal_flat_does_nothing(self):
        assert decide(0.0, 0.0, NOTIONAL, PRICE) is None

    def test_long_and_signal_long_holds(self):
        assert decide(100.0, 1.0, NOTIONAL, PRICE) is None

    def test_long_and_signal_flat_sells_everything(self):
        intent = decide(100.0, 0.0, NOTIONAL, PRICE)
        assert intent.side == SELL
        assert intent.qty == pytest.approx(100.0)


class TestSizing:
    def test_quantity_is_notional_over_price(self):
        assert decide(0.0, 1.0, 50_000.0, 772.55).qty == pytest.approx(50_000 / 772.55)

    def test_fractional_quantities_are_allowed(self):
        # SPY is fractionable, so the backtest's cash/price sizing carries over.
        assert decide(0.0, 1.0, 1_000.0, 772.55).qty == pytest.approx(1.294414, abs=1e-5)

    def test_sell_closes_the_exact_position_not_the_notional(self):
        assert decide(3.5, 0.0, NOTIONAL, PRICE).qty == pytest.approx(3.5)


class TestEpsilon:
    def test_dust_counts_as_flat(self):
        assert is_flat(1e-9)
        assert decide(1e-9, 1.0, NOTIONAL, PRICE).side == BUY

    def test_dust_position_is_not_sold(self):
        assert decide(1e-9, 0.0, NOTIONAL, PRICE) is None

    def test_real_position_is_not_flat(self):
        assert not is_flat(0.01)


class TestGuards:
    def test_short_signal_is_rejected(self):
        # long_only=True should make this unreachable; if it arrives, the
        # signal contract changed without the bot being updated.
        with pytest.raises(ValueError, match="long/flat"):
            decide(0.0, -1.0, NOTIONAL, PRICE)

    @pytest.mark.parametrize("price", [0.0, -1.0, None])
    def test_bad_price_is_rejected(self, price):
        with pytest.raises(ValueError, match="price must be positive"):
            decide(0.0, 1.0, NOTIONAL, price)

    def test_existing_short_is_rejected(self):
        with pytest.raises(ValueError, match="unexpected short"):
            decide(-5.0, 0.0, NOTIONAL, PRICE)

    def test_notional_too_small_to_buy_anything(self):
        assert decide(0.0, 1.0, 0.0, PRICE) is None


def test_intent_is_immutable():
    intent = OrderIntent("SPY", BUY, 1.0, "why")
    with pytest.raises(dataclasses.FrozenInstanceError):
        intent.qty = 2.0
