"""Performance metrics. Shared by the backtester and the live bot."""
import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252

# Regular-session bars per trading day, by yfinance interval string.
BARS_PER_DAY = {
    '1m': 390, '2m': 195, '5m': 78, '15m': 26, '30m': 13,
    '60m': 6.5, '90m': 4.333333333333333, '1h': 6.5,
    '1d': 1, '5d': 0.2, '1wk': 0.2, '1mo': 1 / 21, '3mo': 1 / 63,
}


def bars_per_year(interval='1d'):
    """Annualization factor for a given bar interval.

    Sharpe scales with sqrt(observations per year), so using 252 on 5-minute
    bars understates the factor by ~sqrt(78).
    """
    if interval not in BARS_PER_DAY:
        raise ValueError(
            f"Unknown interval {interval!r}; known: {sorted(BARS_PER_DAY)}"
        )
    return BARS_PER_DAY[interval] * TRADING_DAYS_PER_YEAR


def calculate_performance_metrics(portfolio_values, periods_per_year=None,
                                  interval=None):
    """Calculate performance metrics for a portfolio.

    Pass `interval` (e.g. '5m') to annualize correctly for intraday bars, or
    `periods_per_year` directly. Defaults to daily bars.

    CAGR extrapolates the observed window out to a full year, so over a short
    live window it is not a meaningful number - read Total_Return instead.
    """
    if periods_per_year is None:
        periods_per_year = (bars_per_year(interval) if interval
                            else TRADING_DAYS_PER_YEAR)

    # Ensure we have a Series, not DataFrame
    if isinstance(portfolio_values, pd.DataFrame):
        portfolio_values = portfolio_values.iloc[:, 0]

    returns = portfolio_values.pct_change().dropna()

    start_value = portfolio_values.iloc[0]
    end_value = portfolio_values.iloc[-1]
    total_return = (end_value / start_value - 1) * 100

    # CAGR (Compound Annual Growth Rate)
    num_years = len(portfolio_values) / periods_per_year
    cagr = (end_value / start_value) ** (1 / num_years) - 1

    # Sharpe Ratio (assuming risk-free rate of 0 for simplicity)
    mean_return = returns.mean()
    std_dev = returns.std()

    if pd.notna(std_dev) and std_dev > 0:
        sharpe_ratio = mean_return / std_dev * np.sqrt(periods_per_year)
    else:
        sharpe_ratio = 0

    # Maximum Drawdown
    cumulative = portfolio_values / portfolio_values.cummax()
    max_drawdown = (cumulative.min() - 1) * 100

    return {
        'Total_Return': total_return,
        'CAGR': cagr * 100,  # Convert to percentage
        'Sharpe_Ratio': sharpe_ratio,
        'Max_Drawdown': max_drawdown,
        'Periods_Per_Year': periods_per_year,
    }
