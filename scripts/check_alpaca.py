#!/usr/bin/env python3
"""Alpaca paper-account connectivity and capability check.

A diagnostic, not part of the service. Answers the questions that shape
bot/orders.py and bot/data.py before either gets written:

  * do the credentials work, and is the account able to trade
  * is the market open, and when does it next open/close
  * is the symbol fractionable (the backtest assumes divisible shares)
  * which data feed is this account entitled to (IEX free vs SIP paid)
  * do Alpaca bars survive core.frames.normalize_ohlcv / validate_ohlcv
  * how far do Alpaca bars drift from the yfinance bars the backtest uses

Usage:
    python scripts/check_alpaca.py [SYMBOL] [--interval 1h] [--order]

--order additionally submits a far-from-market limit order and cancels it, to
prove the full submit/cancel round trip. It is priced so it cannot fill.
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

OK, WARN, FAIL = "  ok  ", " warn ", " FAIL "
_failures = []
_warnings = []


def line(status, label, detail=""):
    print(f"[{status}] {label}" + (f"  {detail}" if detail else ""))
    if status == FAIL:
        _failures.append(label)
    elif status == WARN:
        _warnings.append(label)


def header(title):
    print(f"\n{'-' * 68}\n{title}\n{'-' * 68}")


def load_dotenv(path=REPO_ROOT / ".env"):
    """Minimal .env reader so this needs no extra dependency."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, _, value = raw.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def parse_timeframe(interval):
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    units = {"m": TimeFrameUnit.Minute, "h": TimeFrameUnit.Hour, "d": TimeFrameUnit.Day}
    amount, unit = int(interval[:-1]), interval[-1].lower()
    if unit not in units:
        raise ValueError(f"unsupported interval {interval!r}")
    return TimeFrame(amount, units[unit])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol", nargs="?", default="SPY")
    ap.add_argument("--interval", default="1h")
    ap.add_argument("--lookback-days", type=int, default=10)
    ap.add_argument("--order", action="store_true",
                    help="submit and cancel a non-marketable limit order")
    args = ap.parse_args()

    load_dotenv()

    # ---------------------------------------------------------------- creds
    header("Credentials")
    key = os.environ.get("APCA_API_KEY_ID")
    secret = os.environ.get("APCA_API_SECRET_KEY")
    base = os.environ.get("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")
    if not key or not secret:
        line(FAIL, "APCA_API_KEY_ID / APCA_API_SECRET_KEY not set",
             "put them in .env (already gitignored)")
        return 1
    line(OK, "credentials present", f"key ...{key[-4:]}")
    if "paper" not in base:
        line(FAIL, "base URL is not the paper endpoint", base)
        print("\nRefusing to continue against a live endpoint.")
        return 1
    line(OK, "paper endpoint", base)

    try:
        from alpaca.common.exceptions import APIError
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.trading.client import TradingClient
    except ImportError:
        line(FAIL, "alpaca-py not installed", "pip install -r requirements-dev.txt")
        return 1

    trading = TradingClient(key, secret, paper=True)

    # -------------------------------------------------------------- account
    header("Account")
    try:
        acct = trading.get_account()
    except APIError as exc:
        line(FAIL, "authentication failed", str(exc))
        return 1
    line(OK, "authenticated", f"account {acct.account_number}")
    line(OK if acct.status == "ACTIVE" else FAIL, f"status {acct.status}")
    line(OK, "buying power", f"${float(acct.buying_power):,.2f}")
    line(OK, "cash", f"${float(acct.cash):,.2f}")
    line(OK, "equity", f"${float(acct.equity):,.2f}")
    if getattr(acct, "trading_blocked", False):
        line(FAIL, "trading is blocked on this account")
    if getattr(acct, "pattern_day_trader", False):
        line(WARN, "flagged as pattern day trader",
             "intraday strategies may be restricted under $25k")
    line(OK, "shorting enabled", str(getattr(acct, "shorting_enabled", "unknown")))

    # ---------------------------------------------------------------- clock
    header("Market clock")
    clock = trading.get_clock()
    line(OK, "market is " + ("OPEN" if clock.is_open else "CLOSED"),
         f"now {clock.timestamp:%Y-%m-%d %H:%M %Z}")
    line(OK, "next open", f"{clock.next_open:%Y-%m-%d %H:%M %Z}")
    line(OK, "next close", f"{clock.next_close:%Y-%m-%d %H:%M %Z}")
    if not clock.is_open:
        line(WARN, "market closed", "orders would queue for the next session")

    # ---------------------------------------------------------------- asset
    header(f"Asset properties: {args.symbol}")
    try:
        asset = trading.get_asset(args.symbol)
    except APIError as exc:
        line(FAIL, f"could not fetch asset {args.symbol}", str(exc))
        return 1
    line(OK if asset.tradable else FAIL, f"tradable: {asset.tradable}")
    frac = bool(getattr(asset, "fractionable", False))
    line(OK if frac else WARN, f"fractionable: {frac}",
         "" if frac else "bot/orders.py must round to whole shares")
    line(OK, f"shortable: {getattr(asset, 'shortable', 'unknown')}")
    line(OK, f"easy to borrow: {getattr(asset, 'easy_to_borrow', 'unknown')}")
    if not frac:
        print("\n    NOTE: the backtest sizes positions as cash/price (infinitely\n"
              "    divisible). Without fractional shares the live bot must floor to\n"
              "    whole shares and hold the remainder as idle cash - a real source\n"
              "    of backtest/live divergence.")

    # ----------------------------------------------------------- data feeds
    header("Data feed entitlement")
    from alpaca.data.enums import DataFeed
    data = StockHistoricalDataClient(key, secret)
    end = datetime.now(timezone.utc) - timedelta(minutes=20)
    start = end - timedelta(days=args.lookback_days)
    tf = parse_timeframe(args.interval)

    feeds = {}
    for name, feed in (("IEX (free)", DataFeed.IEX), ("SIP (paid)", DataFeed.SIP)):
        try:
            req = StockBarsRequest(symbol_or_symbols=args.symbol, timeframe=tf,
                                   start=start, end=end, feed=feed)
            df = data.get_stock_bars(req).df
            feeds[name] = df
            line(OK, f"{name} entitled", f"{len(df)} bars")
        except APIError as exc:
            msg = str(exc)
            line(WARN, f"{name} not available", msg[:90])

    if not feeds:
        line(FAIL, "no usable data feed")
        return 1

    # Prefer SIP when entitled: IEX is a single venue and has gaps.
    feed_name = next((n for n in feeds if n.startswith("SIP")), None) or next(iter(feeds))
    bars = feeds[feed_name]
    line(OK, f"using {feed_name} for the checks below")
    if len(feeds) > 1:
        counts = {n: len(d) for n, d in feeds.items()}
        line(OK if len(set(counts.values())) == 1 else WARN,
             "bar counts by feed", str(counts))

    # --------------------------------------------------- core.frames contract
    header("core.frames contract")
    from core.frames import OHLCV, normalize_ohlcv, validate_ohlcv

    print(f"    raw Alpaca columns: {list(bars.columns)}")
    df = bars
    if hasattr(df.index, "nlevels") and df.index.nlevels > 1:
        df = df.droplevel("symbol")
        line(OK, "dropped the symbol index level")
    df = df.rename(columns={c: c.capitalize() for c in df.columns})
    missing = [c for c in OHLCV if c not in df.columns]
    if missing:
        line(FAIL, "Alpaca bars lack OHLCV columns after rename", str(missing))
    else:
        line(OK, "columns map to OHLCV", "lowercase -> Title case rename required")

    try:
        norm = normalize_ohlcv(df)
        validate_ohlcv(norm, context=f"{args.symbol} via Alpaca")
        line(OK, "normalize_ohlcv + validate_ohlcv pass", f"{len(norm)} bars")
        print(f"    latest bar: {norm.index[-1]}  close {norm['Close'].iloc[-1]:.2f}")
    except Exception as exc:
        line(FAIL, "frames contract rejected Alpaca bars", str(exc))
        norm = None

    # ------------------------------------------------ signal on live-ish data
    if norm is not None and len(norm) > 15:
        from core.signals import rsi_signals
        sig = rsi_signals(norm, period=14)
        vals = sorted(set(sig["signal"].dropna().unique()))
        line(OK, "core.signals.rsi_signals runs on Alpaca bars",
             f"values {vals}, latest {sig['signal'].iloc[-1]:.0f}")

    # ------------------------------------------------- feed vs yfinance drift
    header("Alpaca vs yfinance (the backtest's data source)")
    try:
        from research.data_fetcher import fetch_data
        yf_df = fetch_data(args.symbol, period=f"{max(args.lookback_days, 5)}d",
                           interval=args.interval, progress=False)
        if norm is not None:
            a = norm["Close"]
            b = yf_df["Close"]
            a.index = a.index.tz_convert("UTC") if a.index.tz else a.index.tz_localize("UTC")
            b.index = b.index.tz_convert("UTC") if b.index.tz else b.index.tz_localize("UTC")
            a_off = sorted({t.minute for t in a.index})
            b_off = sorted({t.minute for t in b.index})
            line(OK, "Alpaca bar minute-offsets", str(a_off))
            line(OK, "yfinance bar minute-offsets", str(b_off))
            if a_off != b_off:
                line(WARN, "bar boundaries do not align",
                     f"Alpaca opens at :{a_off[0]:02d}, yfinance at :{b_off[0]:02d}")
            line(OK, "bars in window", f"Alpaca {len(a)} vs yfinance {len(b)}")
            if len(a) > len(b) * 1.2:
                line(WARN, "Alpaca returns more bars",
                     "it includes extended hours; yfinance is regular session only")

            joined = a.to_frame("alpaca").join(b.to_frame("yfinance"), how="inner")
            if joined.empty:
                line(WARN, "zero overlapping timestamps",
                     "indicators would be computed over different windows")
                print("\n    NOTE: the backtest (yfinance) and the bot (Alpaca) would not\n"
                      "    merely see different prices - they would aggregate different bars.\n"
                      "    Either source Alpaca history for the backtest too, or accept that\n"
                      "    backtest results do not describe the deployed bot.")
            else:
                diff = (joined["alpaca"] - joined["yfinance"]).abs()
                rel = (diff / joined["yfinance"] * 100)
                line(OK, f"{len(joined)} overlapping bars ({feed_name})")
                line(OK, "mean abs diff", f"{diff.mean():.4f} ({rel.mean():.3f}%)")
                line(OK, "max abs diff", f"{diff.max():.4f} ({rel.max():.3f}%)")
                if rel.max() > 0.5:
                    line(WARN, "feeds diverge materially",
                         "backtest and live would see different prices")
    except Exception as exc:
        line(WARN, "yfinance comparison skipped", str(exc)[:90])

    # ------------------------------------------------------- order round trip
    if args.order:
        header("Order round trip (submit -> cancel)")
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest
        try:
            last = float(norm["Close"].iloc[-1])
            limit = round(last * 0.5, 2)  # far below market: cannot fill
            order = trading.submit_order(LimitOrderRequest(
                symbol=args.symbol, qty=1, side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY, limit_price=limit))
            line(OK, "order submitted", f"id {order.id} limit ${limit}")
            trading.cancel_order_by_id(order.id)
            line(OK, "order cancelled", "submit/cancel round trip works")
        except APIError as exc:
            line(FAIL, "order round trip failed", str(exc)[:120])
    else:
        header("Order round trip")
        line(WARN, "skipped", "pass --order to test submit/cancel")

    # -------------------------------------------------------------- summary
    header("Summary")
    if _failures:
        print(f"  {len(_failures)} FAILURE(S): " + "; ".join(_failures))
    if _warnings:
        print(f"  {len(_warnings)} warning(s): " + "; ".join(_warnings))
    if not _failures and not _warnings:
        print("  All checks passed. Safe to build bot/data.py and bot/orders.py.")
    elif not _failures:
        print("  No failures. Connectivity is fine; review the warnings above -\n"
              "  they describe constraints the bot has to be built around.")
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
