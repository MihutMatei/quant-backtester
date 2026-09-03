"""Entrypoint: evaluate the latest closed bar, act once, exit.

Invoked on a schedule (systemd timer or cron) rather than run as a daemon loop.
Exit 0 means "ran correctly", including the common cases of nothing to do -
market closed, bar already handled, signal unchanged. A non-zero exit means the
run genuinely failed, so a scheduler can tell the two apart.
"""
import logging
import sys
from datetime import UTC, datetime

from bot import state
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


def main():
    setup_logging()
    config = load_config()
    log.info("starting: %s", config)

    broker = Broker(config.api_key, config.api_secret,
                    paper=True, dry_run=config.dry_run)

    if not broker.is_market_open():
        log.info("market is closed; nothing to do")
        return 0

    bars = get_bars(config)
    bar_ts = bars.index[-1]
    price = float(bars["Close"].iloc[-1])
    log.info("latest closed bar %s, close %.2f (%d bars)", bar_ts, price, len(bars))

    conn = state.init_db(config.db_path)

    if state.already_acted_on(conn, bar_ts):
        log.info("bar %s already handled; nothing to do", bar_ts)
        return 0

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
        log.info("no action required")
        state.record_run(conn, bar_ts, datetime.now(UTC), signal, "none",
                         position, equity)
        return 0

    log.info("decision: %s %.6f %s (%s)",
             intent.side, intent.qty, intent.symbol, intent.reason)
    order_id = broker.submit_order(intent)

    state.record_trade(conn, bar_ts, datetime.now(UTC), intent.symbol,
                       intent.side, intent.qty, price, order_id,
                       f"rsi={rsi:.1f} signal={signal:.0f} {intent.reason}")
    state.record_run(conn, bar_ts, datetime.now(UTC), signal, intent.side,
                     position, equity)
    log.info("done")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logging.getLogger("bot").exception("run failed")
        sys.exit(1)
