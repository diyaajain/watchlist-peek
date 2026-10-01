"""A small, draggable, always-on-top widget showing live prices.

Run:
    python3 widget.py
Right-click the widget for options (add symbol, remove symbol, refresh now, quit).
Left-click and drag anywhere on the widget to move it.
"""

import threading
import time
import tkinter as tk
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import db
import fetcher


IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = dtime(9, 15)
MARKET_CLOSE = dtime(15, 30)


def is_market_open(now: datetime | None = None) -> bool:
    """NSE's regular trading session: 9:15-15:30 IST, Monday-Friday.

    Doesn't account for exchange holidays (Diwali, Republic Day, etc.) —
    on those days this will say 'open' when the market is actually shut.
    """
    now = now or datetime.now(IST)

    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False

    return MARKET_OPEN <= now.time() <= MARKET_CLOSE


def ask_string(parent, title, prompt) -> str | None:
    """A text-input popup that forces itself above the always-on-top widget.

    tkinter's built-in simpledialog does NOT do this, which is why it used
    to appear hidden behind the widget.
    """
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.resizable(False, False)
    dialog.transient(parent)

    tk.Label(
        dialog,
        text=prompt,
        padx=12
    ).pack(pady=(10, 0))

    entry = tk.Entry(dialog, width=32)
    entry.pack(padx=12, pady=10)

    result: dict = {"value": None}

    def confirm(event=None):
        result["value"] = entry.get()
        dialog.destroy()

    def cancel(event=None):
        dialog.destroy()

    btns = tk.Frame(dialog)
    btns.pack(pady=(0, 10))

    tk.Button(
        btns,
        text="OK",
        command=confirm,
        width=8
    ).pack(side="left", padx=5)

    tk.Button(
        btns,
        text="Cancel",
        command=cancel,
        width=8
    ).pack(side="left")

    entry.bind("<Return>", confirm)
    dialog.bind("<Escape>", cancel)

    dialog.update_idletasks()

    x = parent.winfo_x() + 30
    y = parent.winfo_y() + 30

    dialog.geometry(f"+{x}+{y}")
    dialog.attributes("-topmost", True)
    dialog.lift()
    dialog.focus_force()
    entry.focus_set()
    dialog.grab_set()

    parent.wait_window(dialog)

    return result["value"]


def ask_yes_no(parent, title, prompt) -> bool:
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.resizable(False, False)
    dialog.transient(parent)

    tk.Label(
        dialog,
        text=prompt,
        padx=12,
        pady=12,
        wraplength=260,
        justify="left"
    ).pack()

    result: dict = {"value": False}

    def yes():
        result["value"] = True
        dialog.destroy()

    def no():
        dialog.destroy()

    btns = tk.Frame(dialog)
    btns.pack(pady=(0, 10))

    tk.Button(
        btns,
        text="Yes",
        command=yes,
        width=8
    ).pack(side="left", padx=5)

    tk.Button(
        btns,
        text="No",
        command=no,
        width=8
    ).pack(side="left")

    dialog.update_idletasks()

    x = parent.winfo_x() + 30
    y = parent.winfo_y() + 30

    dialog.geometry(f"+{x}+{y}")
    dialog.attributes("-topmost", True)
    dialog.lift()
    dialog.focus_force()
    dialog.grab_set()

    parent.wait_window(dialog)

    return result["value"]


REFRESH_SECONDS = 15
REFRESH_SECONDS_CLOSED = 180

BG = "#0a0a0a"
FG = "#e6e6e6"
GREEN = "#3ddc84"
RED = "#ff5c5c"
GREY = "#8a8a8a"
CLOSED_COLOR = "#d9a441"

FONT_SYMBOL = ("SF Pro Text", 11, "bold")
FONT_PRICE = ("SF Pro Text", 11)


class TickerWidget(tk.Tk):

    def __init__(self):
        super().__init__()

        db.init_db()

        # No title bar / window chrome
        self.overrideredirect(True)

        # Always on top
        self.attributes("-topmost", True)

        try:
            self.attributes("-alpha", 0.85)
        except tk.TclError:
            pass

        self.configure(bg=BG)

        # Initial position
        self.geometry("+40+40")

        self.rows: dict[str, dict] = {}
        self._last_quotes: dict[str, dict] = {}

        self.display_mode = tk.StringVar(
            value=db.get_setting("display_mode", "pct")
        )

        self._build_ui()
        self._bind_drag()
        self._bind_menu()

        self._stop = False

        self.protocol(
            "WM_DELETE_WINDOW",
            self.quit_app
        )

        threading.Thread(
            target=self._refresh_loop,
            daemon=True
        ).start()

    # ---------- UI ----------

    def _build_ui(self):

        header = tk.Frame(
            self,
            bg=BG
        )

        header.pack(
            fill="x",
            padx=8,
            pady=(6, 2)
        )

        tk.Label(
            header,
            text="● WATCHLIST",
            bg=BG,
            fg=GREY,
            font=("SF Pro Text", 9, "bold")
        ).pack(side="left")

        self.status_lbl = tk.Label(
            header,
            text="",
            bg=BG,
            fg=GREY,
            font=("SF Pro Text", 8)
        )

        self.status_lbl.pack(side="right")

        self.date_lbl = tk.Label(
        self,
        text=time.strftime("%B %d, %Y"),
        bg=BG,
        fg=GREY,
        font=("SF Pro Text", 8),
        anchor="w"
        )

        self.date_lbl.pack(
            fill="x",
            padx=8,
            pady=(1, 1)
        )

        self.banner_lbl = tk.Label(
            self,
            text="",
            bg=BG,
            fg=CLOSED_COLOR,
            font=("SF Pro Text", 8, "italic"),
            anchor="center",
            justify="center"
        )

        self.banner_lbl.pack(
            fill="x",
            padx=8,
            pady=(0, 4)
        )

        self.list_frame = tk.Frame(
            self,
            bg=BG
        )

        self.list_frame.pack(
            fill="both",
            padx=8,
            pady=(0, 6)
        )

        self._rebuild_rows()

        tk.Label(
            self,
            text="Data: Yahoo Finance (yfinance) · may be delayed",
            bg=BG,
            fg=GREY,
            font=("SF Pro Text", 7)
        ).pack(
            fill="x",
            padx=8,
            pady=(0, 5)
        )

    def _rebuild_rows(self):

        for child in self.list_frame.winfo_children():
            child.destroy()

        self.rows.clear()

        for item in db.get_watchlist():

            row = tk.Frame(
                self.list_frame,
                bg=BG
            )

            row.pack(
                fill="x",
                pady=1
            )

            # No fixed width — let Tkinter size this from the actual text.
            name_lbl = tk.Label(
                row,
                text=item["display_name"],
                bg=BG,
                fg=FG,
                font=FONT_SYMBOL,
                anchor="w"
            )

            name_lbl.pack(
                side="left"
            )

            # No fixed width — this allows the widget to grow/shrink
            # depending on the current price/change text.
            price_lbl = tk.Label(
                row,
                text="…",
                bg=BG,
                fg=GREY,
                font=FONT_PRICE,
                anchor="e",
                padx=10
            )

            price_lbl.pack(
                side="right"
            )

            self.rows[item["symbol"]] = {
                "price_lbl": price_lbl,
                "name_lbl": name_lbl
            }

        self._resize_to_fit()

    def _resize_to_fit(self):
        """Resize the borderless widget to its current content size.

        Tkinter can be stubborn about resizing an overrideredirect window on
        macOS, so briefly disabling overrideredirect forces the new natural
        size to be applied.
        """

        # Let all labels/frames calculate their current requested size.
        self.update_idletasks()

        x = self.winfo_x()
        y = self.winfo_y()

        # Briefly turn normal window behavior back on so Tk recalculates
        # the requested size correctly.
        self.overrideredirect(False)
        self.update_idletasks()

        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()

        self.geometry(
            f"{w}x{h}+{x}+{y}"
        )

        # Return to the borderless widget.
        self.overrideredirect(True)

        # Re-assert always-on-top after toggling.
        self.attributes("-topmost", True)

        self.update_idletasks()

    # ---------- dragging ----------

    def _bind_drag(self):

        self._drag = {
            "x": 0,
            "y": 0
        }

        for widget in (self,):

            widget.bind(
                "<ButtonPress-1>",
                self._drag_start
            )

            widget.bind(
                "<B1-Motion>",
                self._drag_move
            )

    def _drag_start(self, event):

        self._drag["x"] = event.x
        self._drag["y"] = event.y

    def _drag_move(self, event):

        x = (
            self.winfo_pointerx()
            - self._drag["x"]
        )

        y = (
            self.winfo_pointery()
            - self._drag["y"]
        )

        self.geometry(
            f"+{x}+{y}"
        )

    # ---------- right-click menu ----------

    def _bind_menu(self):

        menu = tk.Menu(
            self,
            tearoff=0
        )

        menu.add_command(
            label="Add symbol…",
            command=self.add_symbol_dialog
        )

        menu.add_command(
            label="Remove symbol…",
            command=self.remove_symbol_dialog
        )

        menu.add_command(
            label="Refresh now",
            command=lambda: threading.Thread(
                target=self._refresh_once,
                daemon=True
            ).start()
        )

        menu.add_separator()

        display_menu = tk.Menu(
            menu,
            tearoff=0
        )

        for value, label in [
            ("pct", "% change"),
            ("points", "Points change"),
            ("both", "Both")
        ]:

            display_menu.add_radiobutton(
                label=label,
                value=value,
                variable=self.display_mode,
                command=self._on_display_mode_changed
            )

        menu.add_cascade(
            label="Show",
            menu=display_menu
        )

        menu.add_separator()

        menu.add_command(
            label="Quit",
            command=self.quit_app
        )

        self.bind(
            "<Button-2>",
            lambda e: menu.tk_popup(
                e.x_root,
                e.y_root
            )
        )

        self.bind(
            "<Button-3>",
            lambda e: menu.tk_popup(
                e.x_root,
                e.y_root
            )
        )

        self.bind(
            "<Control-Button-1>",
            lambda e: menu.tk_popup(
                e.x_root,
                e.y_root
            )
        )

    def _on_display_mode_changed(self):

        db.set_setting(
            "display_mode",
            self.display_mode.get()
        )

        if self._last_quotes:

            self._render(
                self._last_quotes
            )

    # ---------- adding/removing symbols ----------

    def add_symbol_dialog(self):

        symbol = ask_string(
            self,
            "Add symbol",
            "yfinance symbol, e.g. RELIANCE.NS, TCS.NS, AAPL, MSFT:"
        )

        if not symbol:
            return

        name = ask_string(
            self,
            "Add symbol",
            "Display name (short):"
        ) or symbol

        symbol = symbol.strip().upper()

        quote = fetcher.fetch_quotes(
            [symbol]
        )[symbol]

        if quote["price"] is None:

            if not ask_yes_no(
                self,
                "Symbol not found",
                f"Couldn't fetch a price for {symbol}.\n\n"
                f"Double-check the yfinance symbol. "
                f"Examples: RELIANCE.NS for India, "
                f"AAPL for the US. Add it anyway?"
            ):
                return

        db.add_symbol(
            symbol,
            name
        )

        self._rebuild_rows()

        threading.Thread(
            target=self._refresh_once,
            daemon=True
        ).start()

    def remove_symbol_dialog(self):

        current = db.get_watchlist()

        if not current:
            return

        names = "\n".join(
            f"{r['symbol']}  ({r['display_name']})"
            for r in current
        )

        symbol = ask_string(
            self,
            "Remove symbol",
            f"Type the exact symbol to remove:\n\n{names}"
        )

        if symbol:

            db.remove_symbol(
                symbol.strip().upper()
            )

            self._rebuild_rows()

    # ---------- refresh ----------

    def _refresh_once(self):

        symbols = [
            r["symbol"]
            for r in db.get_watchlist()
        ]

        if not symbols:
            return

        quotes = fetcher.fetch_quotes(
            symbols
        )

        db.log_prices(
            quotes
        )

        self.after(
            0,
            self._render,
            quotes
        )

    def _format_change(self, q: dict) -> str:

        mode = self.display_mode.get()

        if mode == "points":
            return f"({q['change']:+.2f})"

        if mode == "both":
            return (
                f"({q['change']:+.2f} / "
                f"{q['pct_change']:+.2f}%)"
            )

        return f"({q['pct_change']:+.2f}%)"

    @staticmethod
    def _format_price(q: dict) -> str:

        currency = q.get(
            "currency",
            "USD"
        )

        symbol = {
            "INR": "₹",
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "JPY": "¥",
        }.get(
            currency,
            f"{currency} "
        )

        return f"{symbol}{q['price']:,.2f}"

    def _render(self, quotes: dict[str, dict]):

        self._last_quotes = quotes

        any_stale = False

        for symbol, q in quotes.items():

            widgets = self.rows.get(symbol)

            if not widgets:
                continue

            if q["price"] is None:

                widgets["price_lbl"].config(
                    text="no data",
                    fg=GREY
                )

                continue

            arrow = (
                "▲"
                if q["change"] >= 0
                else "▼"
            )

            color = (
                GREEN
                if q["change"] >= 0
                else RED
            )

            text = (
                f"{arrow} "
                f"{self._format_price(q)}  "
                f"{self._format_change(q)}"
            )

            if q["stale"]:

                text += " ⚠"
                any_stale = True

            widgets["price_lbl"].config(
                text=text,
                fg=color
            )

        self.status_lbl.config(
            text=(
                "stale"
                if any_stale
                else time.strftime("%H:%M:%S") + " / " + time.strftime("%I:%M:%S %p")
            )
        )

        # Recalculate widget size after changing text.
        self._resize_to_fit()

    def _update_banner(self, open_now: bool):

        self.banner_lbl.config(
            text=
            (
                "● Market open · Live prices"
                if open_now
                else "● Markets closed · Showing last available price"
            )
        )

    def _refresh_loop(self):

        while not self._stop:

            open_now = is_market_open()

            self.after(
                0,
                self._update_banner,
                open_now
            )

            self._refresh_once()

            time.sleep(
                REFRESH_SECONDS
                if open_now
                else REFRESH_SECONDS_CLOSED
            )

    def quit_app(self):

        self._stop = True
        self.destroy()


if __name__ == "__main__":

    app = TickerWidget()
    app.mainloop()