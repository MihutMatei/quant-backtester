# main.py

# ========== Configuration ==========

# General
TICKER     = 'PLNT'
PERIOD     = "30d"      # 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max (longer period for more data)
INTERVAL   = "5m"       # 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo (hourly for even less noise)
INITIAL_CAPITAL = 10000.0


# Risk Management params
ENABLE_SHORTING = True            # Enable short selling functionality
STOP_LOSS_PCT = 0.02              # Stop loss percentage (2%)
TAKE_PROFIT_PCT = 0.05            # Take profit percentage (5%)
USE_TRAILING_STOP = False         # Enable trailing stop loss
TRAILING_STOP_PCT = 0.03          # Trailing stop percentage (3%)
DEDUP_WINDOW_MINUTES = 30        # Time window to prevent duplicate transactions
SPREAD_PCT = 0.001                # Bid-ask spread percentage (0.1% for SPY)

# Strategy selector
# 1='mean_reversion', 2='moving_average', 
# 3='williams_%R', 4='matei_strat', 5='rsi'
STRATEGY = 3

# Matei Strategy params (corrected RSI logic)
MATEI_RSI_PERIOD = 20
MATEI_WR_PERIOD = 20
MATEI_VOL_LOOKBACK = 20
MATEI_RSI_BUY_TH = 30             # Buy when RSI <= 30 (oversold)
MATEI_RSI_SELL_TH = 70            # Sell when RSI >= 70 (overbought)
MATEI_WR_BUY_TH = -80
MATEI_WR_SELL_TH = -20
MATEI_VOL_BUY_TH = 0.007
MATEI_VOL_SELL_TH = 0.0

# RSI Strategy params
RSI_PERIOD = 72
RSI_BUY_THRESHOLD = 30      # Buy when RSI <= 30 (oversold)
RSI_SELL_THRESHOLD = 70     # Sell when RSI >= 70 (overbought)


# Mean‐Reversion params
MR_WINDOW    = 20       # look-back window (in bars)
MR_THRESHOLD = 1.0      # z-score entry/exit threshold

# Moving‐Average crossover params
MA_SHORT_WINDOW = 5     # in bars
MA_LONG_WINDOW  = 20    # in bars

# Williams %R strategy params
WR_PERIOD             = 24     # look-back window
WR_LONG_ENTRY_THRESH  = -80.0  # enter long when %R ≤ this
WR_LONG_EXIT_THRESH   = -20.0  # exit long when %R ≥ this
WR_SHORT_ENTRY_THRESH = -20.0  # enter short when %R ≥ this
WR_SHORT_EXIT_THRESH  = -80.0  # exit short when %R ≤ this

# Plotting options
GENERATE_ZOOM_PLOTS   = False   # 7d & 14d zooms
GENERATE_CUSTOM_RANGE = True   # custom day-range plots
AUTO_SUGGEST_RANGES   = False   # auto-suggest custom ranges
CUSTOM_RANGES         = [(10, 60), (60, 120), (120, 180)]
GENERATE_HOUR_RANGES  = False   # hour-based custom ranges
CUSTOM_HOUR_RANGES    = [(2, 4), (8, 12), (20, 24)]

# ====================================

from strategy import *
from backtest import *
import yfinance as yf
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
        elif STRATEGY == 4:
            df, signals = generate_matei_strat(
                TICKER,
                period=PERIOD,
                interval=INTERVAL,
                rsi_period=MATEI_RSI_PERIOD,
                wr_period=MATEI_WR_PERIOD,
                vol_lookback=MATEI_VOL_LOOKBACK,
                rsi_buy_th=MATEI_RSI_BUY_TH,
                rsi_sell_th=MATEI_RSI_SELL_TH,
                wr_buy_th=MATEI_WR_BUY_TH,
                wr_sell_th=MATEI_WR_SELL_TH,
                vol_buy_th=MATEI_VOL_BUY_TH,
                vol_sell_th=MATEI_VOL_SELL_TH
    )
        elif STRATEGY == 5:
            df, signals = generate_rsi_strat(
                TICKER,
                period=PERIOD,
                interval=INTERVAL,
                rsi_period=RSI_PERIOD,
                buy_threshold=RSI_BUY_THRESHOLD,
                sell_threshold=RSI_SELL_THRESHOLD
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

    # 3) Backtest with risk management
    portfolio, transactions = backtest_strategy(
        df, signals, INITIAL_CAPITAL,
        log_transactions=True,
        stop_loss_pct=STOP_LOSS_PCT,
        take_profit_pct=TAKE_PROFIT_PCT,
        use_trailing_stop=USE_TRAILING_STOP,
        trailing_stop_pct=TRAILING_STOP_PCT,
        enable_shorting=ENABLE_SHORTING,
        dedup_window_minutes=DEDUP_WINDOW_MINUTES,
        spread_pct=SPREAD_PCT
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
    
    # 7) Calculate and print final profit as last output
    initial_value = portfolio['total'].iloc[0]
    final_value = portfolio['total'].iloc[-1]
    total_return = (final_value - initial_value) / initial_value * 100
    absolute_profit = final_value - initial_value
    
    print(f"\n{'='*60}")
    print(f"FINAL RESULTS - {TICKER} Strategy {STRATEGY}")
    print(f"{'='*60}")
    print(f"Initial Capital: ${initial_value:,.2f}")
    print(f"Final Portfolio Value: ${final_value:,.2f}")
    print(f"Absolute Profit: ${absolute_profit:,.2f}")
    print(f"Total Return: {total_return:.2f}%")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
