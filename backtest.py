import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def backtest_strategy(df, signals, initial_capital=10000.0):
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
                    shares = cash / current_price
                    cash = 0
            elif current_signal == -1.0 and prev_signal != -1.0:  # Sell signal
                if shares > 0:
                    cash = shares * current_price
                    shares = 0
        
        # Update portfolio values
        portfolio.loc[date, 'Shares'] = float(shares)
        portfolio.loc[date, 'Cash'] = float(cash)
        portfolio.loc[date, 'Holdings'] = float(shares * current_price)
        portfolio.loc[date, 'Total'] = float(cash + (shares * current_price))
    
    portfolio['Returns'] = portfolio['Total'].pct_change()
    return portfolio

def plot_portfolio(portfolio, benchmark_df, initial_capital, ticker='Strategy'):

    
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
    benchmark = benchmark_df['Close'].reindex(portfolio.index).ffill()
    normalized_benchmark = benchmark / benchmark.iloc[0] * initial_capital
    ax.plot(normalized_benchmark.index, normalized_benchmark.values, label=' Buy & Hold', color='orange', linewidth=3)
    print("Orange SPY line plotted successfully")
    
    ax.set_title(f'{ticker} Moving Average Strategy vs Buy & Hold', fontsize=16)
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Portfolio Value ($)', fontsize=12)
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig("portfolio_vs_spy.png", dpi=300, bbox_inches='tight')
    print("Plot saved as 'portfolio_vs_spy.png'")
