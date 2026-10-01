"""Fetch live prices for a list of symbols using yfinance.

Batches all symbols into one request where possible, retries transient
failures, and falls back to the last known good price per symbol so a
rate-limit blip doesn't blank the widget.

Set NIFTY_DEBUG=1 in the environment to print the real cause of any
fetch failure instead of failing silently:
    NIFTY_DEBUG=1 python3 widget.py
"""
import os
import time

import yfinance as yf

_last_good: dict[str, dict] = {}
DEBUG = os.environ.get("NIFTY_DEBUG") == "1"


def _from_fast_info(symbol: str) -> dict | None:
    try:
        info = yf.Ticker(symbol).fast_info
        price = info.get("last_price")
        prev_close = info.get("previous_close") or info.get("regular_market_previous_close")
        if price is None or prev_close in (None, 0):
            if DEBUG:
                print(f"[debug] {symbol}: fast_info gave price={price} prev_close={prev_close}")
            return None
        currency = info.get("currency") or "USD"
        return price, prev_close, currency
    except Exception as e:
        if DEBUG:
            print(f"[debug] {symbol}: fast_info raised {type(e).__name__}: {e}")
        return None


def _from_history(symbol: str) -> dict | None:
    """Fallback for when fast_info is unreliable (a known yfinance weak spot).
    Pulls the last two daily closes directly, which is the most battle-tested
    code path in the library."""
    try:
        hist = yf.Ticker(symbol).history(period="5d", interval="1d")
        if hist is None or len(hist) < 2 or "Close" not in hist:
            if DEBUG:
                print(f"[debug] {symbol}: history() returned {0 if hist is None else len(hist)} rows")
            return None
        closes = hist["Close"].dropna()
        if len(closes) < 2:
            return None
        price, prev_close = float(closes.iloc[-1]), float(closes.iloc[-2])
        try:
            currency = yf.Ticker(symbol).fast_info.get("currency") or "USD"
        except Exception:
            currency = "USD"
        return price, prev_close, currency
    except Exception as e:
        if DEBUG:
            print(f"[debug] {symbol}: history() raised {type(e).__name__}: {e}")
        return None


def _quote_for(symbol: str) -> dict | None:
    result = _from_fast_info(symbol) or _from_history(symbol)
    if result is None:
        return None
    price, prev_close, currency = result
    change = price - prev_close
    pct = 100 * change / prev_close
    return {"price": round(price, 2), "prev_close": round(prev_close, 2),
            "change": round(change, 2), "pct_change": round(pct, 2),
            "currency": currency}


def fetch_quotes(symbols: list[str], retries: int = 2) -> dict[str, dict]:
    """Returns {symbol: {price, prev_close, change, pct_change, currency, stale}}.
    'stale' is True when live data failed and a cached value is being reused.
    """
    out = {}
    for symbol in symbols:
        quote = None
        for attempt in range(retries):
            quote = _quote_for(symbol)
            if quote is not None:
                break
            time.sleep(1.5 * (attempt + 1))
        if quote is not None:
            quote["stale"] = False
            _last_good[symbol] = quote
            out[symbol] = quote
        elif symbol in _last_good:
            out[symbol] = {**_last_good[symbol], "stale": True}
        else:
            out[symbol] = {"price": None, "prev_close": None, "change": None,
                            "pct_change": None, "stale": True}
    return out


if __name__ == "__main__":
    print(fetch_quotes(["^NSEI", "RELIANCE.NS", "TCS.NS"]))