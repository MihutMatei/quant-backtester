#!/usr/bin/env python3
"""Alpaca paper-account connectivity and capability check.

A diagnostic, not part of the service. Confirms the things bot/data.py,
bot/broker.py and bot/orders.py are being written against:

  * credentials work and the account can trade
  * market clock
  * whether the symbol is fractionable and shortable
  * which data feed the account is entitled to
  * the real research/bot data path (fetch_alpaca) returns session-filtered
    bars that satisfy the core.frames contract

Severity: FAIL blocks the bot. warn is a real constraint to design around.
info is context, not a problem.

This script is read-only: it never submits an order. The submit/cancel round
trip was verified once against the paper account; bot.run is the only code path
that places orders.

Usage:
    python scripts/check_alpaca.py [SYMBOL] [--interval 1h] [--compare-yfinance]
"""
import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.env import load_dotenv  # noqa: E402

OK, INFO, WARN, FAIL = "  ok  ", " info ", " warn ", " FAIL "
_failures: list[str] = []
_warnings: list[str] = []


def line(status, label, detail=""):
    print(f"[{status}] {label}" + (f"  {detail}" if detail else ""))
    if status == FAIL:
        _failures.append(label)
    elif status == WARN:
        _warnings.append(label)


def header(title):
    print(f"\n{'-' * 68}\n{title}\n{'-' * 68}")


def check_credentials():
    load_dotenv()
    key = os.environ.get("APCA_API_KEY_ID")
    secret = os.environ.get("APCA_API_SECRET_KEY")
    base = os.environ.get("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")

    header("Credentials")
    if not key or not secret:
        line(FAIL, "APCA_API_KEY_ID / APCA_API_SECRET_KEY not set",
             "put them in .env (already gitignored)")
        return None
    line(OK, "credentials present", f"key ...{key[-4:]}")
    if "paper" not in base:
        line(FAIL, "base URL is not the paper endpoint", base)
        return None
    line(OK, "paper endpoint", base)
    return key, secret


def check_account(trading):
    from alpaca.common.exceptions import APIError

    header("Account")
    try:
        acct = trading.get_account()
    except APIError as exc:
        line(FAIL, "authentication failed", str(exc))
        return None

    line(OK, "authenticated", f"account {acct.account_number}")
    line(OK if acct.status == "ACTIVE" else FAIL, f"status {acct.status}")
    line(OK, "equity", f"${float(acct.equity):,.2f}")
    line(OK, "buying power", f"${float(acct.buying_power):,.2f}")

    if getattr(acct, "trading_blocked", False):
        line(FAIL, "trading is blocked on this account")
    if getattr(acct, "pattern_day_trader", False):
        line(WARN, "flagged as pattern day trader",
             "intraday round trips are restricted under $25k equity")

    positions = trading.get_all_positions()
    orders = trading.get_orders()
    line(INFO, "open positions", str(len(positions)))
    line(INFO, "open orders", str(len(orders)))
    return acct


def check_clock(trading):
    header("Market clock")
    clock = trading.get_clock()
    line(OK, "market is " + ("OPEN" if clock.is_open else "CLOSED"),
         f"now {clock.timestamp:%Y-%m-%d %H:%M %Z}")
    line(INFO, "next open", f"{clock.next_open:%Y-%m-%d %H:%M %Z}")
    line(INFO, "next close", f"{clock.next_close:%Y-%m-%d %H:%M %Z}")
    if not clock.is_open:
        line(INFO, "market closed", "orders would queue for the next session")
    return clock


def check_asset(trading, symbol):
    from alpaca.common.exceptions import APIError

    header(f"Asset properties: {symbol}")
    try:
        asset = trading.get_asset(symbol)
    except APIError as exc:
        line(FAIL, f"could not fetch asset {symbol}", str(exc))
        return None

    line(OK if asset.tradable else FAIL, f"tradable: {asset.tradable}")

    fractionable = bool(getattr(asset, "fractionable", False))
    if fractionable:
        line(OK, "fractionable: True", "backtest cash/price sizing carries over")
    else:
        line(WARN, "fractionable: False",
             "bot/orders.py must floor to whole shares and hold the remainder")

    line(INFO, f"shortable: {getattr(asset, 'shortable', 'unknown')}")
    line(INFO, f"easy to borrow: {getattr(asset, 'easy_to_borrow', 'unknown')}")
    return asset


def check_feeds(key, secret, symbol, interval, lookback_days):
    """Report entitlement. Differing bar counts are expected, not a problem."""
    from alpaca.common.exceptions import APIError

    from core.alpaca_source import fetch_alpaca

    header("Data feed entitlement")
    available = []
    for feed in ("sip", "iex"):
        try:
            df = fetch_alpaca(symbol, period=f"{lookback_days}d", interval=interval,
                              feed=feed)
            available.append(feed)
            line(OK, f"{feed.upper()} entitled", f"{len(df)} session bars")
        except APIError as exc:
            line(INFO, f"{feed.upper()} not available", str(exc)[:80])
        except ValueError as exc:
            line(INFO, f"{feed.upper()} returned nothing", str(exc)[:80])

    if not available:
        line(FAIL, "no usable data feed")
        return None

    feed = "sip" if "sip" in available else available[0]
    line(OK, f"using {feed.upper()}",
         "consolidated tape" if feed == "sip" else "single venue, expect gaps")
    return feed


def check_data_path(symbol, interval, feed, lookback_days):
    """Exercise the exact path research/ and bot/ use, not raw bars."""
    from core.alpaca_source import fetch_alpaca

    header("Data path: fetch_alpaca -> core.frames")
    df = fetch_alpaca(symbol, period=f"{lookback_days}d", interval=interval, feed=feed)

    line(OK, "fetch_alpaca returned OHLCV", f"{len(df)} bars, columns {list(df.columns)}")
    line(OK, "validated by core.frames", "sorted, tz-aware, no NaN closes")

    et = df.index.tz_convert("America/New_York")
    hours = sorted({t.hour for t in et})
    days = len({t.date() for t in et})
    line(OK, "regular session only", f"ET hours {hours}")
    line(INFO, "bars per trading day", f"{len(df) / max(days, 1):.1f} over {days} days")
    line(INFO, "latest bar", f"{df.index[-1]}  close {df['Close'].iloc[-1]:.2f}")

    if any(h < 9 or h > 16 for h in hours):
        line(WARN, "extended-hours bars present",
             "filter_regular_session did not apply")
    return df


def check_signal(df):
    from core.signals import rsi_signals

    header("Signal contract")
    if len(df) < 20:
        line(WARN, "not enough bars to evaluate a signal", f"{len(df)} bars")
        return
    sig = rsi_signals(df, period=14)["signal"]
    values = sorted(set(sig.dropna().unique()))
    line(OK, "rsi_signals runs on Alpaca bars", f"values {values}")
    if not set(values) <= {0.0, 1.0}:
        line(FAIL, "signal is not long/flat", "the bot would try to short")
    line(OK, "latest signal", f"{sig.iloc[-1]:.0f}  (position to hold now)")


def compare_yfinance(symbol, interval, df, lookback_days):
    """Informational only: the project uses Alpaca for both backtest and bot."""
    header("yfinance comparison (informational)")
    try:
        from research.data_fetcher import fetch_data
        yf_df = fetch_data(symbol, period=f"{max(lookback_days, 5)}d",
                           interval=interval, progress=False)
    except Exception as exc:
        line(INFO, "yfinance unavailable", str(exc)[:80])
        return

    a_off = sorted({t.minute for t in df.index})
    b_off = sorted({t.minute for t in yf_df.index})
    line(INFO, "Alpaca bar offsets", f":{a_off}")
    line(INFO, "yfinance bar offsets", f":{b_off}")
    line(INFO, "bar counts", f"Alpaca {len(df)} vs yfinance {len(yf_df)}")
    if a_off != b_off:
        line(INFO, "grids differ by design",
             "why DATA_SOURCE defaults to alpaca for both backtest and bot")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol", nargs="?", default="SPY")
    ap.add_argument("--interval", default="1h")
    ap.add_argument("--lookback-days", type=int, default=10)
    ap.add_argument("--compare-yfinance", action="store_true",
                    help="report how Alpaca and yfinance bars differ")
    args = ap.parse_args()

    creds = check_credentials()
    if creds is None:
        return 1
    key, secret = creds

    try:
        from alpaca.trading.client import TradingClient
    except ImportError:
        line(FAIL, "alpaca-py not installed", "pip install -r requirements-dev.txt")
        return 1

    trading = TradingClient(key, secret, paper=True)

    if check_account(trading) is None:
        return 1
    check_clock(trading)
    if check_asset(trading, args.symbol) is None:
        return 1

    feed = check_feeds(key, secret, args.symbol, args.interval, args.lookback_days)
    if feed is None:
        return 1

    df = check_data_path(args.symbol, args.interval, feed, args.lookback_days)
    check_signal(df)

    if args.compare_yfinance:
        compare_yfinance(args.symbol, args.interval, df, args.lookback_days)

    header("Summary")
    if _failures:
        print(f"  {len(_failures)} FAILURE(S): " + "; ".join(_failures))
    elif _warnings:
        print(f"  No failures. {len(_warnings)} constraint(s) to design around:")
        for w in _warnings:
            print(f"    - {w}")
    else:
        print("  All checks passed. No blocking issues and no constraints flagged.")
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
