"""execution_lag decides whether the backtest can be believed.

Signals are computed on a bar's close; filling at that same close is a
look-ahead the live bot cannot reproduce.
"""
import pandas as pd
import pytest

from research.backtest import backtest_strategy


@pytest.fixture
def frame():
    """Open and Close differ sharply so the fill price identifies the bar used."""
    idx = pd.date_range("2026-01-05 14:00", periods=4, freq="1h", tz="UTC")
    return pd.DataFrame(
        {"Open": [100.0, 200.0, 300.0, 400.0],
         "High": [150.0, 250.0, 350.0, 450.0],
         "Low": [90.0, 190.0, 290.0, 390.0],
         "Close": [110.0, 210.0, 310.0, 410.0],
         "Volume": [1000.0] * 4},
        index=idx,
    )


@pytest.fixture
def go_long(frame):
    return pd.DataFrame({"signal": [0.0, 1.0, 1.0, 1.0]}, index=frame.index)


def buys(txns):
    return [t for t in txns if t["Action"] == "BUY"]


def run(frame, signals, lag):
    return backtest_strategy(
        frame, signals, 10000.0, log_transactions=True,
        stop_loss_pct=None, take_profit_pct=None, use_trailing_stop=False,
        enable_shorting=False, dedup_window_minutes=0, spread_pct=0.0,
        execution_lag=lag)


def test_lag_zero_fills_at_the_signal_bar_close(frame, go_long):
    _, txns = run(frame, go_long, 0)
    assert buys(txns)[0]["Price"] == pytest.approx(210.0)   # bar 1 close


def test_lag_one_fills_at_the_next_bar_open(frame, go_long):
    _, txns = run(frame, go_long, 1)
    assert buys(txns)[0]["Price"] == pytest.approx(300.0)   # bar 2 open


def test_lag_delays_the_trade_by_one_bar(frame, go_long):
    _, zero = run(frame, go_long, 0)
    _, one = run(frame, go_long, 1)
    assert buys(one)[0]["Date"] - buys(zero)[0]["Date"] == pd.Timedelta(hours=1)


def test_lag_zero_reproduces_close_only_behaviour(frame, go_long):
    """Without Open the old path must still work."""
    _, txns = run(frame.drop(columns=["Open"]), go_long, 0)
    assert buys(txns)[0]["Price"] == pytest.approx(210.0)


def test_logging_flag_does_not_change_results(frame, go_long):
    """log_transactions gated the dedup clock; it must be inert now."""
    finals = []
    for flag in (True, False):
        pf, _ = backtest_strategy(
            frame, go_long, 10000.0, log_transactions=flag,
            stop_loss_pct=0.02, take_profit_pct=0.05, enable_shorting=True,
            dedup_window_minutes=30, spread_pct=0.001, execution_lag=1)
        finals.append(pf["total"].iloc[-1])
    assert finals[0] == pytest.approx(finals[1])


def test_portfolio_index_matches_input(frame, go_long):
    pf, _ = run(frame, go_long, 1)
    assert pf.index.equals(frame.index)
