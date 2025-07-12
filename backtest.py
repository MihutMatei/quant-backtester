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

def backtest_strategy(df, signals, initial_capital=10000.0, log_transactions=True,
                     stop_loss_pct=None, take_profit_pct=None, 
                     use_trailing_stop=False, trailing_stop_pct=None,
                     enable_shorting=True, dedup_window_minutes=5):
    """
    Enhanced backtest with stop-loss, take-profit, and shorting functionality
    
    Args:
        df: Price data DataFrame
        signals: Trading signals DataFrame
        initial_capital: Starting capital
        log_transactions: Whether to log transactions
        stop_loss_pct: Stop loss percentage (e.g., 0.05 for 5%)
        take_profit_pct: Take profit percentage (e.g., 0.10 for 10%)
        use_trailing_stop: Enable trailing stop loss
        trailing_stop_pct: Trailing stop percentage
        enable_shorting: Enable short selling functionality
        dedup_window_minutes: Time window in minutes to prevent duplicate transactions
    """
    cash = initial_capital
    shares = 0.0  # Positive for long positions, negative for short positions
    portfolio = pd.DataFrame(index=df.index)
    portfolio['cash'] = cash
    portfolio['shares'] = shares
    portfolio['total'] = cash
    
    transactions = []
    
    # Deduplication tracking - prevent duplicate transactions within time window
    last_transaction_time = None
    last_transaction_type = None
    dedup_window = pd.Timedelta(minutes=dedup_window_minutes)
    
    # Risk management tracking
    position_entry_price = None
    position_entry_date = None
    trailing_stop_price = None
    position_type = None  # 'long' or 'short'
    
    price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
    
    def should_allow_transaction(action_type, current_time):
        """Check if a transaction should be allowed based on deduplication window"""
        nonlocal last_transaction_time, last_transaction_type
        
        # Always allow risk management exits (stop loss, take profit, trailing stop)
        if any(risk_action in action_type for risk_action in ['STOP_LOSS', 'TAKE_PROFIT', 'TRAILING_STOP']):
            return True
            
        # Allow transaction if no previous transaction or enough time has passed
        if last_transaction_time is None or (current_time - last_transaction_time) >= dedup_window:
            return True
            
        # Block ANY transaction type if within the deduplication window
        return False
    
    def record_transaction(action_type, current_time):
        """Record the transaction time and type for deduplication"""
        nonlocal last_transaction_time, last_transaction_type
        last_transaction_time = current_time
        last_transaction_type = action_type

    for i, (date, row) in enumerate(df.iterrows()):
        current_price = row[price_col]
        current_signal = signals.iloc[i]['signal']
        prev_signal = signals.iloc[i-1]['signal'] if i > 0 else 0.0
        
        # Risk management checks for existing positions
        if shares != 0 and position_entry_price is not None:
            should_exit = False
            exit_reason = ""
            exit_price = current_price
            
            if position_type == 'long':
                # Long position risk management
                position_return = (current_price - position_entry_price) / position_entry_price
                
                # Stop loss check
                if stop_loss_pct and position_return <= -stop_loss_pct:
                    should_exit = True
                    exit_reason = "STOP_LOSS"
                    exit_price = position_entry_price * (1 - stop_loss_pct)
                
                # Take profit check
                elif take_profit_pct and position_return >= take_profit_pct:
                    should_exit = True
                    exit_reason = "TAKE_PROFIT"
                    exit_price = position_entry_price * (1 + take_profit_pct)
                
                # Trailing stop logic for long positions
                elif use_trailing_stop and trailing_stop_pct:
                    if trailing_stop_price is None:
                        trailing_stop_price = current_price * (1 - trailing_stop_pct)
                    else:
                        # Update trailing stop if price moved favorably (upward)
                        new_trailing_stop = current_price * (1 - trailing_stop_pct)
                        if new_trailing_stop > trailing_stop_price:
                            trailing_stop_price = new_trailing_stop
                    
                    # Check if trailing stop was hit
                    if current_price <= trailing_stop_price:
                        should_exit = True
                        exit_reason = "TRAILING_STOP"
                        exit_price = trailing_stop_price
                        
            elif position_type == 'short':
                # Short position risk management (inverse logic)
                position_return = (position_entry_price - current_price) / position_entry_price
                
                # Stop loss check for short (price goes up)
                if stop_loss_pct and position_return <= -stop_loss_pct:
                    should_exit = True
                    exit_reason = "STOP_LOSS"
                    exit_price = position_entry_price * (1 + stop_loss_pct)
                
                # Take profit check for short (price goes down)
                elif take_profit_pct and position_return >= take_profit_pct:
                    should_exit = True
                    exit_reason = "TAKE_PROFIT"
                    exit_price = position_entry_price * (1 - take_profit_pct)
                
                # Trailing stop logic for short positions
                elif use_trailing_stop and trailing_stop_pct:
                    if trailing_stop_price is None:
                        trailing_stop_price = current_price * (1 + trailing_stop_pct)
                    else:
                        # Update trailing stop if price moved favorably (downward)
                        new_trailing_stop = current_price * (1 + trailing_stop_pct)
                        if new_trailing_stop < trailing_stop_price:
                            trailing_stop_price = new_trailing_stop
                    
                    # Check if trailing stop was hit
                    if current_price >= trailing_stop_price:
                        should_exit = True
                        exit_reason = "TRAILING_STOP"
                        exit_price = trailing_stop_price
            
            # Execute risk management exit
            if should_exit:
                if position_type == 'long':
                    pnl = (exit_price - position_entry_price) * shares
                    cash += shares * exit_price
                elif position_type == 'short':
                    pnl = (position_entry_price - exit_price) * abs(shares)
                    cash += pnl  # Add the PnL to cash
                
                pnl_pct = pnl / (position_entry_price * abs(shares)) * 100
                
                if log_transactions:
                    action = f"{exit_reason}_{position_type.upper()}"
                    transactions.append({
                        'Date': date,
                        'Action': action,
                        'Price': exit_price,
                        'Shares': abs(shares),
                        'PnL': pnl,
                        'Return': pnl_pct,
                        'Portfolio_Value': cash
                    })
                    record_transaction(action, date)
                
                shares = 0.0
                position_entry_price = None
                position_entry_date = None
                trailing_stop_price = None
                position_type = None
        
        # Regular signal-based trading
        if current_signal != prev_signal:
            if current_signal == 1.0 and shares == 0:  # Buy signal when not in position
                if cash > 0 and should_allow_transaction('BUY', date):
                    new_shares = cash / current_price
                    
                    shares = new_shares
                    cash = 0.0
                    position_entry_price = current_price
                    position_entry_date = date
                    trailing_stop_price = None
                    position_type = 'long'
                    
                    if log_transactions:
                        transactions.append({
                            'Date': date,
                            'Action': 'BUY',
                            'Price': current_price,
                            'Shares': new_shares,
                            'PnL': 0.0,
                            'Return': 0.0,
                            'Portfolio_Value': cash + shares * current_price
                        })
                        record_transaction('BUY', date)
            
            elif current_signal == -1.0 and shares > 0:  # Sell signal when in long position
                if should_allow_transaction('SELL', date):
                    pnl = (current_price - position_entry_price) * shares
                    pnl_pct = (current_price - position_entry_price) / position_entry_price * 100
                    
                    cash = shares * current_price
                    
                    if log_transactions:
                        transactions.append({
                            'Date': date,
                            'Action': 'SELL',
                            'Price': current_price,
                            'Shares': shares,
                            'PnL': pnl,
                            'Return': pnl_pct,
                            'Portfolio_Value': cash
                        })
                        record_transaction('SELL', date)
                    
                    shares = 0.0
                    position_entry_price = None
                    position_entry_date = None
                    trailing_stop_price = None
                    position_type = None
                    
                    # If shorting is enabled, enter short position immediately
                    if enable_shorting and cash > 0 and should_allow_transaction('SHORT', date):
                        short_shares = cash / current_price
                        
                        shares = -short_shares  # Negative for short position
                        # For short positions, we keep the cash from the original sale
                        # and track the short position separately
                        position_entry_price = current_price
                        position_entry_date = date
                        trailing_stop_price = None
                        position_type = 'short'
                        
                        if log_transactions:
                            transactions.append({
                                'Date': date,
                                'Action': 'SHORT',
                                'Price': current_price,
                                'Shares': short_shares,
                                'PnL': 0.0,
                                'Return': 0.0,
                                'Portfolio_Value': cash
                            })
                            record_transaction('SHORT', date)
            
            elif current_signal == -1.0 and shares == 0 and enable_shorting:  # Short signal when not in position
                if cash > 0 and should_allow_transaction('SHORT', date):
                    short_shares = cash / current_price
                    
                    shares = -short_shares  # Negative for short position
                    # For short positions, we keep the original cash
                    position_entry_price = current_price
                    position_entry_date = date
                    trailing_stop_price = None
                    position_type = 'short'
                    
                    if log_transactions:
                        transactions.append({
                            'Date': date,
                            'Action': 'SHORT',
                            'Price': current_price,
                            'Shares': short_shares,
                            'PnL': 0.0,
                            'Return': 0.0,
                            'Portfolio_Value': cash
                        })
                        record_transaction('SHORT', date)
            
            elif current_signal == 1.0 and shares < 0:  # Buy signal when in short position (cover)
                if should_allow_transaction('COVER', date):
                    pnl = (position_entry_price - current_price) * abs(shares)
                    pnl_pct = (position_entry_price - current_price) / position_entry_price * 100
                    
                    # Cover short position: add PnL to cash
                    cash = cash + pnl
                    
                    if log_transactions:
                        transactions.append({
                            'Date': date,
                            'Action': 'COVER',
                            'Price': current_price,
                            'Shares': abs(shares),
                            'PnL': pnl,
                            'Return': pnl_pct,
                            'Portfolio_Value': cash
                        })
                        record_transaction('COVER', date)
                    
                    shares = 0.0
                    position_entry_price = None
                    position_entry_date = None
                    trailing_stop_price = None
                    position_type = None
                    
                    # Enter long position immediately after covering
                    if cash > 0 and should_allow_transaction('BUY', date):
                        new_shares = cash / current_price
                        
                        shares = new_shares
                        cash = 0.0
                        position_entry_price = current_price
                        position_entry_date = date
                        trailing_stop_price = None
                        position_type = 'long'
                        
                        if log_transactions:
                            transactions.append({
                                'Date': date,
                                'Action': 'BUY',
                                'Price': current_price,
                                'Shares': new_shares,
                                'PnL': 0.0,
                                'Return': 0.0,
                                'Portfolio_Value': shares * current_price
                            })
                            record_transaction('BUY', date)
            
            elif current_signal == 0.0 and shares > 0:  # Exit signal when in long position
                if should_allow_transaction('EXIT_LONG', date):
                    pnl = (current_price - position_entry_price) * shares
                    pnl_pct = (current_price - position_entry_price) / position_entry_price * 100
                    
                    cash = shares * current_price
                    
                    if log_transactions:
                        transactions.append({
                            'Date': date,
                            'Action': 'EXIT_LONG',
                            'Price': current_price,
                            'Shares': shares,
                            'PnL': pnl,
                            'Return': pnl_pct,
                            'Portfolio_Value': cash
                        })
                        record_transaction('EXIT_LONG', date)
                    
                    shares = 0.0
                    position_entry_price = None
                    position_entry_date = None
                    trailing_stop_price = None
                    position_type = None
                
            elif current_signal == 0.0 and shares < 0:  # Exit signal when in short position
                if should_allow_transaction('EXIT_SHORT', date):
                    pnl = (position_entry_price - current_price) * abs(shares)
                    pnl_pct = (position_entry_price - current_price) / position_entry_price * 100
                    
                    if log_transactions:
                        transactions.append({
                            'Date': date,
                            'Action': 'EXIT_SHORT',
                            'Price': current_price,
                            'Shares': abs(shares),
                            'PnL': pnl,
                            'Return': pnl_pct,
                            'Portfolio_Value': cash + pnl
                        })
                        record_transaction('EXIT_SHORT', date)
                    
                    # Update cash to reflect the PnL from the short position
                    cash = cash + pnl
                    shares = 0.0
                    position_entry_price = None
                    position_entry_date = None
                    trailing_stop_price = None
                    position_type = None
                position_type = None
        
        # Update portfolio tracking
        portfolio.loc[date, 'cash'] = float(cash)
        portfolio.loc[date, 'shares'] = float(shares)
        
        # Calculate total portfolio value
        if shares > 0:  # Long position
            portfolio.loc[date, 'total'] = float(cash + shares * current_price)
        elif shares < 0:  # Short position
            # For short positions: portfolio value = cash + unrealized P&L
            # Unrealized P&L = (entry_price - current_price) * number_of_shares
            if position_entry_price is not None:
                unrealized_pnl = (position_entry_price - current_price) * abs(shares)
                portfolio.loc[date, 'total'] = float(cash + unrealized_pnl)
            else:
                portfolio.loc[date, 'total'] = float(cash)
        else:  # No position
            portfolio.loc[date, 'total'] = float(cash)
    
    # Log transactions to file
    if log_transactions and transactions:
        with open('transactions.txt', 'w') as f:
            f.write("Date,Action,Price,Shares,PnL,Return%,Portfolio_Value\n")
            for t in transactions:
                f.write(f"{t['Date']:%Y-%m-%d %H:%M:%S},{t['Action']},{t['Price']:.2f},"
                       f"{t['Shares']:.6f},{t['PnL']:.2f},{t['Return']:.2f},{t['Portfolio_Value']:.2f}\n")
    
    return portfolio, transactions

def plot_portfolio(portfolio, benchmark_df, initial_capital, ticker='Strategy', transactions=None, zoom_days=None, custom_start_day=None, custom_end_day=None, custom_start_hour=None, custom_end_hour=None):
    # Calculate performance metrics for strategy
    strategy_metrics = calculate_performance_metrics(portfolio['total'])
    
    # Calculate performance metrics for buy & hold benchmark
    benchmark = benchmark_df['Close'].reindex(portfolio.index).ffill()
    normalized_benchmark = benchmark / benchmark.iloc[0].item() * initial_capital
    benchmark_metrics = calculate_performance_metrics(normalized_benchmark)

    # Apply zoom or custom date range if specified
    if custom_start_hour is not None and custom_end_hour is not None:
        # Hour-based custom range (e.g., hour 2 to hour 4)
        # Calculate intervals per hour based on the interval setting
        interval_mapping = {
            '1m': 60,   # 60 intervals per hour
            '2m': 30,   # 30 intervals per hour
            '5m': 12,   # 12 intervals per hour
            '15m': 4,   # 4 intervals per hour
            '30m': 2,   # 2 intervals per hour
            '1h': 1,    # 1 interval per hour
        }
        
        # Try to extract interval from ticker string or use default for 5m
        intervals_per_hour = 12  # Default for 5m
        for interval_key in interval_mapping:
            if interval_key in ticker:
                intervals_per_hour = interval_mapping[interval_key]
                break
        
        total_hours = len(portfolio) // intervals_per_hour
        
        # Validate hour ranges
        if custom_start_hour < 0 or custom_end_hour >= total_hours:
            print(f"Warning: Custom hour range ({custom_start_hour}, {custom_end_hour}) exceeds available data (0-{total_hours-1} hours)")
            print(f"Adjusting to valid range...")
            custom_start_hour = max(0, custom_start_hour)
            custom_end_hour = min(total_hours - 1, custom_end_hour)
        
        if custom_start_hour >= custom_end_hour:
            print(f"Error: Invalid range - start hour {custom_start_hour} >= end hour {custom_end_hour}")
            return
        
        # Convert hours to data point indices
        start_idx = custom_start_hour * intervals_per_hour
        end_idx = (custom_end_hour + 1) * intervals_per_hour
        
        portfolio_zoom = portfolio.iloc[start_idx:end_idx]
        benchmark_zoom = normalized_benchmark.iloc[start_idx:end_idx]
        
        # Filter transactions by the actual date range
        start_date = portfolio_zoom.index[0]
        end_date = portfolio_zoom.index[-1]
        transactions_zoom = [t for t in transactions if start_date <= t['Date'] <= end_date] if transactions else []
        
        plot_title = f'{ticker} Strategy vs Buy & Hold (Hour {custom_start_hour} to {custom_end_hour})'
        filename_suffix = f"_custom_h{custom_start_hour}_to_h{custom_end_hour}"
        
        print(f"Custom hour range: Hour {custom_start_hour} to {custom_end_hour} ({start_date.strftime('%m-%d %H:%M')} to {end_date.strftime('%m-%d %H:%M')}) [{intervals_per_hour} intervals/hour]")
        
    elif custom_start_day is not None and custom_end_day is not None:
        # Custom day range (e.g., day 21 to day 34)
        total_days = len(portfolio)
        
        # Validate day ranges
        if custom_start_day < 0 or custom_end_day >= total_days:
            print(f"Warning: Custom range ({custom_start_day}, {custom_end_day}) exceeds available data (0-{total_days-1})")
            print(f"Adjusting to valid range...")
            custom_start_day = max(0, custom_start_day)
            custom_end_day = min(total_days - 1, custom_end_day)
        
        if custom_start_day >= custom_end_day:
            print(f"Error: Invalid range - start day {custom_start_day} >= end day {custom_end_day}")
            return
        
        # Use integer indexing for day-based slicing
        portfolio_zoom = portfolio.iloc[custom_start_day:custom_end_day+1]
        benchmark_zoom = normalized_benchmark.iloc[custom_start_day:custom_end_day+1]
        
        # Filter transactions by the actual date range
        start_date = portfolio_zoom.index[0]
        end_date = portfolio_zoom.index[-1]
        transactions_zoom = [t for t in transactions if start_date <= t['Date'] <= end_date] if transactions else []
        
        plot_title = f'{ticker} Strategy vs Buy & Hold (Day {custom_start_day} to {custom_end_day})'
        filename_suffix = f"_custom_{custom_start_day}_to_{custom_end_day}"
        
        print(f"Custom range: Day {custom_start_day} to {custom_end_day} ({start_date.strftime('%m-%d %H:%M')} to {end_date.strftime('%m-%d %H:%M')})")
        
    elif zoom_days:
        # Regular zoom (last N days)
        end_date = portfolio.index[-1]
        start_date = end_date - pd.Timedelta(days=zoom_days)
        
        # Filter data for zoom
        portfolio_zoom = portfolio[portfolio.index >= start_date]
        benchmark_zoom = normalized_benchmark[normalized_benchmark.index >= start_date]
        transactions_zoom = [t for t in transactions if t['Date'] >= start_date] if transactions else []
        
        plot_title = f'{ticker} Strategy vs Buy & Hold (Last {zoom_days} days)'
        filename_suffix = f"_zoom_{zoom_days}d"
    else:
        # Full period
        portfolio_zoom = portfolio
        benchmark_zoom = normalized_benchmark
        transactions_zoom = transactions if transactions else []
        plot_title = f'{ticker} Strategy vs Buy & Hold (Full Period)'
        filename_suffix = ""

    
    # Clear any existing plots and create new figure
    plt.close('all')
    fig, ax = plt.subplots(figsize=(15,10))  # Larger figure for better visibility

    # Plot your strategy
    strategy_total = portfolio_zoom['total'].dropna()
    # print(f"Strategy data points: {len(strategy_total)}")
    print(f"Strategy min: {strategy_total.min()}, max: {strategy_total.max()}")
    
    if not strategy_total.empty:
        # Use the axes directly
        ax.plot(strategy_total.index, strategy_total.values, label=f'{ticker} Strategy', color='blue', linewidth=2)
    else:
        print("Warning: Strategy portfolio is empty or all NaN")
    
    # Add benchmark line
    ax.plot(benchmark_zoom.index, benchmark_zoom.values, label='Buy & Hold', color='orange', linewidth=2)
    
    # Add transaction markers based on all transaction types - plotted on benchmark line
    if transactions_zoom:
        # Initialize lists for each transaction type
        buy_dates, buy_values = [], []
        sell_dates, sell_values = [], []
        short_dates, short_values = [], []
        cover_dates, cover_values = [], []
        exit_long_dates, exit_long_values = [], []
        exit_short_dates, exit_short_values = [], []
        
        for transaction in transactions_zoom:
            date = transaction['Date']
            action = transaction['Action']
            
            # Get benchmark value at transaction date
            if date in benchmark_zoom.index:
                benchmark_value = benchmark_zoom.loc[date]
                
                # Ensure we have a scalar value, not a Series
                if hasattr(benchmark_value, 'iloc'):
                    benchmark_value = benchmark_value.iloc[0] if len(benchmark_value) > 0 else benchmark_value
                
                benchmark_value = float(benchmark_value)
                
                # Categorize transactions by action type
                if action == 'BUY':
                    buy_dates.append(date)
                    buy_values.append(benchmark_value)
                elif action == 'SELL':
                    sell_dates.append(date)
                    sell_values.append(benchmark_value)
                elif action == 'SHORT':
                    short_dates.append(date)
                    short_values.append(benchmark_value)
                elif action == 'COVER':
                    cover_dates.append(date)
                    cover_values.append(benchmark_value)
                elif action == 'EXIT_LONG':
                    exit_long_dates.append(date)
                    exit_long_values.append(benchmark_value)
                elif action == 'EXIT_SHORT':
                    exit_short_dates.append(date)
                    exit_short_values.append(benchmark_value)
        
        # Plot each transaction type with distinct markers and colors
        marker_size = 100
        edge_width = 1.5
        
        # Entry signals (larger, filled markers)
        if buy_dates:
            ax.scatter(buy_dates, buy_values, color='green', s=marker_size, marker='o', 
                     zorder=6, label='BUY', edgecolors='darkgreen', linewidth=edge_width, alpha=0.9)
        
        if short_dates:
            ax.scatter(short_dates, short_values, color='red', s=marker_size, marker='v', 
                     zorder=6, label='SHORT', edgecolors='darkred', linewidth=edge_width, alpha=0.9)
        
        # Exit signals (smaller, hollow/outlined markers)
        if sell_dates:
            ax.scatter(sell_dates, sell_values, color='white', s=marker_size*0.8, marker='o', 
                     zorder=6, label='SELL', edgecolors='darkred', linewidth=edge_width+0.5, alpha=0.9)
        
        if cover_dates:
            ax.scatter(cover_dates, cover_values, color='white', s=marker_size*0.8, marker='v', 
                     zorder=6, label='COVER', edgecolors='darkgreen', linewidth=edge_width+0.5, alpha=0.9)
        
        if exit_long_dates:
            ax.scatter(exit_long_dates, exit_long_values, color='lightblue', s=marker_size*0.7, marker='s', 
                     zorder=6, label='EXIT_LONG', edgecolors='blue', linewidth=edge_width, alpha=0.9)
        
        if exit_short_dates:
            ax.scatter(exit_short_dates, exit_short_values, color='lightcoral', s=marker_size*0.7, marker='^', 
                     zorder=6, label='EXIT_SHORT', edgecolors='maroon', linewidth=edge_width, alpha=0.9)
    
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
    ax.text(0.02, 0.98, metrics_text, transform=ax.transAxes, fontsize=11,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9))
    
    ax.set_title(plot_title, fontsize=18, fontweight='bold')
    ax.set_xlabel('Date', fontsize=14)
    ax.set_ylabel('Portfolio Value ($)', fontsize=14)
    ax.legend(fontsize=12, loc='best')
    ax.grid(True, alpha=0.3)
    
    # Improve date formatting on x-axis
    import matplotlib.dates as mdates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(portfolio_zoom) // 2000)))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    plt.tight_layout()
    filename = f"portfolio_vs_spy{filename_suffix}.png"
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"Plot saved as '{filename}'")

def analyze_trading_patterns(portfolio, transactions, ticker):
    """Enhanced trading pattern analysis with risk management insights"""
    if not transactions:
        return
    
    print(f"\n=== Enhanced Trading Analysis for {ticker} ===")
    
    # Basic trading stats
    total_days = (transactions[-1]['Date'] - transactions[0]['Date']).days
    avg_trades_per_day = len(transactions) / total_days if total_days > 0 else 0
    
    # Categorize transactions
    buys = [t for t in transactions if t['Action'] == 'BUY']
    sells = [t for t in transactions if t['Action'] in ['SELL', 'EXIT_LONG', 'EXIT_SHORT']]
    shorts = [t for t in transactions if t['Action'] == 'SHORT']
    covers = [t for t in transactions if t['Action'] == 'COVER']
    stop_losses = [t for t in transactions if 'STOP_LOSS' in t['Action']]
    take_profits = [t for t in transactions if 'TAKE_PROFIT' in t['Action']]
    trailing_stops = [t for t in transactions if 'TRAILING_STOP' in t['Action']]
    
    print(f"Trading Frequency: {len(transactions)} transactions over {total_days} days ({avg_trades_per_day:.2f}/day)")
    entries = len(buys) + len(shorts)
    exits = len(sells)
    print(f"Entries: {entries} | Normal Exits: {exits}")
    print(f"Stop Losses: {len(stop_losses)} | Take Profits: {len(take_profits)} | Trailing Stops: {len(trailing_stops)}")
    
    # Risk management effectiveness
    risk_exits = stop_losses + take_profits + trailing_stops
    if risk_exits:
        avg_risk_return = sum(t['Return'] for t in risk_exits) / len(risk_exits)
        print(f"Risk Management Exits: {len(risk_exits)} (avg return: {avg_risk_return:.2f}%)")
    
    # Performance analysis
    if len(transactions) >= 2:
        returns = [t['Return'] for t in transactions if t['Action'] not in ['BUY', 'SHORT']]
        if returns:
            best_return = max(returns)
            worst_return = min(returns)
            avg_return = sum(returns) / len(returns)
            print(f"Best trade: {best_return:.2f}% | Worst trade: {worst_return:.2f}% | Average: {avg_return:.2f}%")
    
    # Recent activity
    recent_cutoff = transactions[-1]['Date'] - pd.Timedelta(days=7)
    recent_trades = [t for t in transactions if t['Date'] >= recent_cutoff]
    print(f"Recent activity (last 7 days): {len(recent_trades)} transactions")

def create_custom_range_plot(portfolio, benchmark, initial_capital, ticker, transactions, start_day, end_day):
    """Create a plot for a custom day range (e.g., day 21 to day 34)"""
    plot_portfolio(portfolio, benchmark, initial_capital, ticker, transactions, 
                  custom_start_day=start_day, custom_end_day=end_day)
    print(f"Custom range plot created: Day {start_day} to Day {end_day}")

def create_custom_zoom_plot(portfolio, benchmark, initial_capital, ticker, transactions, start_days_ago, end_days_ago=0):
    """Create a custom zoom plot for a specific date range"""
    end_date = portfolio.index[-1] - pd.Timedelta(days=end_days_ago)
    start_date = end_date - pd.Timedelta(days=start_days_ago)
    
    # Custom zoom parameters
    zoom_days = start_days_ago - end_days_ago
    plot_portfolio(portfolio, benchmark, initial_capital, f"{ticker}_custom", transactions, zoom_days=zoom_days)
    print(f"Custom zoom plot created: {start_days_ago} to {end_days_ago} days ago")

def suggest_custom_ranges(portfolio, num_ranges=4):
    """Suggest optimal custom day ranges based on data length"""
    total_days = len(portfolio)
    ranges = []
    
    if total_days < 20:
        print(f"Warning: Only {total_days} data points available. Custom ranges may not be meaningful.")
        return [(0, total_days-1)]
    
    # Create evenly distributed ranges
    segment_size = total_days // (num_ranges + 1)
    
    for i in range(num_ranges):
        start = i * segment_size + segment_size // 2
        end = start + min(segment_size, 20)  # Limit range size to 20 days max
        end = min(end, total_days - 1)
        
        if start < end:
            ranges.append((start, end))
    
    print(f"Suggested custom ranges for {total_days} data points:")
    for i, (start, end) in enumerate(ranges):
        print(f"  Range {i+1}: Day {start} to {end} ({end-start+1} days)")
    
    return ranges
