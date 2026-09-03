"""core.metrics: annualization was silently wrong for every intraday run."""
import numpy as np
import pandas as pd
import pytest

from core.metrics import TRADING_DAYS_PER_YEAR, bars_per_year, calculate_performance_metrics


class TestBarsPerYear:
    def test_daily_is_trading_days(self):
        assert bars_per_year("1d") == TRADING_DAYS_PER_YEAR

    def test_five_minute_bars(self):
        assert bars_per_year("5m") == 78 * TRADING_DAYS_PER_YEAR

    def test_hourly_bars(self):
        assert bars_per_year("1h") == 6.5 * TRADING_DAYS_PER_YEAR

    def test_unknown_interval_raises(self):
        with pytest.raises(ValueError, match="Unknown interval"):
            bars_per_year("7s")


class TestMetrics:
    def test_total_return(self):
        eq = pd.Series([100.0, 110.0, 121.0])
        assert calculate_performance_metrics(eq)["Total_Return"] == pytest.approx(21.0)

    def test_max_drawdown(self):
        eq = pd.Series([100.0, 120.0, 90.0, 130.0])   # peak 120 -> trough 90
        assert calculate_performance_metrics(eq)["Max_Drawdown"] == pytest.approx(-25.0)

    def test_no_drawdown_when_monotonic(self):
        eq = pd.Series([100.0, 101.0, 102.0])
        assert calculate_performance_metrics(eq)["Max_Drawdown"] == pytest.approx(0.0)

    def test_zero_volatility_gives_zero_sharpe(self):
        eq = pd.Series([100.0] * 10)
        assert calculate_performance_metrics(eq)["Sharpe_Ratio"] == 0

    def test_interval_changes_annualization(self):
        rng = np.random.default_rng(0)
        eq = pd.Series(100 * (1 + rng.normal(0, 0.001, 500)).cumprod())
        daily = calculate_performance_metrics(eq)
        intraday = calculate_performance_metrics(eq, interval="5m")
        ratio = np.sqrt(bars_per_year("5m") / TRADING_DAYS_PER_YEAR)
        assert intraday["Sharpe_Ratio"] == pytest.approx(daily["Sharpe_Ratio"] * ratio)

    def test_explicit_periods_per_year_wins(self):
        eq = pd.Series([100.0, 101.0, 102.0, 103.0])
        assert calculate_performance_metrics(eq, periods_per_year=99)["Periods_Per_Year"] == 99

    def test_accepts_a_dataframe(self):
        df = pd.DataFrame({"total": [100.0, 110.0]})
        assert calculate_performance_metrics(df)["Total_Return"] == pytest.approx(10.0)
