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
   STRATEGY = 3          # 1=mean reversion, 2=moving average, 3=Williams %R, 4=combined, 5=RSI
   EXECUTION_LAG = 1     # bars between signal and fill; 0 restores same-bar close fills
   DATA_SOURCE = "alpaca"  # "alpaca" (what the bot trades) or "yfinance"
   ```

   `DATA_SOURCE = "alpaca"` backtests on the same bars the live bot will act on,
   filtered to the regular session. It needs `APCA_API_KEY_ID` and
   `APCA_API_SECRET_KEY` in `.env`. Run `python scripts/check_alpaca.py` first to
   confirm connectivity.

   The two sources are not interchangeable: Alpaca hourly bars align to clock
   hours and yfinance to the market session, so they share no timestamps and
   aggregate different windows. Alpaca also serves 6+ years of hourly history
   against yfinance's 730-day cap.

2. **Run the backtest** from the repository root

   ```
   python -m research.run_backtest
   ```

3. **View results**

   * Plots are saved as `.png` in the working directory.
   * Transaction logs are saved in `transactions.txt`.
   * Console output shows trade summaries and performance metrics.

---

## Tests and linting

```
pytest                                  # 51 tests over core/ and the backtest loop
ruff check core bot tests scripts
```

`research/` is excluded from linting - it is prior research code kept for
reference. CI runs both on every push.

---

## Docker

The bot image carries only `core/` and `bot/`, built from `requirements-bot.txt`:

```
docker build -t quant-bot .
docker run --rm --env-file .env -v botstate:/app/data quant-bot
```

State lives in `/app/data`, owned by the runtime user (uid 10001). A **named
volume** inherits that ownership automatically; a **host bind mount** must be
chowned to `10001:10001` first or SQLite cannot create the database.

~298 MB, runs as an unprivileged user, and contains no matplotlib, yfinance, or
`.env`. CI asserts all three - if an import creeps into `core/` that drags in the
research stack, the build fails rather than silently shipping ~144 MB more.

Credentials are passed at runtime via `--env-file`; `.env` is in `.dockerignore`
so it can never be baked into a layer.

The container is one-shot: it evaluates the latest bar, acts, and exits.
Scheduling is external (systemd timer or cron), so there is no daemon loop.

---

## The bot

One-shot: evaluates the latest *closed* bar, acts, exits. Exit 0 covers the
common do-nothing cases (market closed, bar already handled, signal unchanged);
non-zero means the run genuinely failed, so a scheduler can tell them apart.

```
BOT_DRY_RUN=1 python -m bot.run    # decide and log, submit nothing
python -m bot.run                  # live one-shot against the paper account
```

| variable | default | |
|---|---|---|
| `BOT_SYMBOL` | `SPY` | |
| `BOT_INTERVAL` | `1h` | |
| `BOT_NOTIONAL` | `50000` | dollars per entry |
| `BOT_RSI_PERIOD` / `BOT_RSI_BUY` / `BOT_RSI_SELL` | `14` / `30` / `70` | |
| `BOT_LOOKBACK_DAYS` | `10` | ~60 session bars |
| `BOT_FEED` | `sip` | |
| `BOT_DB_PATH` | `data/bot.db` | `/app/data/bot.db` in the image |
| `BOT_DRY_RUN` | `0` | |

Credentials come from `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY`, never from
config files in the repo.

**State.** SQLite records the trade log, an equity point per run, and which
bars have been handled. It deliberately does *not* track positions or cash:
Alpaca is authoritative for those, and a local copy drifts on partial fills or
manual intervention, leaving two sources of truth. The `bar_ts` primary key is
what makes re-running a bar a no-op, so an overlapping schedule or a manual
re-invocation cannot double-trade.

**Closed bars only.** Alpaca stamps a bar at its start and serves it while it is
still forming, so `bot.data.drop_unclosed` discards any bar whose interval has
not elapsed. Acting on a partial bar is a live-only failure the backtest cannot
reproduce, because history contains only closed bars.

---

## Extending

* Add signal logic to `core/signals.py` if the bot should trade it, or
  `research/legacy_signals.py` if it is research only.
* Wrap it into a strategy in `research/strategies.py`.
* Reuse `research/backtest.py` for consistent evaluation.

Anything imported by `core/` ends up in the deployed image, so keep it free of
matplotlib and yfinance.

---
