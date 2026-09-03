"""SQLite audit trail, idempotency ledger, and equity snapshots.

Deliberately does NOT track positions or cash. Alpaca is authoritative for
those; a local copy drifts on partial fills, manual dashboard intervention, or
corporate actions, leaving two sources of truth and no way to tell which is
stale. What is kept here is what Alpaca cannot give us cheaply: which bars this
bot has already acted on, and an equity point per run for the weekly comparison.
"""
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    bar_ts    TEXT PRIMARY KEY,   -- UNIQUE: makes re-running a bar a no-op
    ran_at    TEXT NOT NULL,
    signal    REAL NOT NULL,
    action    TEXT NOT NULL,
    position  REAL NOT NULL,
    equity    REAL
);

CREATE TABLE IF NOT EXISTS trades (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    bar_ts    TEXT NOT NULL,
    ts        TEXT NOT NULL,
    symbol    TEXT NOT NULL,
    side      TEXT NOT NULL,
    qty       REAL NOT NULL,
    price     REAL,
    order_id  TEXT,
    reason    TEXT
);

CREATE INDEX IF NOT EXISTS idx_trades_bar_ts ON trades(bar_ts);
"""


def init_db(path):
    """Open (creating if needed) the state database."""
    path = Path(path)
    if path.parent and str(path.parent) not in ("", "."):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def already_acted_on(conn, bar_ts):
    """True if this bar has already been processed - the idempotency guard."""
    row = conn.execute(
        "SELECT 1 FROM runs WHERE bar_ts = ?", (str(bar_ts),)
    ).fetchone()
    return row is not None


def record_run(conn, bar_ts, ran_at, signal, action, position, equity=None):
    """Record that this bar was processed. Ignores a duplicate bar_ts."""
    conn.execute(
        "INSERT OR IGNORE INTO runs (bar_ts, ran_at, signal, action, position, equity)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (str(bar_ts), str(ran_at), float(signal), action, float(position),
         None if equity is None else float(equity)),
    )
    conn.commit()


def record_trade(conn, bar_ts, ts, symbol, side, qty, price=None,
                 order_id=None, reason=None):
    """Log a submitted order: timestamp, price, quantity, and the signal reason."""
    conn.execute(
        "INSERT INTO trades (bar_ts, ts, symbol, side, qty, price, order_id, reason)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (str(bar_ts), str(ts), symbol, side, float(qty),
         None if price is None else float(price),
         None if order_id is None else str(order_id), reason),
    )
    conn.commit()


def equity_curve(conn):
    """(bar_ts, equity) points for the weekly comparison, oldest first."""
    return [
        (row["bar_ts"], row["equity"])
        for row in conn.execute(
            "SELECT bar_ts, equity FROM runs WHERE equity IS NOT NULL"
            " ORDER BY bar_ts"
        )
    ]


def trades(conn):
    """Every logged trade, oldest first."""
    return [dict(r) for r in conn.execute("SELECT * FROM trades ORDER BY id")]
