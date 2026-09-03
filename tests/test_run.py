"""Every exit path must report exactly once, and reporting must never block trading."""
from dataclasses import dataclass, field

import pandas as pd
import pytest

from bot import run as run_module


@dataclass
class FakeConfig:
    symbol: str = "SPY"
    interval: str = "1h"
    notional: float = 50_000.0
    rsi_period: int = 14
    rsi_buy: float = 45.0
    rsi_sell: float = 50.0
    lookback_days: int = 10
    feed: str = "sip"
    db_path: str = ""
    dry_run: bool = True
    heartbeat_url: str = "https://hc-ping.com/test"
    api_key: str = field(default="k", repr=False)
    api_secret: str = field(default="s", repr=False)


class FakeBroker:
    def __init__(self, *a, market_open=True, position=0.0, **k):
        self._open, self._position = market_open, position
        self.orders = []

    def is_market_open(self):
        return self._open

    def get_position(self, symbol):
        return self._position

    def get_equity(self):
        return 100_000.0

    def submit_order(self, intent):
        self.orders.append(intent)
        return "order-1"


def bars(n=60, rsi_direction="down"):
    idx = pd.date_range("2026-09-01 14:00", periods=n, freq="1h", tz="UTC")
    # Falling prices drive RSI low (entry); rising drives it high (exit).
    close = pd.Series(range(n, 0, -1) if rsi_direction == "down" else range(n),
                      dtype=float) + 100
    return pd.DataFrame({"Open": close.values, "High": close.values + 1,
                         "Low": close.values - 1, "Close": close.values,
                         "Volume": 1000.0}, index=idx)


class Pings:
    def __init__(self, returns=True):
        self.ok_calls, self.fail_calls, self.returns = [], [], returns

    def ok(self, url, summary=""):
        self.ok_calls.append((url, summary))
        return self.returns

    def fail(self, url, detail=""):
        self.fail_calls.append((url, detail))
        return self.returns


@pytest.fixture
def env(monkeypatch, tmp_path):
    pings = Pings()
    cfg = FakeConfig(db_path=str(tmp_path / "bot.db"))
    monkeypatch.setattr(run_module, "load_config", lambda: cfg)
    monkeypatch.setattr(run_module, "heartbeat", pings)
    monkeypatch.setattr(run_module, "get_bars", lambda c: bars())
    return cfg, pings, monkeypatch


class TestEveryPathReports:
    def test_market_closed(self, env):
        cfg, pings, mp = env
        mp.setattr(run_module, "Broker", lambda *a, **k: FakeBroker(market_open=False))
        assert run_module.main() == 0
        assert len(pings.ok_calls) == 1
        assert "market closed" in pings.ok_calls[0][1]
        assert pings.fail_calls == []

    def test_no_action(self, env):
        cfg, pings, mp = env
        mp.setattr(run_module, "get_bars", lambda c: bars(rsi_direction="up"))
        mp.setattr(run_module, "Broker", lambda *a, **k: FakeBroker())
        assert run_module.main() == 0
        assert "no action" in pings.ok_calls[0][1]

    def test_a_trade(self, env):
        cfg, pings, mp = env
        broker = FakeBroker()
        mp.setattr(run_module, "Broker", lambda *a, **k: broker)
        assert run_module.main() == 0
        assert len(broker.orders) == 1
        assert "buy" in pings.ok_calls[0][1]
        assert "SPY" in pings.ok_calls[0][1]

    def test_already_handled_bar(self, env):
        cfg, pings, mp = env
        mp.setattr(run_module, "Broker", lambda *a, **k: FakeBroker())
        run_module.main()
        run_module.main()          # same bar again
        assert "already handled" in pings.ok_calls[1][1]
        assert len(pings.ok_calls) == 2

    def test_failure_pings_fail_and_exits_nonzero(self, env):
        cfg, pings, mp = env

        def boom(_):
            raise RuntimeError("alpaca is down")

        mp.setattr(run_module, "get_bars", boom)
        mp.setattr(run_module, "Broker", lambda *a, **k: FakeBroker())
        assert run_module.main() == 1
        assert pings.ok_calls == []
        assert "alpaca is down" in pings.fail_calls[0][1]


class TestReportingCannotBlockTrading:
    def test_a_failing_ping_does_not_change_the_exit_code(self, env):
        cfg, pings, mp = env
        pings.returns = False          # every ping fails
        broker = FakeBroker()
        mp.setattr(run_module, "Broker", lambda *a, **k: broker)
        assert run_module.main() == 0
        assert len(broker.orders) == 1  # the trade still happened

    def test_the_order_is_submitted_before_the_ping(self, env):
        """A ping means the work completed, not that it started."""
        cfg, pings, mp = env
        broker = FakeBroker()
        order_seen_at_ping = {}

        def spy_ok(url, summary=""):
            order_seen_at_ping["orders"] = len(broker.orders)
            return True

        pings.ok = spy_ok
        mp.setattr(run_module, "Broker", lambda *a, **k: broker)
        run_module.main()
        assert order_seen_at_ping["orders"] == 1

    def test_no_url_configured_still_runs(self, env):
        cfg, pings, mp = env
        cfg.heartbeat_url = ""
        broker = FakeBroker()
        mp.setattr(run_module, "Broker", lambda *a, **k: broker)
        assert run_module.main() == 0
        assert len(broker.orders) == 1
