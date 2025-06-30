# Easy configuration options - change these to experiment with different timeframes
TICKER = 'AMD'
PERIOD = "30d"      # Options: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
INTERVAL = "5m"     # Options: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
STRATEGY = "mean_reversion"  # Options: "mean_reversion", "moving_average"

# Note: 1m and 2m data limited to 7 days, 5m-90m data limited to 60 days

from strategy import *
from backtest import backtest_strategy, plot_portfolio
import yfinance as yf

def main():
    ticker = TICKER
    
    # Period-based approach configuration (adjusted for 5m data limitations)
    period = PERIOD       # Last 30 days (5m data only available for last 60 days)
    interval = INTERVAL      # 5-minute data
    
    short_window = 12    # Adjusted for 5m intervals (1 hour)
    long_window = 24     # Adjusted for 5m intervals (2 hours)
    initial_capital = 10000.0
    window = 50          # Adjusted for higher frequency
    threshold = 1.0

    try:
        # Period-based approach with 5-minute intervals
        df, signals = generate_mean_reversal_strat(
            ticker, period=period, interval=interval,
            window=window, threshold=threshold
        )

    except ValueError as e:
        print(e)
        return

    # Download benchmark data with same timeframe
    benchmark = yf.download(ticker, period=period, interval=interval, auto_adjust=True)
    if benchmark.empty:
        print("Could not download benchmark data.")
        return

    portfolio, transactions = backtest_strategy(df, signals, initial_capital)
    plot_portfolio(portfolio, benchmark, initial_capital, f"{ticker}_{interval}")
    
    # Print summary of transactions
    if transactions:
        print(f"\nTransaction Summary:")
        print(f"Total transactions: {len(transactions)}")
        print(f"First transaction: {transactions[0]['Date'].strftime('%Y-%m-%d %H:%M')} - {transactions[0]['Action']}")
        print(f"Last transaction: {transactions[-1]['Date'].strftime('%Y-%m-%d %H:%M')} - {transactions[-1]['Action']}")
        print(f"Final return: {transactions[-1]['Return']:.2f}%")
        print(f"Data points: {len(df)}")
        print(f"Timeframe: {period} with {interval} intervals")

if __name__ == "__main__":
    main()
