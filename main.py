from strategy import generate_strategy
from backtest import backtest_strategy, plot_portfolio
import yfinance as yf

def main():
    ticker = 'AMD'
    start_date = '2023-01-01'
    end_date = '2023-07-07'
    short_window = 6
    long_window = 10
    initial_capital = 10000.0

    try:
        df, signals = generate_strategy(ticker, start_date, end_date, short_window, long_window)
    except ValueError as e:
        print(e)
        return

    # Download SPY for benchmark
    benchmark = yf.download('AMD', start=start_date, end=end_date, auto_adjust=True)
    if benchmark.empty:
        print("Could not download benchmark (SPY) data.")
        return

    portfolio = backtest_strategy(df, signals, initial_capital)
    plot_portfolio(portfolio, benchmark, initial_capital, ticker)

if __name__ == "__main__":
    main()
