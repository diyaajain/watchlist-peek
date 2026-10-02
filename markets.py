"""Trading hours and holiday calendars for the two markets this app tracks:
India (NSE) and the US (NYSE/Nasdaq).

Holiday dates are festival- and law-based and shift every year — they are
NOT something that can be computed from a formula (unlike, say, "last Monday
of May"). This file hardcodes the official 2026 calendars and must be
updated by hand for each new year. Sources used for 2026:
  - NSE: official circular NSE/FAOP/71777 (Dec 12, 2025), nseindia.com
  - NYSE/Nasdaq: published 2026 holiday schedule, nyse.com

If a year isn't in HOLIDAYS below, this code quietly falls back to a
weekday-only check (no holiday awareness) for that year — see
`market_status_detail`'s `has_holiday_data` field.
"""
from datetime import date, datetime, time as dtime
from zoneinfo import ZoneInfo

MARKET_IN = "IN"
MARKET_US = "US"

MARKET_NAME = {
    MARKET_IN: "India (NSE)",
    MARKET_US: "US (NYSE/Nasdaq)",
}
MARKET_FLAG = {
    MARKET_IN: "🇮🇳",
    MARKET_US: "🇺🇸",
}
MARKET_TZ = {
    MARKET_IN: ZoneInfo("Asia/Kolkata"),
    MARKET_US: ZoneInfo("America/New_York"),
}
# Regular trading session only — doesn't account for NSE's occasional special
# sessions (e.g. Budget Day) or US pre/post-market hours.
MARKET_HOURS = {
    MARKET_IN: (dtime(9, 15), dtime(15, 30)),
    MARKET_US: (dtime(9, 30), dtime(16, 0)),
}

HOLIDAYS: dict[str, dict[int, dict[date, str]]] = {
    MARKET_IN: {
        2026: {
            date(2026, 1, 26): "Republic Day",
            date(2026, 3, 3): "Holi",
            date(2026, 3, 26): "Shri Ram Navami",
            date(2026, 3, 31): "Shri Mahavir Jayanti",
            date(2026, 4, 3): "Good Friday",
            date(2026, 4, 14): "Dr. Ambedkar Jayanti",
            date(2026, 5, 1): "Maharashtra Day",
            date(2026, 5, 28): "Bakri Id",
            date(2026, 6, 26): "Muharram",
            date(2026, 9, 14): "Ganesh Chaturthi",
            date(2026, 10, 2): "Gandhi Jayanti",
            date(2026, 10, 20): "Dussehra",
            date(2026, 11, 10): "Diwali (Balipratipada)",
            date(2026, 11, 24): "Guru Nanak Jayanti",
            date(2026, 12, 25): "Christmas",
        },
    },
    MARKET_US: {
        2026: {
            date(2026, 1, 1): "New Year's Day",
            date(2026, 1, 19): "Martin Luther King Jr. Day",
            date(2026, 2, 16): "Washington's Birthday",
            date(2026, 4, 3): "Good Friday",
            date(2026, 5, 25): "Memorial Day",
            date(2026, 6, 19): "Juneteenth",
            date(2026, 7, 3): "Independence Day (observed)",
            date(2026, 9, 7): "Labor Day",
            date(2026, 11, 26): "Thanksgiving Day",
            date(2026, 12, 25): "Christmas Day",
        },
    },
}


def market_for_symbol(symbol: str) -> str:
    """NSE symbols use a .NS/.BO suffix or an ^NSE.../^BSE... index prefix.
    Everything else (AAPL, MSFT, ^GSPC, ^DJI, ...) is treated as US."""
    s = symbol.strip().upper()
    if s.endswith(".NS") or s.endswith(".BO") or s.startswith("^NSE") or s.startswith("^BSE"):
        return MARKET_IN
    return MARKET_US


def _holiday_on(market: str, d: date) -> str | None:
    return HOLIDAYS.get(market, {}).get(d.year, {}).get(d)


def has_holiday_data(market: str, year: int) -> bool:
    return year in HOLIDAYS.get(market, {})


def market_status_detail(market: str, now: datetime | None = None) -> dict:
    """Everything the UI needs for one market: whether it's open right now,
    the reason if it's closed, and a formatted local time."""
    tz = MARKET_TZ[market]
    now = now.astimezone(tz) if now else datetime.now(tz)
    holiday = _holiday_on(market, now.date())

    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        open_now, label = False, "Closed (weekend)"
    elif holiday:
        open_now, label = False, f"Closed — {holiday}"
    else:
        open_t, close_t = MARKET_HOURS[market]
        open_now = open_t <= now.time() <= close_t
        label = "Open" if open_now else "Closed (outside trading hours)"

    return {
        "market": market,
        "open": open_now,
        "holiday": holiday,
        "label": label,
        "local_time": now.strftime("%I:%M %p %Z"),
        "has_holiday_data": has_holiday_data(market, now.year),
    }


def is_market_open(market: str, now: datetime | None = None) -> bool:
    return market_status_detail(market, now)["open"]
