import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

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

def backtest_strategy(df, signals, initial_capital=10000.0, log_transactions=True):
    price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
    price_series = df[price_col]
    if isinstance(price_series, pd.DataFrame):
        price_series = price_series.iloc[:, 0]
    
    # Align price series with signals
    price_series = price_series.reindex(signals.index).ffill()
    
    # Create portfolio dataframe
    portfolio = pd.DataFrame(index=signals.index)
    portfolio['Position'] = signals['signal']
    portfolio['Price'] = price_series
    
    # Calculate shares owned
    portfolio['Shares'] = 0.0
    portfolio['Cash'] = float(initial_capital)
    portfolio['Total'] = float(initial_capital)
    
    # Calculate actual portfolio values with proper trading logic
    shares = 0.0
    cash = initial_capital
    transactions = []  # Store all transactions
    
    for i, (date, row) in enumerate(portfolio.iterrows()):
        if i == 0:
            continue
            
        prev_signal = portfolio['Position'].iloc[i-1]
        current_signal = row['Position']
        current_price = row['Price']
        
        # Check for signal change (buy/sell)
        if current_signal != prev_signal:
            if current_signal == 1.0 and prev_signal != 1.0:  # Buy signal
                if cash > 0:
                    new_shares = cash / current_price
                    equity = cash + (shares * current_price)
                    if log_transactions:
                        transactions.append({
                            'Date': date,
                            'Action': 'BUY',
                            'Price': current_price,
                            'Shares': new_shares,
                            'Return': 0.0 if not transactions else ((equity / initial_capital) - 1) * 100,
                            'Equity': equity
                        })
                    shares = new_shares
                    cash = 0
            elif current_signal == -1.0 and prev_signal != -1.0:  # Sell signal
                if shares > 0:
                    new_cash = shares * current_price
                    equity = new_cash
                    if log_transactions:
                        transactions.append({
                            'Date': date,
                            'Action': 'SELL',
                            'Price': current_price,
                            'Shares': shares,
                            'Return': ((equity / initial_capital) - 1) * 100,
                            'Equity': equity
                        })
                    cash = new_cash
                    shares = 0
        
        # Update portfolio values
        portfolio.loc[date, 'Shares'] = float(shares)
        portfolio.loc[date, 'Cash'] = float(cash)
        portfolio.loc[date, 'Holdings'] = float(shares * current_price)
        portfolio.loc[date, 'Total'] = float(cash + (shares * current_price))
    
    portfolio['Returns'] = portfolio['Total'].pct_change()
    
    # Log transactions to file if enabled
    if log_transactions and transactions:
        transactions_df = pd.DataFrame(transactions)
        transactions_df.to_csv('transactions.txt', index=False, 
                              date_format='%Y-%m-%d',
                              float_format='%.2f')
        print(f"Logged {len(transactions)} transactions to transactions.txt")
    
    return portfolio, transactions

def plot_portfolio(portfolio, benchmark_df, initial_capital, ticker='Strategy'):
    # Calculate performance metrics for strategy
    strategy_metrics = calculate_performance_metrics(portfolio['Total'])
    
    # Calculate performance metrics for buy & hold benchmark
    benchmark = benchmark_df['Close'].reindex(portfolio.index).ffill()
    normalized_benchmark = benchmark / benchmark.iloc[0] * initial_capital
    benchmark_metrics = calculate_performance_metrics(normalized_benchmark)

    
    # Clear any existing plots and create new figure
    plt.close('all')
    fig, ax = plt.subplots(figsize=(12,8))

    # Debug: Print portfolio info
    print(f"Portfolio Total min: {portfolio['Total'].min()}")
    print(f"Portfolio Total max: {portfolio['Total'].max()}")
    print(f"Portfolio Total first few values:\n{portfolio['Total'].head()}")
    print(f"Portfolio Total has NaN: {portfolio['Total'].isna().any()}")

    # Plot your strategy
    strategy_total = portfolio['Total'].dropna()
    print(f"Strategy data points: {len(strategy_total)}")
    print(f"Strategy min: {strategy_total.min()}, max: {strategy_total.max()}")
    
    if not strategy_total.empty:
        # Use the axes directly
        ax.plot(strategy_total.index, strategy_total.values, label=f'{ticker} Strategy', color='blue', linewidth=3)
        print("Blue line plotted successfully")
    else:
        print("Warning: Strategy portfolio is empty or all NaN")
    
    # Add SPY benchmark back
    ax.plot(normalized_benchmark.index, normalized_benchmark.values, label='Buy & Hold', color='orange', linewidth=3)
    print("Orange Buy & Hold line plotted successfully")
    
    # Create performance metrics text
    metrics_text = (
        f"Strategy Performance:\n"
        f"CAGR: {strategy_metrics['CAGR']:.2f}%\n"
        f"Sharpe Ratio: {strategy_metrics['Sharpe_Ratio']:.2f}\n"
        f"Max Drawdown: {strategy_metrics['Max_Drawdown']:.2f}%\n\n"
        f"Buy & Hold Performance:\n"
        f"CAGR: {benchmark_metrics['CAGR']:.2f}%\n"
        f"Sharpe Ratio: {benchmark_metrics['Sharpe_Ratio']:.2f}\n"
        f"Max Drawdown: {benchmark_metrics['Max_Drawdown']:.2f}%"
    )
    
    # Add text box with metrics
    ax.text(0.02, 0.98, metrics_text, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    ax.set_title(f'{ticker} Moving Average Strategy vs Buy & Hold', fontsize=16)
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Portfolio Value ($)', fontsize=12)
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig("portfolio_vs_spy.png", dpi=300, bbox_inches='tight')
    print("Plot saved as 'portfolio_vs_spy.png'")
