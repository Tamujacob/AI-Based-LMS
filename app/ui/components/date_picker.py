"""
app/ui/components/date_picker.py
Pure-tkinter calendar popup. No tkcalendar dependency.
"""

import tkinter as tk
import customtkinter as ctk
from datetime import date
import calendar
from app.ui.styles.theme import COLORS, FONTS

_GREEN_DARK = "#1A5C1E"
_GREEN      = "#34A038"
_GOLD       = "#D4A820"
_WHITE      = "#FFFFFF"
_TEXT       = "#1A2E1A"
_HOVER_BG   = "#C8DFC8"
_TODAY_BG   = "#D4A820"
_SEL_BG     = "#34A038"


class DatePicker(ctk.CTkFrame):
    def __init__(self, master, label: str = None,
                 initial_date: date = None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.columnconfigure(0, weight=1)
        self._selected_date = initial_date or date.today()
        self._popup = None

        row = 0
        if label:
            ctk.CTkLabel(self, text=label,
                         font=FONTS["body_small"],
                         text_color=COLORS["text_secondary"],
                         anchor="w").grid(row=0, column=0, columnspan=2,
                                          sticky="w", pady=(0, 4))
            row = 1

        self.date_var = ctk.StringVar(value=str(self._selected_date))
        self.entry = ctk.CTkEntry(
            self, textvariable=self.date_var, state="readonly",
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONTS["body"],
            corner_radius=8, height=40, border_width=1)
        self.entry.grid(row=row, column=0, sticky="ew", padx=(0, 4))

        self.cal_btn = ctk.CTkButton(
            self, text="📅", width=40, height=40,
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["accent_green_dark"],
            text_color=_WHITE, corner_radius=8,
            font=("Segoe UI Emoji", 16),
            command=self._toggle_calendar)
        self.cal_btn.grid(row=row, column=1)

    def _toggle_calendar(self):
        if self._popup and self._popup.winfo_exists():
            self._popup.destroy()
            self._popup = None
            return
        self._open_calendar()

    def _open_calendar(self):
        # Force accurate widget geometry before reading coords
        self.update_idletasks()

        btn_x = self.cal_btn.winfo_rootx()
        btn_y = self.cal_btn.winfo_rooty()
        btn_h = self.cal_btn.winfo_height()
        btn_w = self.cal_btn.winfo_width()

        PW, PH = 280, 300
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        x = btn_x + btn_w - PW
        y = btn_y + btn_h + 4
        x = max(0, min(x, sw - PW))
        y = max(0, min(y, sh - PH))

        popup = tk.Toplevel(self.winfo_toplevel())
        self._popup = popup
        popup.overrideredirect(True)
        popup.configure(bg="#C8DFC8")

        # Place and make visible BEFORE grab_set
        popup.geometry(f"{PW}x{PH}+{x}+{y}")
        popup.lift()
        popup.focus_force()
        popup.update_idletasks()   # ← ensure window is viewable
        popup.grab_set()           # ← now safe to grab

        # 1-px border via outer padding frame
        outer = tk.Frame(popup, bg="#C8DFC8", padx=1, pady=1)
        outer.pack(fill="both", expand=True)

        inner = tk.Frame(outer, bg=_WHITE)
        inner.pack(fill="both", expand=True)

        # Header
        hdr = tk.Frame(inner, bg=_GREEN_DARK, height=36)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        self._view_date = date(self._selected_date.year,
                               self._selected_date.month, 1)

        self._month_label = tk.Label(
            hdr, text="", bg=_GREEN_DARK, fg=_GOLD,
            font=("Helvetica", 10, "bold"))
        self._month_label.pack(side="left", padx=(10, 0), fill="y")

        tk.Button(
            hdr, text="✕", bg=_GREEN_DARK, fg=_WHITE,
            activebackground="#C0392B", activeforeground=_WHITE,
            relief="flat", bd=0, padx=8, cursor="hand2",
            font=("Helvetica", 10),
            command=lambda: self._close(popup),
        ).pack(side="right", fill="y")

        # Prev / Next
        nav = tk.Frame(inner, bg=_WHITE, pady=4)
        nav.pack(fill="x")
        tk.Button(nav, text="◀", bg=_WHITE, fg=_GREEN,
                  activebackground=_HOVER_BG, relief="flat", bd=0,
                  font=("Helvetica", 11, "bold"), cursor="hand2",
                  command=lambda: self._shift(-1)).pack(side="left", padx=10)
        tk.Button(nav, text="▶", bg=_WHITE, fg=_GREEN,
                  activebackground=_HOVER_BG, relief="flat", bd=0,
                  font=("Helvetica", 11, "bold"), cursor="hand2",
                  command=lambda: self._shift(1)).pack(side="right", padx=10)

        # Day-of-week headers
        dow = tk.Frame(inner, bg=_GREEN_DARK)
        dow.pack(fill="x", padx=8)
        for i, d in enumerate(["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]):
            tk.Label(dow, text=d, bg=_GREEN_DARK, fg=_GOLD,
                     font=("Helvetica", 9, "bold"),
                     width=3, anchor="center").grid(
                row=0, column=i, padx=1, pady=3)

        # Day grid
        self._grid = tk.Frame(inner, bg=_WHITE)
        self._grid.pack(fill="both", expand=True, padx=8, pady=4)

        # Confirm
        tk.Button(
            inner, text="✔  Confirm",
            bg=_GREEN, fg=_WHITE,
            activebackground=_GREEN_DARK, activeforeground=_WHITE,
            relief="flat", bd=0, padx=16, pady=6,
            font=("Helvetica", 10, "bold"), cursor="hand2",
            command=lambda: self._confirm(popup),
        ).pack(pady=(0, 8))

        self._render_grid()

    def _render_grid(self):
        for w in self._grid.winfo_children():
            w.destroy()

        vd    = self._view_date
        today = date.today()
        self._month_label.configure(
            text=f"  {calendar.month_name[vd.month]}  {vd.year}")

        for r, week in enumerate(calendar.monthcalendar(vd.year, vd.month)):
            for c, day in enumerate(week):
                if day == 0:
                    tk.Label(self._grid, text="", bg=_WHITE,
                             width=3, height=1).grid(
                        row=r, column=c, padx=1, pady=1)
                    continue

                d           = date(vd.year, vd.month, day)
                is_sel      = (d == self._selected_date)
                is_today    = (d == today)

                if is_sel:
                    bg, fg, weight = _SEL_BG, _WHITE, "bold"
                elif is_today:
                    bg, fg, weight = _TODAY_BG, _WHITE, "bold"
                else:
                    bg, fg, weight = _WHITE, _TEXT, "normal"

                tk.Button(
                    self._grid, text=str(day),
                    bg=bg, fg=fg,
                    activebackground=_HOVER_BG, activeforeground=_TEXT,
                    relief="flat", bd=0, cursor="hand2",
                    font=("Helvetica", 9, weight),
                    width=3, height=1,
                    command=lambda dd=d: self._pick(dd),
                ).grid(row=r, column=c, padx=1, pady=1)

    def _pick(self, d: date):
        self._selected_date = d
        self._render_grid()

    def _shift(self, delta: int):
        vd    = self._view_date
        month = vd.month + delta
        year  = vd.year
        if month > 12: month, year = 1, year + 1
        elif month < 1: month, year = 12, year - 1
        self._view_date = date(year, month, 1)
        self._render_grid()

    def _confirm(self, popup):
        self.date_var.set(str(self._selected_date))
        self._close(popup)

    def _close(self, popup):
        try:
            popup.grab_release()
            popup.destroy()
        except Exception:
            pass
        self._popup = None

    # Public API
    def get_date(self) -> date:
        return self._selected_date

    def get(self) -> str:
        return str(self._selected_date)

    def set_date(self, d: date):
        self._selected_date = d
        self.date_var.set(str(d))