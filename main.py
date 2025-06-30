from strategy import *
from backtest import backtest_strategy, plot_portfolio
import yfinance as yf

def main():
    ticker = 'AMD'
    start_date = '2022-03-01'
    end_date = '2023-06-01'
    short_window = 20
    long_window = 50
    initial_capital = 10000.0
    window = 20
    treshold = 1.0

    try:
        # df, signals = generate_moving_avg_corssorver_strat(ticker, start_date, end_date, short_window, long_window)
        df, signals =  generate_mean_reversal_strat(ticker, start_date, end_date, window, treshold)

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
