# main.py

# ========== Configuration ==========

# General
TICKER     = 'XEL'
PERIOD     = "2y"      # 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
INTERVAL   = "1d"       # 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
INITIAL_CAPITAL = 10000.0

# Strategy selector
STRATEGY   = 1          # 1='mean_reversion', 2='moving_average', 3='williams_%R'

# Mean‐Reversion params
MR_WINDOW    = 27       # look-back window (in bars)
MR_THRESHOLD = 1.0      # z-score entry/exit threshold

# Moving‐Average crossover params
MA_SHORT_WINDOW = 5     # in bars
MA_LONG_WINDOW  = 20    # in bars

# Williams %R strategy params
WR_PERIOD             = 14     # look-back window
WR_LONG_ENTRY_THRESH  = -80.0  # enter long when %R ≤ this
WR_LONG_EXIT_THRESH   = -20.0  # exit long when %R ≥ this
WR_SHORT_ENTRY_THRESH = -20.0  # enter short when %R ≥ this
WR_SHORT_EXIT_THRESH  = -80.0  # exit short when %R ≤ this

# Plotting options
GENERATE_ZOOM_PLOTS   = False   # 7d & 14d zooms
GENERATE_CUSTOM_RANGE = False   # custom day-range plots
AUTO_SUGGEST_RANGES   = False   # auto-suggest custom ranges
CUSTOM_RANGES         = [(21, 34), (10, 25), (40, 55), (5, 15)]
GENERATE_HOUR_RANGES  = False   # hour-based custom ranges
CUSTOM_HOUR_RANGES    = [(2, 4), (8, 12), (20, 24)]

# ====================================

from strategy import *
from backtest import *
import yfinance as yf


def main():
    # 1) Select and generate strategy
    try:
        if STRATEGY == 1:
            df, signals = generate_mean_reversal_strat(
                TICKER,
                period=PERIOD,
                interval=INTERVAL,
                window=MR_WINDOW,
                threshold=MR_THRESHOLD
            )

        elif STRATEGY == 2:
            df, signals = generate_moving_avg_crossover_strat(
                TICKER,
                period=PERIOD,
                interval=INTERVAL,
                short_window=MA_SHORT_WINDOW,
                long_window=MA_LONG_WINDOW
            )

        elif STRATEGY == 3:
            df, signals = generate_williamsr_strat(
                TICKER,
                period=PERIOD,
                interval=INTERVAL,
                wr_period=WR_PERIOD,
                long_entry_thresh=WR_LONG_ENTRY_THRESH,
                long_exit_thresh=WR_LONG_EXIT_THRESH,
                short_entry_thresh=WR_SHORT_ENTRY_THRESH,
                short_exit_thresh=WR_SHORT_EXIT_THRESH
            )

        else:
            raise ValueError(
                f"Unknown strategy: {STRATEGY}. "
                "Use 1='mean_reversion', 2='moving_average', or 3='williams_%R'"
            )

    except ValueError as e:
        print(e)
        return

    # 2) Download benchmark data
    benchmark = yf.download(
        TICKER,
        period=PERIOD,
        interval=INTERVAL,
        auto_adjust=True
    )
    if benchmark.empty:
        print("Could not download benchmark data.")
        return

    # 3) Backtest
    portfolio, transactions = backtest_strategy(
        df, signals, INITIAL_CAPITAL
    )

    # 4) Full-period plot
    plot_portfolio(
        portfolio,
        benchmark,
        INITIAL_CAPITAL,
        f"{TICKER}_{INTERVAL}_{STRATEGY}",
        transactions
    )

    # 5) Optional zoom & custom plots
    if GENERATE_ZOOM_PLOTS:
        plot_portfolio(portfolio, benchmark, INITIAL_CAPITAL,
                       f"{TICKER}_{INTERVAL}_{STRATEGY}", transactions,
                       zoom_days=7)
        plot_portfolio(portfolio, benchmark, INITIAL_CAPITAL,
                       f"{TICKER}_{INTERVAL}_{STRATEGY}", transactions,
                       zoom_days=14)

    if GENERATE_CUSTOM_RANGE:
        ranges = CUSTOM_RANGES or suggest_custom_ranges(portfolio) if AUTO_SUGGEST_RANGES else CUSTOM_RANGES
        for start_day, end_day in ranges:
            plot_portfolio(portfolio, benchmark, INITIAL_CAPITAL,
                           f"{TICKER}_{INTERVAL}_{STRATEGY}", transactions,
                           custom_start_day=start_day,
                           custom_end_day=end_day)

    if GENERATE_HOUR_RANGES:
        for start_hour, end_hour in CUSTOM_HOUR_RANGES:
            plot_portfolio(portfolio, benchmark, INITIAL_CAPITAL,
                           f"{TICKER}_{INTERVAL}_{STRATEGY}", transactions,
                           custom_start_hour=start_hour,
                           custom_end_hour=end_hour)

    # 6) Transaction summary & analysis
    if transactions:
        print("\nTransaction Summary:")
        print(f"Strategy: {STRATEGY}")
        print(f"Total transactions: {len(transactions)}")
        print(f"Final return: {transactions[-1]['Return']:.2f}%")
        print(f"Timeframe: {PERIOD} @ {INTERVAL}\n")
        analyze_trading_patterns(portfolio, transactions, TICKER)


if __name__ == "__main__":
    main()
