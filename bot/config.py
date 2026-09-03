"""Runtime configuration, sourced from the environment.

Credentials are read from env vars only - never committed as module globals.
In Docker they arrive via --env-file; locally core.env reads .env.
"""
import os
from dataclasses import dataclass, field

from core.env import load_dotenv


def _env_float(name, default):
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc


def _env_int(name, default):
    return int(_env_float(name, default))


def _env_bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class BotConfig:
    """Everything the bot needs for one run."""

    symbol: str = "SPY"
    interval: str = "1h"
    notional: float = 50_000.0
    rsi_period: int = 14
    rsi_buy: float = 45.0
    rsi_sell: float = 50.0
    lookback_days: int = 10
    feed: str = "sip"
    db_path: str = "data/bot.db"
    dry_run: bool = False
    # Anyone holding this can mark the check healthy and suppress the
    # alert, so it is a credential: hidden from repr, kept out of the repo.
    heartbeat_url: str = field(default="", repr=False)
    # repr=False so credentials cannot reach a log line via the dataclass repr.
    api_key: str = field(default="", repr=False)
    api_secret: str = field(default="", repr=False)

    def validate(self):
        if not self.api_key or not self.api_secret:
            raise ValueError(
                "APCA_API_KEY_ID / APCA_API_SECRET_KEY are not set. Put them in "
                ".env, or pass them with --env-file when running the container."
            )
        if self.notional <= 0:
            raise ValueError(f"BOT_NOTIONAL must be positive, got {self.notional}")
        if self.rsi_buy >= self.rsi_sell:
            raise ValueError(
                f"BOT_RSI_BUY ({self.rsi_buy}) must be below "
                f"BOT_RSI_SELL ({self.rsi_sell})"
            )
        if self.lookback_days < 1:
            raise ValueError("BOT_LOOKBACK_DAYS must be at least 1")
        return self


def load_config():
    """Build the bot config from environment variables."""
    load_dotenv()
    return BotConfig(
        symbol=os.environ.get("BOT_SYMBOL", "SPY").upper(),
        interval=os.environ.get("BOT_INTERVAL", "1h"),
        notional=_env_float("BOT_NOTIONAL", 50_000.0),
        rsi_period=_env_int("BOT_RSI_PERIOD", 14),
        rsi_buy=_env_float("BOT_RSI_BUY", 45.0),
        rsi_sell=_env_float("BOT_RSI_SELL", 50.0),
        lookback_days=_env_int("BOT_LOOKBACK_DAYS", 10),
        feed=os.environ.get("BOT_FEED", "sip").lower(),
        db_path=os.environ.get("BOT_DB_PATH", "data/bot.db"),
        dry_run=_env_bool("BOT_DRY_RUN"),
        heartbeat_url=os.environ.get("BOT_HEARTBEAT_URL", "").strip(),
        api_key=os.environ.get("APCA_API_KEY_ID", ""),
        api_secret=os.environ.get("APCA_API_SECRET_KEY", ""),
    ).validate()
