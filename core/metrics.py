"""Performance metrics. Shared by the backtester and the live bot."""
import pandas as pd
import numpy as np


def calculate_performance_metrics(portfolio_values, trading_days_per_year=252):
    """Calculate performance metrics for a portfolio"""
    # Ensure we have a Series, not DataFrame
    if isinstance(portfolio_values, pd.DataFrame):
        portfolio_values = portfolio_values.iloc[:, 0]
    
    returns = portfolio_values.pct_change().dropna()
    
    # CAGR (Compound Annual Growth Rate)
    start_value = portfolio_values.iloc[0]
    end_value = portfolio_values.iloc[-1]
    num_years = len(portfolio_values) / trading_days_per_year
    cagr = (end_value / start_value) ** (1 / num_years) - 1
    
    # Sharpe Ratio (assuming risk-free rate of 0 for simplicity)
    mean_return = returns.mean()
    std_dev = returns.std()
    
    if pd.notna(std_dev) and std_dev > 0:
        sharpe_ratio = mean_return / std_dev * np.sqrt(trading_days_per_year)
    else:
        sharpe_ratio = 0
    
    # Maximum Drawdown
    cumulative = portfolio_values / portfolio_values.cummax()
    max_drawdown = (cumulative.min() - 1) * 100
    
    return {
        'CAGR': cagr * 100,  # Convert to percentage
        'Sharpe_Ratio': sharpe_ratio,
        'Max_Drawdown': max_drawdown
    }
