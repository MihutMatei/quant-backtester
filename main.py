# Easy configuration options - change these to experiment with different timeframes
TICKER = 'PLTR'
PERIOD = "60d"      # Options: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
INTERVAL = "5m"     # Options: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
STRATEGY = 1  # Options: 1 == "mean_reversion", 2=="moving_average"

# Plotting options
GENERATE_ZOOM_PLOTS = False      # Generate 7d and 14d zoom plots
GENERATE_CUSTOM_RANGE = False    # Generate custom day range plots
AUTO_SUGGEST_RANGES = False     # Automatically suggest optimal ranges based on data length

# Custom day ranges to plot (start_day, end_day)
# Days are counted from the beginning of the data period (0-indexed)
# Example: (21, 34) means plot from day 21 to day 34 of the dataset
# Set to empty list [] to use AUTO_SUGGEST_RANGES when AUTO_SUGGEST_RANGES=True
CUSTOM_RANGES = [               
    (21, 34),   # Day 21 to Day 34 - your requested range
    (10, 25),   # Day 10 to Day 25 - early period focus
    (40, 55),   # Day 40 to Day 55 - later period analysis
    (5, 15),    # Day 5 to Day 15 - very early period
]

# Hour-based custom ranges (useful for high-frequency data like 1m, 5m)
# Format: (start_hours, end_hours) from beginning of dataset
# Example: (2, 4) means plot from hour 2 to hour 4 of the dataset
CUSTOM_HOUR_RANGES = [
    (2, 4),    # First 2 hours of trading
    (8, 12),   # Mid-day trading (4 hours)
    (20, 24),  # End-of-day trading
]

GENERATE_HOUR_RANGES = False  # Enable/disable hour-based custom ranges (best for 1m/2m data)

# Note: 1m and 2m data limited to 7 days, 5m-90m data limited to 60 days

from strategy import *
from backtest import backtest_strategy, plot_portfolio, analyze_trading_patterns, suggest_custom_ranges
import yfinance as yf

def main():
    ticker = TICKER
    
    # Period-based approach configuration (adjusted for 5m data limitations)
    period = PERIOD       # Last 30 days (5m data only available for last 60 days)
    interval = INTERVAL      # 5-minute data
    
    short_window = 7    # Adjusted for 5m intervals (1 hour)
    long_window = 24     # Adjusted for 5m intervals (2 hours)
    initial_capital = 10000.0
    window = 75          # Adjusted for higher frequency
    threshold = 1.0

    try:
        # Dynamically select strategy based on STRATEGY configuration
        if STRATEGY == 1:
            df, signals = generate_mean_reversal_strat(
                ticker, period=period, interval=interval,
                window=window, threshold=threshold
            )
        elif STRATEGY == 2:
            df, signals = generate_moving_avg_corssorver_strat(
                ticker, period=period, interval=interval,
                short_window=short_window, long_window=long_window
            )
        else:
            raise ValueError(f"Unknown strategy: {STRATEGY}. Use 'mean_reversion' or 'moving_average'")

    except ValueError as e:
        print(e)
        return

    # Download benchmark data with same timeframe
    benchmark = yf.download(ticker, period=period, interval=interval, auto_adjust=True)
    if benchmark.empty:
        print("Could not download benchmark data.")
        return

    portfolio, transactions = backtest_strategy(df, signals, initial_capital)
    
    # Generate multiple plots for better visualization
    # Full period plot
    plot_portfolio(portfolio, benchmark, initial_capital, f"{ticker}_{interval}_{STRATEGY}", transactions)
    
    # Zoomed plots for detailed analysis (if enabled)
    if GENERATE_ZOOM_PLOTS:
        plot_portfolio(portfolio, benchmark, initial_capital, f"{ticker}_{interval}_{STRATEGY}", transactions, zoom_days=7)   # Last week
        plot_portfolio(portfolio, benchmark, initial_capital, f"{ticker}_{interval}_{STRATEGY}", transactions, zoom_days=14)  # Last 2 weeks
    
    # Custom range plots (if enabled)
    if GENERATE_CUSTOM_RANGE:
        ranges_to_plot = CUSTOM_RANGES
        
        # Auto-suggest ranges if enabled and no custom ranges provided
        if AUTO_SUGGEST_RANGES and not CUSTOM_RANGES:
            ranges_to_plot = suggest_custom_ranges(portfolio)
        
        if ranges_to_plot:
            # print(f"\nGenerating {len(ranges_to_plot)} custom range plots...")
            for start_day, end_day in ranges_to_plot:
                plot_portfolio(portfolio, benchmark, initial_capital, f"{ticker}_{interval}_{STRATEGY}", 
                             transactions, custom_start_day=start_day, custom_end_day=end_day)
                # print(f"  ✓ Custom range plot: Day {start_day} to Day {end_day}")
    
    # Hour-based custom range plots (if enabled)
    if GENERATE_HOUR_RANGES and CUSTOM_HOUR_RANGES:
        # print(f"\nGenerating {len(CUSTOM_HOUR_RANGES)} hour-based custom range plots...")
        for start_hour, end_hour in CUSTOM_HOUR_RANGES:
            plot_portfolio(portfolio, benchmark, initial_capital, f"{ticker}_{interval}_{STRATEGY}", 
                         transactions, custom_start_hour=start_hour, custom_end_hour=end_hour)
            # print(f"  ✓ Hour range plot: Hour {start_hour} to Hour {end_hour}")
    
    # Print summary of transactions
    if transactions:
        print(f"\nTransaction Summary:")
        print(f"Strategy: {STRATEGY}")
        print(f"Total transactions: {len(transactions)}")
        print(f"Final return: {transactions[-1]['Return']:.2f}%")
        print(f"Timeframe: {period} with {interval} intervals")
        
        # Advanced trading analysis
        analyze_trading_patterns(portfolio, transactions, ticker)
    
    # Summary of generated plots
    # print(f"\n📊 Plot Generation Summary:")
    # print(f"  ✓ Full period plot generated")
    # if GENERATE_ZOOM_PLOTS:
        # print(f"  ✓ Zoom plots generated (7d, 14d)")
    
    # if GENERATE_CUSTOM_RANGE:
        # ranges_to_plot = CUSTOM_RANGES
        # if AUTO_SUGGEST_RANGES and not CUSTOM_RANGES:
            # ranges_to_plot = suggest_custom_ranges(portfolio)
        
        # if ranges_to_plot:
            # print(f"  ✓ {len(ranges_to_plot)} custom range plots generated")
            # for start_day, end_day in ranges_to_plot:
                # print(f"    - Day {start_day} to Day {end_day}")
    
    # if GENERATE_HOUR_RANGES and CUSTOM_HOUR_RANGES:
        # print(f"  ✓ {len(CUSTOM_HOUR_RANGES)} hour-based range plots generated")
        # for start_hour, end_hour in CUSTOM_HOUR_RANGES:
            # print(f"    - Hour {start_hour} to Hour {end_hour}")
    
    # custom_count = (len(ranges_to_plot) if GENERATE_CUSTOM_RANGE and 'ranges_to_plot' in locals() and ranges_to_plot else 0)
    # hour_count = (len(CUSTOM_HOUR_RANGES) if GENERATE_HOUR_RANGES and CUSTOM_HOUR_RANGES else 0)
    # total_plots = 1 + (2 if GENERATE_ZOOM_PLOTS else 0) + custom_count + hour_count
    # print(f"  📈 Total plots generated: {total_plots}")

if __name__ == "__main__":
    main()
