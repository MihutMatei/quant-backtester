# Quant multistrat backtester and paper-trading bot

A backtesting framework and the live trading bot built from it, deployed as a
scheduled service on AWS.

The same signal code drives both: `core/` is imported by the backtester and by
the bot, so a strategy is tested on exactly the bars it will later trade. The
bot runs one-shot on a systemd timer against an Alpaca **paper** account, logs
every decision, and is watched by an external dead-man's switch.

```
Alpaca bars -> core.frames -> core.signals -> bot.orders -> Alpaca paper API
                    |                                              |
              research/backtest                            SQLite trade log
                    |                                              |
              plots + metrics                            healthchecks.io ping
```

Nothing here is investment advice, and none of it trades real money.

---

## Repository layout

Split by **dependency weight**, so the deployed image never carries the research
stack. Anything imported by `core/` ends up on the server; matplotlib and
yfinance must not.

| | |
|---|---|
| **`core/`** | shared by both sides. pandas, numpy, alpaca-py. |
| `core/frames.py` | OHLCV normalisation and validation - one frame shape for every data source |
| `core/signals.py` | the strategy the bot runs (RSI band). `signal.iloc[-1]` is the position to hold after that bar closes |
| `core/metrics.py` | CAGR, Sharpe, max drawdown, total return, annualised per bar interval |
| `core/alpaca_source.py` | historical bars from Alpaca, session-filtered |
| `core/env.py` | dependency-free `.env` reader |
| **`bot/`** | live paper trading. Ships to the server. |
| `bot/run.py` | entry point: evaluate one closed bar, act, exit |
| `bot/orders.py` | pure decision function - no I/O, the most heavily tested module |
| `bot/broker.py` | Alpaca trading client wrapper |
| `bot/data.py` | live bars, with the still-forming bar discarded |
| `bot/state.py` | SQLite trade log, equity points, idempotency ledger |
| `bot/config.py` | configuration from environment variables |
| `bot/heartbeat.py` | dead-man's-switch ping |
| **`research/`** | backtesting and plotting. Local only; never copied into the image. |
| `research/run_backtest.py` | entry point; all configuration at the top of the file |
| `research/backtest.py` | simulation loop with stops, spread and execution lag |
| `research/legacy_signals.py` | earlier custom strategies, kept for reference |
| **`deploy/`** | systemd units and operational scripts |
| **`scripts/`** | `check_alpaca.py` - read-only environment diagnostic |
| **`tests/`** | 151 tests, all offline: no network, no credentials |

---

## Getting started

```bash
git clone https://github.com/MihutMatei/quant-backtester.git
cd quant-backtester
./setup.sh                       # venv + requirements-dev.txt
source quantenv/bin/activate
pytest                           # 151 passing
```

`setup.sh` rebuilds the virtualenv if a Python upgrade has broken it - on a
rolling distribution that happens more often than you would like.

For anything touching Alpaca you need a **paper** account (free) and a `.env`:

```
APCA_API_KEY_ID=...
APCA_API_SECRET_KEY=...
APCA_API_BASE_URL=https://paper-api.alpaca.markets
BOT_HEARTBEAT_URL=              # optional, see Monitoring
```

`.env` is gitignored and in `.dockerignore`. Credentials never enter the repo or
an image layer.

Check the account before anything else:

```bash
python scripts/check_alpaca.py SPY
```

It verifies credentials, account status, the market clock, whether the symbol is
fractionable and shortable, feed entitlement, and that Alpaca bars satisfy the
`core.frames` contract. It refuses to run against a non-paper endpoint and never
submits an order.

### Dependencies

Split by target, so the image stays small:

| file | contents | installed |
|---|---|---|
| `requirements-bot.txt` | alpaca-py, pandas, numpy | ~178 MB |
| `requirements-research.txt` | + matplotlib, yfinance | ~322 MB |
| `requirements-dev.txt` | + pytest, ruff | ~348 MB |

---

## Backtesting

Configuration lives at the top of `research/run_backtest.py`:

```python
TICKER = 'SPY'
PERIOD = "30d"
INTERVAL = "1h"
STRATEGY = 5            # 1=mean reversion, 2=moving average, 3=Williams %R, 4=combined, 5=RSI
EXECUTION_LAG = 1       # bars between signal and fill; 0 restores same-bar close fills
DATA_SOURCE = "alpaca"  # "alpaca" (what the bot trades) or "yfinance"
```

```bash
python -m research.run_backtest
```

Plots land as `.png` in the working directory, trades in `transactions.txt`, and
a summary on stdout.

**The two data sources are not interchangeable.** Alpaca hourly bars align to
clock hours; yfinance aligns to the market session. They share no timestamps and
aggregate different windows, so an RSI over 14 Alpaca bars is a different
indicator from an RSI over 14 yfinance bars. `DATA_SOURCE = "alpaca"` is the
default because it is what the bot trades. Alpaca also serves 6+ years of hourly
history against yfinance's 730-day cap.

---

## The bot

One-shot. It evaluates the latest **closed** bar, acts, and exits - there is no
daemon. Exit 0 covers every do-nothing case (market closed, bar already handled,
signal unchanged); non-zero means the run genuinely failed, so a scheduler can
tell the two apart.

```bash
BOT_DRY_RUN=1 python -m bot.run    # decide and log, submit nothing
python -m bot.run                  # live one-shot against the paper account
```

`bot.run` is the only code path in the repository that can submit an order.

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

**Strategy.** Long or flat only. It enters when RSI falls to `BOT_RSI_BUY`, holds
through the middle, and exits when RSI reaches `BOT_RSI_SELL`. Holding through
the middle is what makes the exit threshold mean anything - without that carry a
single number would control both ends.

Defaults of 45/50 are chosen for **trade frequency, not returns**. On 60 days of
SPY hourly bars they give roughly 1.6 round trips a week, against 0.4 for the
textbook 30/70 - which over a one-week comparison window would likely produce no
trades at all and nothing to measure. Selecting thresholds on backtested returns
over a single symbol and two months would be fitting noise.

---

## Tests, linting, CI

```bash
pytest
ruff check core bot tests scripts
```

151 tests, all offline - no network, no credentials, no Alpaca account needed.
`research/` is excluded from linting; it is earlier research code kept for
reference rather than maintained.

GitHub Actions runs both on every push, then builds the image and asserts three
things about it: the research stack is absent, `core` and `bot` import, and no
`.env` is present. If an import creeps into `core/` that drags matplotlib in, CI
fails rather than silently shipping ~144 MB more.

---

## Docker

```bash
docker build -t quant-bot:latest .
docker run --rm --env-file .env -v quant-bot-state:/app/data quant-bot:latest
```

~298 MB. Multi-stage on `python:3.14-slim`, runs as an unprivileged user (uid
10001), contains only `core/` and `bot/`.

State lives in `/app/data`, owned by that user. A **named volume** inherits the
ownership automatically; a **host bind mount** must be chowned to `10001:10001`
first, or SQLite cannot create the database.

---

## Deploying to EC2

What follows is the exact setup this project runs on. A `t3.micro` is enough -
the bot does about two seconds of work an hour.

**Instance:** `t3.micro`, Ubuntu Server 24.04 LTS, **16 GiB** gp3. The 8 GiB
default is too tight once the image, Docker's overlay store and OS updates are
on it.

**Security group:** one inbound rule, SSH on port 22 from your own address. The
bot only makes outbound connections, so nothing needs to reach in. Never open 22
to `0.0.0.0/0`.

### On your machine

```bash
chmod 400 ~/.ssh/your-key.pem
export KEY=~/.ssh/your-key.pem EC2=ubuntu@<public-ip>

scp -i "$KEY" .env "$EC2":~/bot.env     # copy rather than retype a 40-char secret
ssh -i "$KEY" "$EC2"
```

The code is cloned from GitHub on the box, not copied from the laptop.

### On the server

```bash
# 1. Swap first. 1 GB of RAM plus `pip install pandas` is an OOM kill waiting to
#    happen, and it presents as a confusing random build failure.
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

# 5. Install units and start the timer
sudo deploy/install.sh

# 6. Verify
systemctl is-enabled quant-bot.timer                       # "enabled" - survives reboot
systemctl list-timers quant-bot.timer
sudo systemctl start quant-bot.service                     # run one bar now
journalctl -u quant-bot -n 20 --no-pager
systemctl list-units --failed                              # want an empty list
sudo grep -c '^BOT_HEARTBEAT_URL=.\+' /etc/quant-bot/env   # want 1, not 0
```

That last check matters more than it looks: an unset heartbeat URL is a silent
no-op by design, so a clean log cannot tell you it is missing. Confirm the check
went green on healthchecks.io rather than inferring it from a successful run.

| file | |
|---|---|
| `deploy/quant-bot.service` | one `docker run`, `Type=oneshot` |
| `deploy/quant-bot.timer` | fires at `*:05:00`, `Persistent=true` |
| `deploy/quant-bot-failure@.service` | `OnFailure=` hook - add a real notifier here |
| `deploy/install.sh` | idempotent installer |
| `deploy/botctl.sh` | day-to-day operation |
| `deploy/allow-my-ip.sh` | repoint the SSH rule after changing networks |

---

## Operating it

```bash
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

**There is no long-running process to restart.** The timer holds the schedule
and the service does one bar's work and exits, so "restarting the bot" means
reloading the units and re-arming the timer - what `reload` does. Restarting a
`Type=oneshot` service merely runs it once more.

| you want to | command |
|---|---|
| change strategy or bot code | `botctl.sh update` |
| change a `.service` or `.timer` | `botctl.sh reload` |
| change `/etc/quant-bot/env` | nothing - it is read fresh each run |
| see a decision right now | `botctl.sh dry` |
| stop trading | `botctl.sh pause` |

**`pause` does not close anything.** A position held when you stop the timer
stays open and unmanaged, because the exit signal cannot fire while nothing is
evaluating bars. Check `botctl.sh state` before pausing for any length of time.

**Nothing rebuilds automatically.** A `git pull` without a rebuild keeps running
the old image, so a strategy change appears to deploy and does not.

**After a reboot there is nothing to do.** The timer is enabled, so systemd arms
it at boot, and `Persistent=true` runs a missed occurrence shortly after. A
manual run straight afterwards usually logs `already handled` - the state volume
survived, so that bar was processed. That is the idempotency guard working.

---

## Monitoring

systemd catches runs that *fail*. It cannot catch runs that never happen - a
disabled timer, a stopped instance, a machine that never came back from a
reboot. Nothing fails in those cases, so nothing fires, and the silence looks
exactly like a healthy weekend. A watchdog running beside the bot dies with it,
so the detector has to be external.

Set `BOT_HEARTBEAT_URL` to a [healthchecks.io](https://healthchecks.io) ping URL.
The bot posts to it after every successful run and to `<url>/fail` on an
exception. Create the check with **period 1 hour, grace 20 minutes**, and attach
an email or Telegram integration.

Use period rather than cron: `Persistent=true` makes a missed run fire
immediately on boot rather than at `:05`, and the bot always acts on the latest
closed bar, so a late run trades identically to a punctual one. You care whether
it is running at all, not whether it is on time.

Two properties the tests pin, because either failing would be self-defeating:

* **Unset is a silent no-op** - no network call, no warning, no behaviour change.
* **A ping can never break a run.** Every network error is swallowed, a timeout
  is always set, and the order is submitted *before* the ping - so a ping means
  the work finished, not that it started. Monitoring must not be able to take
  down the thing it monitors.

Do-nothing runs ping too. A run that correctly stayed flat is a healthy run, and
staying quiet would make a slow market indistinguishable from a dead bot.

The POST body is the decision line, so the check history doubles as an
hour-by-hour record:

```
no action | rsi 72.8 signal 0 position 0.0000 equity 99,999.98 | SPY 1h | 2026-09-03 18:05:12Z
```

---

## Troubleshooting

| symptom | cause |
|---|---|
| `ssh: Connection timed out` | security group is dropping packets - your address changed. Run `deploy/allow-my-ip.sh <sg-id>` |
| `ssh: Connection refused` | packets arrive, nothing listening - wrong IP, or sshd is down |
| `swapon failed: Read-only file system` | the swap unit ran before the root filesystem was remounted rw |
| `What= path is not absolute, ignoring: swapfile` | the fstab entry is missing its leading `/`. It must read `/swapfile` |
| `docker: permission denied` | the `docker` group has not applied to this shell - log out and back in, or `newgrp docker` |
| bot logs `already handled` | correct: that bar was processed. It waits for the next close |
| bot logs `market closed` | correct: the timer fires around the clock on purpose |
| healthchecks never goes green | `BOT_HEARTBEAT_URL` is unset or wrong. It is silent by design |

Edit `/etc/fstab` carefully and run `sudo findmnt --verify` before rebooting. A
broken entry can stop the instance booting, and recovering that means detaching
the volume and attaching it to a second instance.

---

## Design notes

The decisions in here that are not obvious, and why.

**Split by dependency weight, not by feature.** `core/` holds what both sides
need, `bot/` what ships, `research/` what stays local. The Dockerfile copies two
directories and the research stack is excluded by construction rather than by
discipline. CI asserts it, so an accidental import fails the build instead of
quietly adding 144 MB.

**One data source for backtest and live.** yfinance and Alpaca bars share no
timestamps and aggregate different windows, so a yfinance backtest cannot
describe an Alpaca-traded bot. Both sides now read Alpaca through the same
`core.frames` contract.

**Execution lag.** Signals are computed on a bar's close; filling at that same
close is a look-ahead the live bot cannot reproduce. The backtest shifts fills to
the next bar's open by default. `execution_lag=0` restores the old behaviour for
comparison.

**Closed bars only.** Alpaca stamps a bar at its start and serves it while it is
still forming, so `bot.data.drop_unclosed` discards any bar whose interval has
not elapsed. Acting on a partial bar is a live-only failure the backtest cannot
exhibit, because history contains only closed bars.

**Alpaca is authoritative for positions.** SQLite records the trade log, equity
points, and which bars were handled - not positions or cash. A local copy of
those drifts on partial fills or manual intervention, leaving two sources of
truth and no way to tell which is stale.

**Idempotency by `bar_ts`.** The primary key on the run table makes re-running a
bar a no-op, so an overlapping schedule, a reboot catch-up, or a manual
invocation cannot double-trade.

**One-shot rather than a container that sleeps.** `--restart always` only
notices a process *exiting*. A bot that deadlocks keeps the container `Up` and
Docker satisfied while nothing trades - liveness without correctness. With a
timer, "did it run and exit 0 in the last hour" is a question systemd and
journald already answer.

**Market hours are not in the schedule.** The timer fires around the clock and
`bot/run.py` asks Alpaca's clock, which knows about holidays, half-days and
unscheduled closures. A hardcoded window does not, and would try to trade on days
the market is shut. An out-of-hours run costs one API call and exits 0.

**`:05` and not `:00`.** The hourly bar closes exactly on the hour; firing on the
boundary races its aggregation.

---

## Extending

* Add signal logic to `core/signals.py` if the bot should trade it, or
  `research/legacy_signals.py` if it is research only.
* Wrap it into a strategy in `research/strategies.py`.
* Reuse `research/backtest.py` for consistent evaluation.

Anything imported by `core/` ends up in the deployed image, so keep it free of
matplotlib and yfinance. CI will tell you if you forget.

---

## License

Public domain (Unlicense). See `LICENSE`.
