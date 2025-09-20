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
  * Easy to extend with custom strategies via `signals.py`.

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

* **`main.py`** – Entry point of the application.
* **`backtest.py`** – Core backtesting engine with performance metrics and plotting.
* **`data_fetcher.py`** – Data retrieval and preprocessing via yfinance.
* **`strategy.py`** – High-level strategy definitions.
* **`signals.py`** – Signal-generation logic (e.g., moving averages, mean reversion).

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
   pip install -r requirements.txt
   ```

   If a `requirements.txt` file is not available, install manually:

   ```
   pip install pandas numpy matplotlib yfinance
   ```

4. **Verify installation**
   Run the script with default configuration to check everything is working:

   ```
   python main.py
   ```

---

## Requirements File (`requirements.txt`)

A sample `requirements.txt` is provided below for convenience:

```
pandas>=2.0.0
numpy>=1.25.0
matplotlib>=3.7.0
yfinance>=0.2.30
```

---

## Usage

1. **Configure parameters** in `main.py`

   ```
   TICKER = 'PLTR'
   PERIOD = "60d"
   INTERVAL = "5m"
   STRATEGY = 1  # 1 = mean reversion, 2 = moving average
   ```

2. **Run the backtest**

   ```
   python main.py
   ```

3. **View results**

   * Plots are saved as `.png` in the working directory.
   * Transaction logs are saved in `transactions.txt`.
   * Console output shows trade summaries and performance metrics.

---

## Extending

* Add new signal-generation logic in `signals.py`.
* Wrap into a strategy in `strategy.py`.
* Reuse the same `backtest.py` pipeline for consistent evaluation.

---
