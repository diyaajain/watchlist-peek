# NIFTY Desktop Tracker

A tiny floating widget that stays on top of every app and shows live prices
for whatever stocks or indices you're watching — no tab-switching, no manual
refresh.

## Setup

```bash
cd nifty-tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 widget.py
```

A small dark widget appears near the top-left of your screen, showing
**NIFTY 50** by default. Drag it anywhere by clicking and holding on it.

## Using it

- **Move it:** click and drag anywhere on the widget.
- **Add a stock:** right-click (or Ctrl+click on a trackpad) → "Add symbol…".
  Use a yfinance symbol:
  - Indices: `^NSEI` (NIFTY 50), `^NSEBANK` (BANK NIFTY)
  - NSE stocks: ticker + `.NS`, e.g. `RELIANCE.NS`, `TCS.NS`, `INFY.NS`, `HDFCBANK.NS`
- **Remove a stock:** right-click → "Remove symbol…", type the exact symbol.
- **Force a refresh:** right-click → "Refresh now".
- **Choose what the change shows:** right-click → "Show" → **% change**,
  **Points change**, or **Both**. Your choice is saved and remembered next
  time you open the app.
- **Quit:** right-click → "Quit", or just close the window.

It refreshes every 15 seconds while NSE is open (`REFRESH_SECONDS` in
`widget.py`), and every 3 minutes while it's closed (`REFRESH_SECONDS_CLOSED`)
since there's no point polling often when nothing's moving. Green with ▲
means up since previous close, red with ▼ means down. A ⚠ next to a price
means the live fetch failed and it's showing the last known value (this
happens occasionally — Yahoo Finance's free data has no uptime guarantee and
can rate-limit).

An **"● Markets closed"** banner appears outside NSE's regular session
(9:15 AM–3:30 PM IST, Monday–Friday). This is a fixed time check, so it does
**not** know about exchange holidays (Diwali, Republic Day, etc.) — on those
days it will say "open" when the market is actually shut.

## Making it a real standalone app (recommended)

Running `widget.py` from VS Code's terminal ties it to VS Code — closing VS
Code kills the whole process tree underneath it, widget included. The fix
is to stop running it as a script and build it into an actual `.app` you
launch by double-clicking, independent of any editor or terminal.

```bash
source .venv/bin/activate
pip install pyinstaller
pyinstaller --windowed --name "NiftyTracker" --add-data "schema.sql:." widget.py
```

This creates `dist/NiftyTracker.app`. Drag it into **Applications**, then
double-click it like any other app. It keeps running even if VS Code, the
terminal, and everything else is closed, and quits only when you quit it
(right-click the widget → Quit).

The database now lives at `~/Library/Application Support/NiftyTracker/tracker.db`,
not inside the project folder — this is required for a packaged app (its own
folder isn't reliably writable) and is also just the correct place for it.
If you already have a `tracker.db` in the project folder from running it as
a script and want to keep that history:
```bash
mkdir -p ~/Library/"Application Support"/NiftyTracker
mv tracker.db ~/Library/"Application Support"/NiftyTracker/
```

**To launch it automatically at login:** System Settings → General → Login
Items → add `NiftyTracker.app`.

**Rebuilding after you edit the code:** re-run the `pyinstaller` command
above; it overwrites `dist/NiftyTracker.app`.

**If macOS blocks it** the first time ("NiftyTracker can't be opened because
it is from an unidentified developer"), right-click the app → Open, then
confirm. This is normal for locally-built, unsigned apps and only needs
doing once.

## How it's built

- **`widget.py`** — the floating window (`tkinter`, borderless, always-on-top,
  draggable). Refreshes on a background thread so the UI never freezes.
- **`fetcher.py`** — pulls prices via `yfinance`, with retries and a cached
  last-good-value fallback per symbol.
- **`db.py`** / **`schema.sql`** — SQLite database. `watchlist` holds the
  stocks you're tracking; `price_log` records every fetch, so you already
  have the raw data for a price-history chart later.

## Troubleshooting

**Widget shows "no data" for everything.**
First isolate whether it's `yfinance`/network or this code:
```bash
python3 -c "import yfinance as yf; print(yf.Ticker('^NSEI').fast_info.last_price)"
```
- **Prints a number:** the library and network are fine. Quit the widget and
  restart it (`python3 widget.py`) — it may have hit a transient failure
  before yfinance "warmed up". You can also run it with debug logging to see
  the exact cause of any failure in the terminal:
  ```bash
  NIFTY_DEBUG=1 python3 widget.py
  ```
- **Prints an error or nothing:** upgrade yfinance, since Yahoo's backend
  changes often enough that older versions silently break:
  ```bash
  pip install -U yfinance
  ```
  If it still fails, you're likely being rate-limited (Yahoo throttles bursts
  of requests) — wait a few minutes, make sure only one copy of the widget
  is running, and keep the watchlist short.

**Add/Remove windows open but are hidden behind the widget.**
This was a bug in the first version — the popup didn't tell macOS to stay
above the always-on-top widget. It's fixed as of this version; make sure
you're running the current `widget.py`, which uses custom `ask_string` /
`ask_yes_no` dialogs instead of tkinter's default ones.

## Known limitations

- **Prices aren't true tick-by-tick real-time.** Yahoo Finance data for NSE
  is typically delayed by a few minutes. For a casual watch-list that's
  usually fine; for active trading decisions, don't rely on it.
- **No official free NSE real-time API exists**, so this uses the same
  Yahoo Finance data source most free tools use. If Yahoo rate-limits you,
  prices just go stale (marked ⚠) rather than crashing the widget.
- **macOS-tested logic, not macOS-exclusive.** `tkinter` and `-topmost` work
  on Windows and Linux too, but window behavior (especially over full-screen
  apps) can differ by OS — you may need to adjust `overrideredirect`/
  `-topmost` handling if you move platforms.

## Ideas to extend it

- A sparkline chart per row, drawn from `price_log`.
- A settings file for refresh interval, colors, and opacity instead of
  editing constants in `widget.py`.
- Desktop notifications when a stock crosses a price you set.
- Package it as a standalone `.app` with `pyinstaller` so it doesn't need a
  terminal open.
