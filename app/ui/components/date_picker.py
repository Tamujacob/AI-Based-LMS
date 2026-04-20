"""
app/ui/components/date_picker.py
A clean date picker widget using tkcalendar.
Shows a text entry with a calendar button.
"""

import customtkinter as ctk
from tkcalendar import DateEntry
from datetime import date
import tkinter as tk
from app.ui.styles.theme import COLORS, FONTS


class DatePicker(ctk.CTkFrame):
    """
    A date picker widget that shows:
    - A text entry displaying the selected date
    - A small calendar button that opens a popup calendar
    
    Usage:
        picker = DatePicker(parent, label="Loan Date")
        date_value = picker.get_date()   # returns datetime.date object
        date_str = picker.get()          # returns "YYYY-MM-DD" string
        picker.set_date(date(2025, 1, 1))
    """

    def __init__(self, master, label: str = None, initial_date: date = None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.columnconfigure(0, weight=1)
        self._selected_date = initial_date or date.today()
        self._label_text = label
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

        # Calendar button
        self.cal_btn = ctk.CTkButton(
            self,
            text="📅",
            width=40, height=40,
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["accent_green_dark"],
            text_color="#FFFFFF",
            corner_radius=8,
            font=("Helvetica", 16),
            command=self._open_calendar,
        )
        self.cal_btn.grid(row=row, column=1)

    def _open_calendar(self):
        """Open a popup calendar window."""
        popup = tk.Toplevel()
        popup.title("Select Date")
        popup.resizable(False, False)
        popup.configure(bg="#FFFFFF")
        popup.grab_set()  # Modal

        # Position near the button
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 4
        popup.geometry(f"280x220+{x}+{y}")

        # Header
        tk.Label(popup, text="Select Date",
                 font=("Helvetica", 12, "bold"),
                 fg="#1A5C1E", bg="#FFFFFF").pack(pady=(12, 4))

        # Calendar widget
        cal = DateEntry(
            popup,
            width=18,
            background="#34A038",
            foreground="#FFFFFF",
            borderwidth=0,
            year=self._selected_date.year,
            month=self._selected_date.month,
            day=self._selected_date.day,
            date_pattern="yyyy-mm-dd",
            font=("Helvetica", 11),
        )
        cal.pack(padx=20, pady=8)

        def confirm():
            selected = cal.get_date()
            self._selected_date = selected
            self.date_var.set(str(selected))
            popup.destroy()

        # Confirm button
        tk.Button(
            popup, text="Confirm",
            bg="#34A038", fg="white",
            font=("Helvetica", 11, "bold"),
            relief="flat", padx=20, pady=6,
            cursor="hand2",
            command=confirm,
        ).pack(pady=8)

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