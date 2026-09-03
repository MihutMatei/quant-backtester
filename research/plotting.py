"""Portfolio plots. Research only - pulls in matplotlib."""
import pandas as pd
import matplotlib.pyplot as plt

from core.metrics import calculate_performance_metrics


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
