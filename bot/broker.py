"""Alpaca trading client wrapper.

Kept thin: everything here is I/O, so the interesting logic stays in
bot.orders where it can be tested without a network or an account.
"""
import logging

log = logging.getLogger(__name__)

DRY_RUN_ORDER_ID = "dry-run"


class Broker:
    """Alpaca paper/live trading, with a dry-run mode that submits nothing."""

    def __init__(self, api_key, api_secret, paper=True, dry_run=False, client=None):
        self.dry_run = dry_run
        if client is not None:
            self._client = client          # injected in tests
        else:
            from alpaca.trading.client import TradingClient
            self._client = TradingClient(api_key, api_secret, paper=paper)

    def get_position(self, symbol):
        """Signed position size for `symbol`; 0.0 when flat.

        Alpaca raises rather than returning an empty position when flat, so the
        'no position' case arrives as an APIError and must not propagate.
        """
        from alpaca.common.exceptions import APIError
        try:
            return float(self._client.get_open_position(symbol).qty)
        except APIError as exc:
            if "position does not exist" in str(exc).lower() or "404" in str(exc):
                return 0.0
            raise

    def get_equity(self):
        return float(self._client.get_account().equity)

    def is_market_open(self):
        return bool(self._client.get_clock().is_open)

    def submit_order(self, intent):
        """Send an OrderIntent to Alpaca. Returns the order id."""
        if self.dry_run:
            log.info("DRY RUN: would %s %.6f %s (%s)",
                     intent.side, intent.qty, intent.symbol, intent.reason)
            return DRY_RUN_ORDER_ID

        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        side = OrderSide.BUY if intent.side == "buy" else OrderSide.SELL
        order = self._client.submit_order(MarketOrderRequest(
            symbol=intent.symbol,
            qty=round(intent.qty, 6),
            side=side,
            # Fractional quantities require a market DAY order on Alpaca.
            time_in_force=TimeInForce.DAY,
        ))
        log.info("submitted %s %.6f %s -> order %s",
                 intent.side, intent.qty, intent.symbol, order.id)
        return str(order.id)
