"""SQLite helpers for the watchlist, price history, and settings."""
import sqlite3
import sys
from pathlib import Path


def _resource_path(name: str) -> Path:
    """Find a bundled file whether running as a plain script or as a
    PyInstaller-built .app (which unpacks resources to a temp folder)."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / name
    return Path(__file__).with_name(name)


def _data_dir() -> Path:
    """A writable, persistent location outside the app bundle — a packaged
    .app's own folder isn't a safe place to write a database."""
    d = Path.home() / "Library" / "Application Support" / "WatchlistPeek"
    d.mkdir(parents=True, exist_ok=True)
    return d


DB_PATH = _data_dir() / "tracker.db"
SCHEMA_PATH = _resource_path("schema.sql")

# Seed symbols for a first run. yfinance symbol -> display name.
DEFAULT_WATCHLIST = [
    ("^NSEI", "NIFTY 50"),
]


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = connect()
    conn.executescript(SCHEMA_PATH.read_text())
    if not conn.execute("SELECT 1 FROM watchlist LIMIT 1").fetchone():
        for i, (symbol, name) in enumerate(DEFAULT_WATCHLIST):
            conn.execute(
                "INSERT INTO watchlist (symbol, display_name, sort_order) VALUES (?,?,?)",
                (symbol, name, i),
            )
    conn.commit()
    conn.close()


def get_watchlist() -> list[sqlite3.Row]:
    conn = connect()
    rows = conn.execute(
        "SELECT symbol, display_name FROM watchlist ORDER BY sort_order, added_at"
    ).fetchall()
    conn.close()
    return rows


def add_symbol(symbol: str, display_name: str) -> None:
    conn = connect()
    max_order = conn.execute("SELECT COALESCE(MAX(sort_order), -1) FROM watchlist").fetchone()[0]
    conn.execute(
        "INSERT OR REPLACE INTO watchlist (symbol, display_name, sort_order) VALUES (?,?,?)",
        (symbol.strip().upper(), display_name.strip(), max_order + 1),
    )
    conn.commit()
    conn.close()


def remove_symbol(symbol: str) -> None:
    conn = connect()
    conn.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))
    conn.commit()
    conn.close()


def log_prices(quotes: dict[str, dict]) -> None:
    """quotes: {symbol: {price, prev_close, change, pct_change, ...}}"""
    conn = connect()
    conn.executemany(
        """INSERT INTO price_log (symbol, price, prev_close, change, pct_change)
           VALUES (:symbol, :price, :prev_close, :change, :pct_change)""",
        [{"symbol": s, **q} for s, q in quotes.items() if q.get("price") is not None],
    )
    conn.commit()
    conn.close()


def get_setting(key: str, default: str | None = None) -> str | None:
    conn = connect()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    conn = connect()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Watchlist:", [dict(r) for r in get_watchlist()])
