"""bot.broker is I/O, so these use a fake client - no network, no account."""
import pytest

from bot.broker import DRY_RUN_ORDER_ID, Broker
from bot.orders import OrderIntent


class FakeAPIError(Exception):
    pass


class FakeClient:
    def __init__(self, position=None, error=None, equity=100_000.0, is_open=True):
        self._position, self._error = position, error
        self._equity, self._is_open = equity, is_open
        self.submitted = []

    def get_open_position(self, symbol):
        if self._error:
            raise self._error
        return type("P", (), {"qty": self._position})()

    def get_account(self):
        return type("A", (), {"equity": self._equity})()

    def get_clock(self):
        return type("C", (), {"is_open": self._is_open})()

    def submit_order(self, request):
        self.submitted.append(request)
        return type("O", (), {"id": "order-xyz"})()


def broker(client, dry_run=False):
    return Broker("k", "s", paper=True, dry_run=dry_run, client=client)


@pytest.fixture(autouse=True)
def patch_api_error(monkeypatch):
    """bot.broker imports APIError lazily; point it at our fake."""
    import sys
    import types
    mod = types.ModuleType("alpaca.common.exceptions")
    mod.APIError = FakeAPIError
    monkeypatch.setitem(sys.modules, "alpaca.common.exceptions", mod)


class TestGetPosition:
    def test_returns_the_quantity(self):
        assert broker(FakeClient(position="64.7")).get_position("SPY") == 64.7

    def test_flat_when_alpaca_says_the_position_does_not_exist(self):
        # Alpaca raises instead of returning zero; this must not propagate.
        err = FakeAPIError("position does not exist")
        assert broker(FakeClient(error=err)).get_position("SPY") == 0.0

    def test_flat_on_a_404(self):
        err = FakeAPIError('{"code":40410000,"message":"404 not found"}')
        assert broker(FakeClient(error=err)).get_position("SPY") == 0.0

    def test_other_errors_still_propagate(self):
        # A credentials or outage problem must not be read as "flat".
        with pytest.raises(FakeAPIError):
            broker(FakeClient(error=FakeAPIError("unauthorized"))).get_position("SPY")


class TestAccount:
    def test_equity(self):
        assert broker(FakeClient(equity=99_500.0)).get_equity() == 99_500.0

    @pytest.mark.parametrize("is_open", [True, False])
    def test_market_open(self, is_open):
        assert broker(FakeClient(is_open=is_open)).is_market_open() is is_open


class TestSubmit:
    def test_dry_run_submits_nothing(self):
        client = FakeClient()
        result = broker(client, dry_run=True).submit_order(
            OrderIntent("SPY", "buy", 1.0, "why"))
        assert result == DRY_RUN_ORDER_ID
        assert client.submitted == []
