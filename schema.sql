-- Watchlist Peek: database schema (SQLite)

CREATE TABLE IF NOT EXISTS watchlist (
    symbol       TEXT PRIMARY KEY,   -- yfinance symbol, e.g. '^NSEI', 'RELIANCE.NS', 'AAPL'
    display_name TEXT NOT NULL,      -- shown on the widget, e.g. 'NIFTY 50', 'Reliance'
    sort_order   INTEGER DEFAULT 0,
    added_at     TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS price_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol        TEXT NOT NULL,
    price         REAL,
    prev_close    REAL,
    change        REAL,
    pct_change    REAL,
    fetched_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_price_log_symbol_time ON price_log(symbol, fetched_at);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
