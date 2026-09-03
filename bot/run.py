"""Entrypoint: evaluate the latest closed bar, act once, exit.

Invoked on a schedule (systemd timer) rather than run as a daemon loop.

Exit 0 means "ran correctly", including the common do-nothing cases - market
closed, bar already handled, signal unchanged. A non-zero exit means the run
genuinely failed, so systemd can tell the two apart and OnFailure only fires on
real breakage.

Every successful path pings the heartbeat, do-nothing cases included: a run
that correctly decided to do nothing is a healthy run, and suppressing its ping
would make a quiet market indistinguishable from a dead bot.
"""
import logging
import sys
import traceback
from datetime import UTC, datetime

from bot import heartbeat, state
from bot.broker import Broker
from bot.config import load_config
from bot.data import get_bars
from bot.orders import decide
from core.signals import rsi_signals

log = logging.getLogger("bot")


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        stream=sys.stdout,
    )


def run_once(config):
    """Do the work for one bar. Returns a one-line summary, or raises."""
    broker = Broker(config.api_key, config.api_secret,
                    paper=True, dry_run=config.dry_run)

    if not broker.is_market_open():
        return "market closed; nothing to do"

    bars = get_bars(config)
    bar_ts = bars.index[-1]
    price = float(bars["Close"].iloc[-1])
    log.info("latest closed bar %s, close %.2f (%d bars)", bar_ts, price, len(bars))

    conn = state.init_db(config.db_path)

    if state.already_acted_on(conn, bar_ts):
        return f"bar {bar_ts} already handled; nothing to do"

    signals = rsi_signals(bars, period=config.rsi_period,
                          buy_threshold=config.rsi_buy,
                          sell_threshold=config.rsi_sell)
    signal = float(signals["signal"].iloc[-1])
    rsi = float(signals["rsi"].iloc[-1])
    position = broker.get_position(config.symbol)
    equity = broker.get_equity()
    log.info("rsi %.1f -> signal %.0f | position %.6f | equity %.2f",
             rsi, signal, position, equity)

    intent = decide(position, signal, config.notional, price, symbol=config.symbol)

    if intent is None:
        state.record_run(conn, bar_ts, datetime.now(UTC), signal, "none",
                         position, equity)
        return (f"no action | rsi {rsi:.1f} signal {signal:.0f} "
                f"position {position:.4f} equity {equity:,.2f}")

    log.info("decision: %s %.6f %s (%s)",
             intent.side, intent.qty, intent.symbol, intent.reason)
    order_id = broker.submit_order(intent)

    state.record_trade(conn, bar_ts, datetime.now(UTC), intent.symbol,
                       intent.side, intent.qty, price, order_id,
                       f"rsi={rsi:.1f} signal={signal:.0f} {intent.reason}")
    state.record_run(conn, bar_ts, datetime.now(UTC), signal, intent.side,
                     position, equity)
    return (f"{intent.side} {intent.qty:.4f} {intent.symbol} @ {price:.2f} | "
            f"rsi {rsi:.1f} equity {equity:,.2f} order {order_id}")


def main():
    setup_logging()

    # A failure here means no config, and therefore no heartbeat URL to report
    # it with. The missing ping is itself the signal: the check goes silent and
    # healthchecks raises the alarm after the grace period.
    config = load_config()
    log.info("starting: %s", config)

    try:
        summary = run_once(config)
    except Exception:
        log.exception("run failed")
        heartbeat.fail(config.heartbeat_url, traceback.format_exc())
        return 1

    log.info(summary)
    heartbeat.ok(config.heartbeat_url, summary)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logging.getLogger("bot").exception("run failed before configuration")
        sys.exit(1)
