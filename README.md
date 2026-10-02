# Watchlist Peek

A tiny floating widget that stays on top of every app and shows live prices
for whatever stocks or indices you're watching — Indian (NSE) or US — no
tab-switching, no manual refresh.

## Setup

```bash
cd watchlist-peek
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 widget.py
```

A small dark widget appears near the top-left of your screen, showing
**NIFTY 50** by default. Drag it anywhere by clicking and holding on it.

## Using it

- **Move it:** click and drag anywhere on the widget.
- **Add a stock:** right-click (or Ctrl+click on a trackpad) → "Add symbol…".
  Use a yfinance symbol:
  - India (NSE): ticker + `.NS`, e.g. `RELIANCE.NS`, `TCS.NS`, `INFY.NS`,
    `HDFCBANK.NS`; indices like `^NSEI` (NIFTY 50), `^NSEBANK` (BANK NIFTY)
  - US: plain ticker, e.g. `AAPL`, `MSFT`, `GOOGL`; indices like `^GSPC`
    (S&P 500), `^DJI` (Dow), `^IXIC` (Nasdaq)
  - Prices show in the right currency automatically (₹ for NSE, $ for US,
    etc.) based on what yfinance reports for that symbol.
- **Remove a stock:** right-click → "Remove symbol…", type the exact symbol.
- **Force a refresh:** right-click → "Refresh now".
- **Choose what the change shows:** right-click → "Show" → **% change**,
  **Points change**, or **Both**. Your choice is saved and remembered next
  time you open the app.
- **Check market status:** right-click → "Market status…" for each
  market's open/closed state, local time, and the holiday name if it's
  closed for one today.
- **Quit:** right-click → "Quit", or just close the window.

### Refresh timing

It refreshes every 15 seconds while at least one of your tracked markets is
open (`REFRESH_SECONDS` in `widget.py`), and every 3 minutes when every
tracked market is closed (`REFRESH_SECONDS_CLOSED`) — no point polling often
when nothing's moving. Which market(s) count is worked out from your actual
watchlist: a US-only watchlist is judged by NYSE/Nasdaq hours, an NSE-only
one by NSE hours, and a mixed one by both.

Green with ▲ means up since previous close, red with ▼ means down. A ⚠ next
to a price means the live fetch failed and it's showing the last known value
(this happens occasionally — Yahoo Finance's free data has no uptime
guarantee and can rate-limit).

### Market status banner

A small line under the header shows each tracked market's state, e.g.
`🇮🇳 Open   🇺🇸 Closed`. This accounts for:
- **Weekends** (both markets)
- **Official trading holidays** — the actual 2026 calendars for NSE and
  NYSE/Nasdaq, not just a weekday check (see `markets.py`)
- **Regular trading hours** — 9:15 AM–3:30 PM IST for NSE, 9:30 AM–4:00 PM
  ET for NYSE/Nasdaq

**This needs updating every year.** `markets.py` hardcodes the 2026 holiday
calendars (festival dates like Diwali and Holi shift annually and can't be
computed from a formula, so there's no way around maintaining this by hand).
If you run this in 2027 without updating it, the "Market status…" popup
will show a ⚠ warning that no holiday calendar is loaded for that year, and
the app falls back to a weekday-only check — it won't know about holidays,
but weekends and trading hours still work correctly.

## Making it a real standalone app (recommended)

Running `widget.py` from VS Code's terminal ties it to VS Code — closing VS
Code kills the whole process tree underneath it, widget included. The fix
is to stop running it as a script and build it into an actual `.app` you
launch by double-clicking, independent of any editor or terminal.

```bash
source .venv/bin/activate
python3 -m pip install pyinstaller
pyinstaller --windowed --name "WatchlistPeek" --add-data "schema.sql:." widget.py
```

This creates `dist/WatchlistPeek.app`. Drag it into **Applications**, then
double-click it like any other app. It keeps running even if VS Code, the
terminal, and everything else is closed, and quits only when you quit it
(right-click the widget → Quit).

The database lives at `~/Library/Application Support/WatchlistPeek/tracker.db`,
not inside the project folder — this is required for a packaged app (its own
folder isn't reliably writable) and is also just the correct place for it.

> **Renamed from an earlier "NiftyTracker" build?** If you have an existing
> database at `~/Library/Application Support/NiftyTracker/tracker.db` and
> want to keep that watchlist/history, move it:
> ```bash
> mkdir -p ~/Library/"Application Support"/WatchlistPeek
> mv ~/Library/"Application Support"/NiftyTracker/tracker.db \
>    ~/Library/"Application Support"/WatchlistPeek/
> ```

**To launch it automatically at login:** System Settings → General → Login
Items → add `WatchlistPeek.app`.

**Rebuilding after you edit the code:** re-run the `pyinstaller` command
above, then replace the old copy:
```bash
rm -rf /Applications/WatchlistPeek.app
mv dist/WatchlistPeek.app /Applications/
```
Editing the `.py` files does **not** update an already-built `.app` — it's a
frozen snapshot of the code at build time, so changes only take effect after
a rebuild.

**If macOS blocks it** the first time ("WatchlistPeek can't be opened
because it is from an unidentified developer"), right-click the app → Open,
then confirm. This is normal for locally-built, unsigned apps and only
needs doing once.

**Housekeeping after a build:** `build/` is intermediate scratch output, not
something you run directly (running the executable inside it will fail with
a "Failed to load Python shared library" error) — the real output is
`dist/WatchlistPeek.app`. Both `build/` and `dist/` are safe to delete once
the app is installed in `/Applications`; `pyinstaller` regenerates them.

## How it's built

- **`widget.py`** — the floating window (`tkinter`, borderless, always-on-top,
  draggable). Refreshes on a background thread so the UI never freezes.
- **`fetcher.py`** — pulls prices via `yfinance`, with retries and a cached
  last-good-value fallback per symbol. Reports each quote's currency so the
  widget can show ₹, $, etc. correctly.
- **`markets.py`** — trading hours and holiday calendars for NSE and
  NYSE/Nasdaq, and which market a given symbol belongs to.
- **`db.py`** / **`schema.sql`** — SQLite database. `watchlist` holds the
  stocks you're tracking; `price_log` records every fetch (raw data for a
  future price-history chart); `settings` stores small preferences like
  your chosen display mode.

## Troubleshooting

**Widget shows "no data" for everything.**
First isolate whether it's `yfinance`/network or this code:
```bash
python3 -c "import yfinance as yf; print(yf.Ticker('^NSEI').fast_info.last_price)"
```
- **Prints a number:** the library and network are fine. Quit the widget and
  restart it — it may have hit a transient failure before yfinance "warmed
  up". You can also run it with debug logging to see the exact cause of any
  failure in the terminal:
  ```bash
  NIFTY_DEBUG=1 python3 widget.py
  ```
- **Prints an error or nothing:** upgrade yfinance, since Yahoo's backend
  changes often enough that older versions silently break:
  ```bash
  python3 -m pip install -U yfinance
  ```
  If it still fails, you're likely being rate-limited (Yahoo throttles bursts
  of requests) — wait a few minutes, make sure only one copy of the widget
  is running, and keep the watchlist short.

**`pip install` says "command not found".**
Use the module form instead, which works regardless of how your Python was
installed:
```bash
python3 -m pip install -r requirements.txt
```

**Add/Remove dialogs open but are hidden behind the widget.**
Fixed — the popups now explicitly force themselves above the always-on-top
widget. Make sure you're running the current `widget.py`.

**Market status looks wrong for the current year.**
See "This needs updating every year" above — the holiday calendars are
hardcoded per year and must be refreshed in `markets.py` annually.

## Known limitations

- **Prices aren't true tick-by-tick real-time.** Yahoo Finance data is
  typically delayed by a few minutes. Fine for a casual watchlist; don't
  rely on it for active trading decisions.
- **No official free NSE real-time API exists**, so this uses the same
  Yahoo Finance data source most free tools use. If Yahoo rate-limits you,
  prices just go stale (marked ⚠) rather than crashing the widget.
- **Holiday calendars need annual maintenance** (see above) — they are not,
  and cannot be, computed automatically.
- **Regular trading sessions only.** NSE's occasional special sessions
  (e.g. a Budget Day session) and US pre-/post-market hours aren't modeled.
- **macOS-tested logic, not macOS-exclusive.** `tkinter` and `-topmost` work
  on Windows and Linux too, but window behavior (especially the
  overrideredirect resize workaround) is macOS-specific and may need
  adjustment on other platforms.

## Ideas to extend it

- A sparkline chart per row, drawn from `price_log`.
- A settings file for refresh interval, colors, and opacity instead of
  editing constants in `widget.py`.
- Desktop notifications when a stock crosses a price you set.
- Auto-updating holiday calendars from a maintained source instead of a
  hardcoded yearly list.
