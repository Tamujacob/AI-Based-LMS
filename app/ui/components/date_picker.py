"""
app/ui/components/date_picker.py
A clean date picker widget using tkcalendar.
Shows a text entry with a calendar button that opens a popup anchored to the button.
"""

import customtkinter as ctk
from tkcalendar import Calendar
from datetime import date
import tkinter as tk
from app.ui.styles.theme import COLORS, FONTS


class DatePicker(ctk.CTkFrame):
    """
    A date picker widget that shows:
    - A read-only text entry displaying the selected date
    - A calendar button that opens a popup anchored directly below the button

    Usage:
        picker = DatePicker(parent, label="Loan Date")
        date_value = picker.get_date()   # returns datetime.date object
        date_str   = picker.get()        # returns "YYYY-MM-DD" string
        picker.set_date(date(2025, 1, 1))
    """

    def __init__(self, master, label: str = None, initial_date: date = None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.columnconfigure(0, weight=1)
        self._selected_date = initial_date or date.today()
        self._label_text = label
        self._popup = None
        self._build()

    def _build(self):
        row = 0
        if self._label_text:
            ctk.CTkLabel(
                self, text=self._label_text,
                font=FONTS["body_small"],
                text_color=COLORS["text_secondary"],
                anchor="w"
            ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
            row = 1

        # Date display entry (read-only, styled)
        self.date_var = ctk.StringVar(value=str(self._selected_date))
        self.entry = ctk.CTkEntry(
            self,
            textvariable=self.date_var,
            state="readonly",
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            font=FONTS["body"],
            corner_radius=8,
            height=40,
            border_width=1,
        )
        self.entry.grid(row=row, column=0, sticky="ew", padx=(0, 4))

        # Calendar button — we anchor the popup to this widget
        self.cal_btn = ctk.CTkButton(
            self,
            text="📅",
            width=40, height=40,
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["accent_green_dark"],
            text_color="#FFFFFF",
            corner_radius=8,
            font=("Segoe UI Emoji", 16),
            command=self._open_calendar,
        )
        self.cal_btn.grid(row=row, column=1)

    def _open_calendar(self):
        """Open a popup calendar anchored directly below the 📅 button."""

        # If already open, close it
        if self._popup and self._popup.winfo_exists():
            self._popup.destroy()
            self._popup = None
            return

        # Force geometry update so winfo coords are accurate
        self.cal_btn.update_idletasks()

        # Use the button's screen position as anchor
        btn_x = self.cal_btn.winfo_rootx()
        btn_y = self.cal_btn.winfo_rooty()
        btn_h = self.cal_btn.winfo_height()

        popup_w = 260
        popup_h = 230

        # Determine screen size to avoid going off-screen
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        x = btn_x - popup_w + self.cal_btn.winfo_width()  # right-align to button
        y = btn_y + btn_h + 4                              # just below the button

        # Clamp to screen bounds
        x = max(0, min(x, screen_w - popup_w))
        y = max(0, min(y, screen_h - popup_h))

        popup = tk.Toplevel()
        self._popup = popup
        popup.title("")
        popup.resizable(False, False)
        popup.overrideredirect(True)        # borderless popup
        popup.configure(bg="#FFFFFF")
        popup.geometry(f"{popup_w}x{popup_h}+{x}+{y}")
        popup.grab_set()

        # Rounded container frame
        container = tk.Frame(popup, bg="#FFFFFF",
                             highlightbackground=COLORS["border"],
                             highlightthickness=1)
        container.pack(fill="both", expand=True)

        # Header bar
        header = tk.Frame(container, bg=COLORS["accent_green_dark"], height=32)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="  📅  Select Date",
                 font=("Helvetica", 10, "bold"),
                 fg="#FFFFFF", bg=COLORS["accent_green_dark"],
                 anchor="w").pack(side="left", fill="y")
        tk.Button(header, text="✕", font=("Helvetica", 10),
                  fg="#FFFFFF", bg=COLORS["accent_green_dark"],
                  activebackground=COLORS["danger"],
                  activeforeground="#FFFFFF",
                  relief="flat", bd=0, padx=8,
                  cursor="hand2",
                  command=lambda: (popup.destroy(), setattr(self, "_popup", None))
                  ).pack(side="right", fill="y")

        # tkcalendar Calendar widget (not DateEntry — full calendar view)
        cal = Calendar(
            container,
            selectmode="day",
            year=self._selected_date.year,
            month=self._selected_date.month,
            day=self._selected_date.day,
            date_pattern="yyyy-mm-dd",
            background=COLORS["accent_green"],
            foreground="#FFFFFF",
            headersbackground=COLORS["accent_green_dark"],
            headersforeground=COLORS["accent_gold"],
            selectbackground=COLORS["accent_gold"],
            selectforeground="#1A2E1A",
            normalbackground="#FFFFFF",
            normalforeground=COLORS["text_primary"],
            weekendbackground="#F4F6F4",
            weekendforeground=COLORS["accent_green_dark"],
            othermonthbackground="#ECECEC",
            othermonthforeground="#AAAAAA",
            bordercolor=COLORS["border"],
            font=("Helvetica", 9),
        )
        cal.pack(padx=8, pady=(6, 4), fill="both", expand=True)

        def confirm():
            selected_str = cal.get_date()           # returns "YYYY-MM-DD"
            y_, m_, d_ = map(int, selected_str.split("-"))
            self._selected_date = date(y_, m_, d_)
            self.date_var.set(str(self._selected_date))
            popup.destroy()
            self._popup = None

        # Confirm button
        tk.Button(
            container, text="✔  Confirm",
            bg=COLORS["accent_green"], fg="white",
            font=("Helvetica", 10, "bold"),
            activebackground=COLORS["accent_green_dark"],
            activeforeground="#FFFFFF",
            relief="flat", padx=16, pady=5,
            cursor="hand2",
            command=confirm,
        ).pack(pady=(0, 8))

        # Close popup if user clicks outside
        popup.bind("<FocusOut>", lambda e: self._close_if_focus_lost(popup))

    def _close_if_focus_lost(self, popup):
        """Destroy popup when focus moves outside it."""
        try:
            focused = popup.focus_get()
            if focused is None:
                popup.destroy()
                self._popup = None
        except Exception:
            pass

    def get_date(self) -> date:
        """Return selected date as datetime.date."""
        return self._selected_date

    def get(self) -> str:
        """Return selected date as YYYY-MM-DD string."""
        return str(self._selected_date)

    def set_date(self, d: date):
        """Set the date programmatically."""
        self._selected_date = d
        self.date_var.set(str(d))