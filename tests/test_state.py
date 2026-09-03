"""bot.state is the idempotency guard: re-running a bar must not re-trade."""
from datetime import UTC, datetime

from bot import state

BAR = "2026-09-03 16:00:00+00:00"
NOW = datetime(2026, 9, 3, 16, 5, tzinfo=UTC)


def db(tmp_path):
    return state.init_db(tmp_path / "bot.db")


def test_creates_the_file_and_schema(tmp_path):
    conn = db(tmp_path)
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"runs", "trades"} <= tables
    assert (tmp_path / "bot.db").exists()


def test_creates_missing_parent_directories(tmp_path):
    state.init_db(tmp_path / "nested" / "deeper" / "bot.db")
    assert (tmp_path / "nested" / "deeper" / "bot.db").exists()


def test_init_is_idempotent(tmp_path):
    state.init_db(tmp_path / "bot.db")
    state.init_db(tmp_path / "bot.db")   # must not raise on existing schema


class TestIdempotency:
    def test_unhandled_bar_is_not_flagged(self, tmp_path):
        assert state.already_acted_on(db(tmp_path), BAR) is False

    def test_recorded_bar_is_flagged(self, tmp_path):
        conn = db(tmp_path)
        state.record_run(conn, BAR, NOW, 1.0, "buy", 0.0, 100_000.0)
        assert state.already_acted_on(conn, BAR) is True

    def test_duplicate_bar_does_not_raise_or_duplicate(self, tmp_path):
        conn = db(tmp_path)
        state.record_run(conn, BAR, NOW, 1.0, "buy", 0.0, 100_000.0)
        state.record_run(conn, BAR, NOW, 0.0, "none", 5.0, 99_000.0)
        rows = conn.execute("SELECT * FROM runs").fetchall()
        assert len(rows) == 1
        assert rows[0]["action"] == "buy"     # the first write wins

    def test_survives_reopening_the_database(self, tmp_path):
        state.record_run(db(tmp_path), BAR, NOW, 1.0, "buy", 0.0, 100_000.0)
        assert state.already_acted_on(db(tmp_path), BAR) is True


class TestTrades:
    def test_records_the_fields_the_brief_requires(self, tmp_path):
        conn = db(tmp_path)
        state.record_trade(conn, BAR, NOW, "SPY", "buy", 64.7, 772.55,
                           "order-1", "rsi=28.4 signal=1")
        row = state.trades(conn)[0]
        assert (row["symbol"], row["side"]) == ("SPY", "buy")
        assert row["qty"] == 64.7 and row["price"] == 772.55
        assert row["order_id"] == "order-1"
        assert "rsi=28.4" in row["reason"]

    def test_multiple_trades_per_bar_are_allowed(self, tmp_path):
        conn = db(tmp_path)
        for side in ("sell", "buy"):
            state.record_trade(conn, BAR, NOW, "SPY", side, 1.0)
        assert len(state.trades(conn)) == 2


class TestEquityCurve:
    def test_returns_points_oldest_first(self, tmp_path):
        conn = db(tmp_path)
        state.record_run(conn, "2026-09-03 15:00:00+00:00", NOW, 0.0, "none", 0.0, 100.0)
        state.record_run(conn, "2026-09-03 16:00:00+00:00", NOW, 1.0, "buy", 0.0, 110.0)
        assert [e for _, e in state.equity_curve(conn)] == [100.0, 110.0]

    def test_skips_runs_without_equity(self, tmp_path):
        conn = db(tmp_path)
        state.record_run(conn, BAR, NOW, 0.0, "none", 0.0, None)
        assert state.equity_curve(conn) == []
