# Quantitative Trading Backtester

A modular Python framework for designing, testing, and analyzing algorithmic trading strategies.
This project provides an end-to-end pipeline: data fetching, signal generation, strategy construction, backtesting with portfolio accounting, performance evaluation, and visualization.

---

## Features

* **Data Handling**

  * Flexible historical data download using [yfinance](https://pypi.org/project/yfinance/).
  * Supports multiple intervals: intraday (1m, 5m, 1h) and daily/weekly.
  * Configurable save-to-CSV for reproducibility.

* **Strategies**

  * **Moving Average Crossover** (trend-following).
  * **Mean Reversion** (z-score based).
  * Easy to extend with custom strategies via `core/signals.py`.

* **Backtesting**

  * Tracks positions, cash, and equity over time.
  * Logs buy/sell transactions with returns.
  * Outputs performance metrics:

    * CAGR (Compound Annual Growth Rate)
    * Sharpe Ratio
    * Maximum Drawdown

* **Visualization**

  * Portfolio vs. Buy & Hold plots with transaction markers.
  * Support for zoomed views (last N days).
  * Custom ranges by day or hour for granular analysis.
  * Annotated performance metrics directly on plots.

* **Analysis Tools**

  * Trading pattern insights (frequency, best/worst returns, recent activity).
  * Automatic suggestion of meaningful zoom ranges.

---

## Project Structure

The project is organized into modular components to make it easy to extend and maintain:

The tree is split by dependency weight, so the deployable bot never pulls in the
research stack:

**`core/`** – shared by the backtester and the live bot; pandas only.

* **`core/frames.py`** – OHLCV normalization and validation. One shape for every data source.
* **`core/signals.py`** – Signal logic used in production (RSI). `signal.iloc[-1]` is the position to hold after that bar closes.
* **`core/metrics.py`** – CAGR, Sharpe, max drawdown, total return, with interval-aware annualization.

**`research/`** – backtesting and plotting; local only, pulls in yfinance + matplotlib.

* **`research/run_backtest.py`** – Entry point; all configuration lives at the top.
* **`research/backtest.py`** – Simulation loop with stops, spread, and execution lag.
* **`research/plotting.py`** – Portfolio vs. buy-and-hold plots.
* **`research/legacy_signals.py`** – Earlier custom strategies (Williams %R, mean reversion, combined).
* **`research/strategies.py`** – Fetch-plus-signal glue.
* **`research/data_fetcher.py`** – yfinance retrieval.
* **`research/analysis.py`** – Trade-log statistics.

**`bot/`** – live paper trading against Alpaca. Currently stubs.

---

## Installation

1. **Clone the repository**

   ```
   git clone https://github.com/yourusername/quant-backtester.git
   cd quant-backtester
   ```

2. **Create a virtual environment (recommended)**

   ```
   python -m venv venv
   source venv/bin/activate      # Linux/MacOS
   venv\Scripts\activate         # Windows
   ```

3. **Install dependencies**

   ```
   pip install -r requirements-dev.txt
   ```

   Or run `./setup.sh`, which creates the venv and rebuilds it if a Python
   upgrade has broken it.

4. **Verify installation**
   Run the script with default configuration to check everything is working:

   ```
   python -m research.run_backtest
   ```

---

## Requirements

Dependencies are split by target so the deployed image stays small:

* **`requirements-bot.txt`** – `alpaca-py`, `pandas`, `numpy`. This set defines the
  Docker image and must never pull in matplotlib or yfinance (~178 MB installed).
* **`requirements-research.txt`** – the above plus `matplotlib` and `yfinance`, for
  backtesting locally.
* **`requirements-dev.txt`** – the above plus `pytest` and `ruff`, which CI runs.

---

## Usage

1. **Configure parameters** at the top of `research/run_backtest.py`

   ```
   TICKER = 'PLNT'
   PERIOD = "30d"
   INTERVAL = "5m"
   STRATEGY = 3        # 1=mean reversion, 2=moving average, 3=Williams %R, 4=combined, 5=RSI
   EXECUTION_LAG = 1   # bars between signal and fill; 0 restores same-bar close fills
   ```

2. **Run the backtest** from the repository root

   ```
   python -m research.run_backtest
   ```

3. **View results**

   * Plots are saved as `.png` in the working directory.
   * Transaction logs are saved in `transactions.txt`.
   * Console output shows trade summaries and performance metrics.

---

## Extending

* Add signal logic to `core/signals.py` if the bot should trade it, or
  `research/legacy_signals.py` if it is research only.
* Wrap it into a strategy in `research/strategies.py`.
* Reuse `research/backtest.py` for consistent evaluation.

Anything imported by `core/` ends up in the deployed image, so keep it free of
matplotlib and yfinance.

---
