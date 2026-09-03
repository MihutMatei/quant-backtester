"""bot.config must never leak credentials and must reject nonsense early."""
import pytest

from bot.config import BotConfig, load_config

CREDS = {"APCA_API_KEY_ID": "key-1234", "APCA_API_SECRET_KEY": "secret-abcd"}


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Isolate from the developer's real .env and environment."""
    for name in list(CREDS) + ["BOT_SYMBOL", "BOT_INTERVAL", "BOT_NOTIONAL",
                               "BOT_RSI_PERIOD", "BOT_RSI_BUY", "BOT_RSI_SELL",
                               "BOT_LOOKBACK_DAYS", "BOT_FEED", "BOT_DB_PATH",
                               "BOT_DRY_RUN"]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("bot.config.load_dotenv", lambda *a, **k: False)
    for k, v in CREDS.items():
        monkeypatch.setenv(k, v)
    return monkeypatch


class TestDefaults:
    def test_matches_the_agreed_configuration(self, env):
        cfg = load_config()
        assert (cfg.symbol, cfg.interval) == ("SPY", "1h")
        assert cfg.notional == 50_000.0
        assert (cfg.rsi_period, cfg.rsi_buy, cfg.rsi_sell) == (14, 30.0, 70.0)
        assert cfg.feed == "sip"
        assert cfg.dry_run is False


class TestOverrides:
    def test_reads_env(self, env):
        env.setenv("BOT_SYMBOL", "qqq")
        env.setenv("BOT_NOTIONAL", "12345.67")
        env.setenv("BOT_RSI_PERIOD", "21")
        cfg = load_config()
        assert cfg.symbol == "QQQ"          # upper-cased
        assert cfg.notional == pytest.approx(12345.67)
        assert cfg.rsi_period == 21

    @pytest.mark.parametrize("raw,expected",
                             [("1", True), ("true", True), ("YES", True),
                              ("on", True), ("0", False), ("no", False),
                              ("", False)])
    def test_dry_run_parsing(self, env, raw, expected):
        env.setenv("BOT_DRY_RUN", raw)
        assert load_config().dry_run is expected

    def test_non_numeric_value_is_rejected(self, env):
        env.setenv("BOT_NOTIONAL", "lots")
        with pytest.raises(ValueError, match="must be a number"):
            load_config()


class TestValidation:
    def test_missing_credentials_raise(self, env):
        env.delenv("APCA_API_KEY_ID")
        with pytest.raises(ValueError, match="APCA_API_KEY_ID"):
            load_config()

    def test_non_positive_notional_rejected(self, env):
        env.setenv("BOT_NOTIONAL", "0")
        with pytest.raises(ValueError, match="must be positive"):
            load_config()

    def test_inverted_thresholds_rejected(self, env):
        env.setenv("BOT_RSI_BUY", "80")
        with pytest.raises(ValueError, match="must be below"):
            load_config()

    def test_zero_lookback_rejected(self, env):
        env.setenv("BOT_LOOKBACK_DAYS", "0")
        with pytest.raises(ValueError, match="at least 1"):
            load_config()


class TestSecrecy:
    def test_repr_hides_credentials(self, env):
        text = repr(load_config())
        assert "secret-abcd" not in text
        assert "key-1234" not in text

    def test_but_the_values_are_still_available(self, env):
        cfg = load_config()
        assert cfg.api_key == "key-1234"

    def test_config_is_logged_by_run_so_repr_matters(self):
        # bot.run does `log.info("starting: %s", config)`, so anything in the
        # repr reaches the logs and, in deployment, journald.
        cfg = BotConfig(api_key="PKTESTKEY123", api_secret="SUPERSECRETVALUE")
        rendered = str(cfg)
        assert "SUPERSECRETVALUE" not in rendered
        assert "PKTESTKEY123" not in rendered
        assert "SPY" in rendered      # non-secret fields still shown
