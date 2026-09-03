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

`bot.run` is the only code path that submits orders. `scripts/check_alpaca.py`
is read-only.

| variable | default | |
|---|---|---|
| `BOT_SYMBOL` | `SPY` | |
| `BOT_INTERVAL` | `1h` | |
| `BOT_NOTIONAL` | `50000` | dollars per entry |
| `BOT_RSI_PERIOD` | `14` | |
| `BOT_RSI_BUY` / `BOT_RSI_SELL` | `45` / `50` | enter at or below buy, exit at or above sell |
| `BOT_LOOKBACK_DAYS` | `10` | ~60 session bars |
| `BOT_FEED` | `sip` | |
| `BOT_DB_PATH` | `data/bot.db` | `/app/data/bot.db` in the image |
| `BOT_DRY_RUN` | `0` | |
| `BOT_HEARTBEAT_URL` | unset | healthchecks.io ping URL; unset disables |

Credentials come from `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY`, never from
config files in the repo.

**State.** SQLite records the trade log, an equity point per run, and which
bars have been handled. It deliberately does *not* track positions or cash:
Alpaca is authoritative for those, and a local copy drifts on partial fills or
manual intervention, leaving two sources of truth. The `bar_ts` primary key is
what makes re-running a bar a no-op, so an overlapping schedule or a manual
re-invocation cannot double-trade.

**Entry and exit are a band, not a threshold.** The bot enters when RSI falls to
`BOT_RSI_BUY`, holds through the middle, and exits when RSI reaches
`BOT_RSI_SELL`. Holding through the middle is what makes the exit threshold
meaningful; without it a single number would control both ends.

Defaults of 45/50 are chosen for trade frequency, not returns. On 60 days of
SPY hourly bars they give roughly 1.6 round trips a week, against 0.4 for the
textbook 30/70 - which over a one-week window would likely produce no trades at
all and nothing to compare. Widening the band trades less and holds longer;
`long_only=False` keeps the older stateless two-sided mapping so previous
backtests still reproduce.

**Closed bars only.** Alpaca stamps a bar at its start and serves it while it is
still forming, so `bot.data.drop_unclosed` discards any bar whose interval has
not elapsed. Acting on a partial bar is a live-only failure the backtest cannot
reproduce, because history contains only closed bars.

---

## Deployment

The bot is one-shot: a systemd timer starts it, it evaluates one bar, it exits.
Nothing runs in between.

```
docker build -t quant-bot:latest .
sudo deploy/install.sh          # writes /etc/quant-bot/env on first run
# add the Alpaca keys to /etc/quant-bot/env, then:
sudo deploy/install.sh
```

### First deployment to EC2

Instance: `t3.micro`, Ubuntu Server 24.04 LTS, **16 GiB** gp3. The 8 GiB default
is too tight once the image, Docker's overlay store and OS updates are on it.

Security group: **one** inbound rule, SSH on 22 from your own address. The bot
only makes outbound connections, so nothing needs to reach in. Never open 22 to
`0.0.0.0/0`.

**On your machine**

```
chmod 400 ~/.ssh/bot-control.pem
export KEY=~/.ssh/bot-control.pem EC2=ubuntu@<public-ip>

scp -i "$KEY" .env "$EC2":~/bot.env     # copy, don't retype a 40-char secret
ssh -i "$KEY" "$EC2"
```

The code is cloned from GitHub on the box, not copied from the laptop.

**On the server**

```
# 1. Swap first: 1 GB RAM plus `pip install pandas` is an OOM waiting to happen,
#    and it presents as a confusing random build failure.
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
printf '/swapfile none swap sw 0 0\n' | sudo tee -a /etc/fstab
sudo findmnt --verify            # parse fstab the way boot will, before trusting it

# 2. Docker
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io git
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu
sudo reboot                      # picks up the group change and any new kernel

# 3. Clone and build (a few minutes on a micro)
git clone https://github.com/MihutMatei/quant-backtester.git
cd quant-backtester
docker build -t quant-bot:latest .
docker run --rm quant-bot:latest python -c "import core.signals, bot.run; print('ok')"

# 4. Credentials
sudo install -d -m 0750 /etc/quant-bot
sudo install -m 0600 ~/bot.env /etc/quant-bot/env
shred -u ~/bot.env

# 5. Install and start
sudo deploy/install.sh

# 6. Verify
systemctl is-enabled quant-bot.timer     # "enabled" - survives reboot
systemctl list-timers quant-bot.timer
sudo systemctl start quant-bot.service   # run one bar now
journalctl -u quant-bot -n 20 --no-pager
systemctl list-units --failed            # want an empty list
sudo grep -c '^BOT_HEARTBEAT_URL=.\+' /etc/quant-bot/env   # want 1, not 0
```

That last check matters more than it looks: an unset heartbeat URL is a silent
no-op by design, so the logs cannot tell you it is missing. Confirm the check
went green on healthchecks.io rather than inferring it from a clean run.

### After a reboot

Nothing. The timer is enabled, so systemd arms it at boot. With
`Persistent=true` a run may fire on its own within a minute if the reboot
spanned a scheduled `:05`.

A manual `systemctl start quant-bot.service` right after a reboot usually logs
`bar ... already handled; nothing to do` - the state volume survived, so the
bar was already processed. That is the idempotency guard working, not a fault.
For a full decision without touching state, run dry against an empty database:

```
docker run --rm --env-file /etc/quant-bot/env -e BOT_DRY_RUN=1 quant-bot:latest
```

### Deploying a change

```
cd ~/quant-backtester && git pull && docker build -t quant-bot:latest .
```

The next timer fire picks up the new image. **Nothing rebuilds automatically** -
a `git pull` without a rebuild silently keeps running the old strategy, which is
easy to do and hard to notice.

### Troubleshooting

| symptom | cause |
|---|---|
| `ssh: Connection timed out` | security group drops the packets - your address changed. `deploy/allow-my-ip.sh` |
| `ssh: Connection refused` | packets arrive, nothing listening - wrong IP, or sshd down |
| `swapon failed: Read-only file system` | the swap unit ran before the root fs was remounted rw |
| `What= path is not absolute, ignoring: swapfile` | the fstab entry is missing its leading `/`. Must be `/swapfile`, not `swapfile` |
| `docker: permission denied` | the `docker` group has not applied to this shell yet - log out and back in, or `newgrp docker` |
| bot logs `already handled` | correct: that bar was processed. Waits for the next close |

Edit `/etc/fstab` carefully and run `sudo findmnt --verify` before rebooting. A
broken entry can stop the instance booting, and recovering that means detaching
the volume and attaching it to a second instance.

| file | |
|---|---|
| `deploy/quant-bot.service` | one `docker run`, `Type=oneshot` |
| `deploy/quant-bot.timer` | fires at `*:05:00`, `Persistent=true` |
| `deploy/quant-bot-failure@.service` | `OnFailure=` hook - add a real notifier here |
| `deploy/allow-my-ip.sh` | repoint the SSH rule after changing networks |
| `deploy/botctl.sh` | day-to-day operation - status, logs, pause, update |

### Operating it

`deploy/botctl.sh` wraps the day-to-day commands:

```
deploy/botctl.sh status     # timer state, next fire, last run, recent decisions
deploy/botctl.sh logs       # follow the journal
deploy/botctl.sh history    # every decision so far
deploy/botctl.sh run        # run one bar now (real)
deploy/botctl.sh dry        # evaluate now without trading or pinging
deploy/botctl.sh state      # trade log and equity points from SQLite
deploy/botctl.sh pause      # stop the timer - no further trading
deploy/botctl.sh resume     # start it again
deploy/botctl.sh reload     # after editing deploy/*.service|timer
deploy/botctl.sh update     # git pull, rebuild, re-arm
```

Or the underlying systemd commands directly:

```
journalctl -u quant-bot -f            # the trade log
systemctl list-timers quant-bot.timer # when it next fires
systemctl list-units --failed         # did anything break
sudo systemctl start quant-bot.service   # run one bar now
sudo systemctl disable --now quant-bot.timer
```

There is no long-running process to keep alive. The timer holds the schedule
and the service does one bar's work and exits, so "restarting the bot" means
reloading the units and re-arming the timer - which is what `reload` does.
Restarting a `Type=oneshot` service just runs it once more.

**`pause` does not close anything.** If the bot is holding a position when you
stop the timer, that position stays open and unmanaged: the exit signal cannot
fire while nothing is evaluating bars. Check `botctl.sh state` before pausing
for any length of time.

**`dry` blanks `BOT_HEARTBEAT_URL` and mounts no volume.** A diagnostic run
should not touch the monitoring signal - a ping from a manual test would mask a
genuinely dead scheduler - and skipping the volume means the idempotency guard
cannot suppress the decision you are trying to see.

**SSH access from a changing address.** The security group allows port 22 from
one address. After moving between networks, `deploy/allow-my-ip.sh <sg-id>`
repoints it at wherever you are now and revokes the stale rules - otherwise
every network you have ever used stays permanently open. It authorises the new
address before revoking the old ones, since security group changes apply to
established connections and revoking first could cut the session you are using
to run it.

A stale rule shows up as SSH *timing out* rather than being refused: the group
silently drops the packets, so there is nothing to answer you. The bot is
unaffected either way - it only makes outbound connections and never needs
inbound SSH to trade.

**Why `:05` and not `:00`.** The hourly bar closes exactly on the hour; firing
on the boundary races the bar's own aggregation. Five past is clear of it.
Alpaca's `end` parameter filters which bars come back rather than truncating
them, so the twenty-minute delay on recent SIP data does not cut the last bar
short - it only decides whether that bar is returned at all.

**Market hours are not in the schedule, deliberately.** The timer fires around
the clock and `bot/run.py` asks Alpaca's clock, which knows about holidays,
half-days and unscheduled closures. A hardcoded window does not, and would try
to trade on days the market is shut. An out-of-hours run costs one API call and
exits 0.

**Why one-shot rather than a container that sleeps.** `--restart always` only
notices a process *exiting*. A bot that deadlocks or blocks on a socket keeps
the container `Up` and Docker satisfied while nothing trades - liveness without
correctness. With a timer, "did it run and exit 0 in the last hour" is a
question systemd and journald already answer, and a failed run shows up in
`systemctl list-units --failed` without anything being built.

Credentials live in `/etc/quant-bot/env`, root-owned and `0600` - outside the
repo and outside the image. State is a named Docker volume, so idempotency and
the trade log survive restarts and image rebuilds.

---

## Heartbeat

systemd catches runs that *fail*. It cannot catch runs that never happen - a
disabled timer, a stopped instance, a machine that never came back from a
reboot. Nothing fails in those cases, so nothing fires, and the silence looks
exactly like a healthy weekend. The detector has to live somewhere the
instance's death cannot reach.

Set `BOT_HEARTBEAT_URL` to a healthchecks.io ping URL. The bot posts to it after
every successful run and to `<url>/fail` on an exception.

On the healthchecks.io side, create a check with **period 1 hour, grace 20
minutes**. Use period rather than cron: `Persistent=true` makes a missed run
fire immediately on boot rather than at `:05`, and the bot always acts on the
latest closed bar, so a late run trades identically to a punctual one. You care
whether it is running at all, not whether it is on time.

Two properties the tests pin, because both would be self-defeating:

* **Unset is a silent no-op.** No network call, no warning, no behaviour change.
* **A ping can never break a run.** Every network error is swallowed and logged;
  the order is submitted *before* the ping, so a ping means the work finished
  rather than that it started. Monitoring must not be able to take down the
  thing it monitors.

Do-nothing runs ping too. A run that correctly decided to stay flat is a
healthy run, and staying quiet would make a slow market indistinguishable from
a dead bot.

The POST body is what healthchecks.io shows in the check history and in the
alert mail, so it leads with a line that stands on its own:

```
no action | rsi 72.8 signal 0 position 0.0000 equity 99,999.98 | SPY 1h | 2026-09-03 18:05:12Z

FAILED: RuntimeError: alpaca is down | SPY 1h | 2026-09-03 18:05:12Z
Traceback (most recent call last):
  ...
```

A raw traceback starts with `Traceback (most recent call last):`, which tells
you nothing about which bot, which symbol, or when - so the failure body leads
with the exception type and message and keeps the traceback underneath.

Note what the body says in each alert. A `/fail` ping trips the check
immediately and the body is that run's traceback. A silence alert means no ping
arrived at all, so the newest body is the *last healthy run* - which is the
useful context: what it was doing before it went quiet.

---

## Extending

* Add signal logic to `core/signals.py` if the bot should trade it, or
  `research/legacy_signals.py` if it is research only.
* Wrap it into a strategy in `research/strategies.py`.
* Reuse `research/backtest.py` for consistent evaluation.

Anything imported by `core/` ends up in the deployed image, so keep it free of
matplotlib and yfinance.

---
