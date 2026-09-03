"""SQLite-backed state so restarts don't lose positions or the trade log."""


def init_db(path):
    raise NotImplementedError


def record_trade(conn, trade):
    raise NotImplementedError
