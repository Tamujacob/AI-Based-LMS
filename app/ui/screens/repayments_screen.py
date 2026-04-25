"""
app/ui/screens/repayments_screen.py
────────────────────────────────────
Record Payment screen for Bingongold Credit LMS.

New features:
- Multi-mode loan search: by Loan Number, Client Name, or Client Phone
- Loan picker dialog when multiple loans match a client search
- Placeholder text on all labels/inputs
- Print Receipt uses themed Save dialog
- All buttons always reachable via scrollable form
"""

import threading
import customtkinter as ctk
import tkinter as tk
from datetime import date

from app.ui.styles.theme import COLORS, FONTS, primary_button_style, input_style
from app.ui.components.sidebar import Sidebar
from app.ui.components.date_picker import DatePicker
from app.ui.components.data_table import DataTable

PAYMENT_METHODS    = ["Cash", "Mobile Money", "Bank Transfer", "Cheque"]
SEARCH_MODES       = ["Loan Number", "Client Name", "Client Phone"]
_NOTES_PLACEHOLDER = "Add any relevant payment notes here..."

# Colour shortcuts
_GREEN_DARK = "#1A5C1E"
_GREEN      = "#34A038"
_WHITE      = "#FFFFFF"
_TEXT       = "#1A2E1A"
_LIGHT      = "#F4F6F4"
_BORDER     = "#C8DFC8"
_MUTED      = "#7A9A7A"


# ══════════════════════════════════════════════════════════════════════════════
# Loan picker dialog  (shown when a client name/phone matches multiple loans)
# ══════════════════════════════════════════════════════════════════════════════

class LoanPickerDialog(tk.Toplevel):
    """
    Themed dialog listing multiple loans for the user to choose from.
    Result stored in self.result (Loan object) or None if cancelled.
    """

    def __init__(self, master, loans: list, client_map: dict):
        super().__init__(master)
        self.result     = None
        self.loans      = loans
        self.client_map = client_map   # loan.client_id → client object

        self.title("Select Loan")
        self.resizable(False, False)
        self.configure(bg=_LIGHT)
        self.grab_set()

        height = min(130 + len(loans) * 54, 540)
        self.geometry(f"580x{height}")
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"580x{height}+{(sw-580)//2}+{(sh-height)//2}")

        self._build()

    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=_GREEN_DARK, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr,
                 text="💰  Multiple loans found — select one",
                 bg=_GREEN_DARK, fg=_WHITE,
                 font=("Helvetica", 12, "bold")).pack(
            side="left", padx=16, fill="y")
        tk.Button(hdr, text="✕", bg=_GREEN_DARK, fg=_WHITE,
                  activebackground="#C0392B", activeforeground=_WHITE,
                  relief="flat", bd=0, padx=14, cursor="hand2",
                  font=("Helvetica", 13),
                  command=self._cancel).pack(side="right", fill="y")

        tk.Label(self,
                 text=f"  {len(self.loans)} loans matched. Click a row to select.",
                 bg=_LIGHT, fg=_MUTED,
                 font=("Helvetica", 9)).pack(fill="x", pady=(8, 2))

        # Column headers
        col_hdr = tk.Frame(self, bg=_GREEN, height=30)
        col_hdr.pack(fill="x", padx=12)
        col_hdr.pack_propagate(False)
        for text, w in [("Loan No.", 14), ("Client", 20),
                         ("Type", 16), ("Status", 10), ("Balance", 14)]:
            tk.Label(col_hdr, text=text, bg=_GREEN, fg=_WHITE,
                     font=("Helvetica", 9, "bold"),
                     width=w, anchor="w").pack(
                side="left",
                padx=(12 if text == "Loan No." else 2, 0),
                fill="y")

        # Scrollable rows
        outer  = tk.Frame(self, bg=_BORDER, padx=1, pady=1)
        outer.pack(fill="both", expand=True, padx=12, pady=(4, 0))
        canvas = tk.Canvas(outer, bg=_WHITE, highlightthickness=0)
        sb     = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        frame  = tk.Frame(canvas, bg=_WHITE)
        win    = canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win, width=e.width))

        for i, loan in enumerate(self.loans):
            bg     = _WHITE if i % 2 == 0 else "#F0F7F0"
            client = self.client_map.get(loan.client_id)

            # Try to get balance
            try:
                from app.core.services.repayment_service import RepaymentService
                balance = RepaymentService.get_outstanding_balance(loan.id)
                bal_str = f"UGX {float(balance):,.0f}"
            except Exception:
                bal_str = "—"

            row = tk.Frame(frame, bg=bg, cursor="hand2")
            row.pack(fill="x")

            tk.Label(row, text=loan.loan_number,
                     bg=bg, fg=_TEXT,
                     font=("Helvetica", 9, "bold"),
                     width=14, anchor="w").pack(
                side="left", padx=(12, 2), pady=10)
            tk.Label(row,
                     text=client.full_name if client else "—",
                     bg=bg, fg=_MUTED,
                     font=("Helvetica", 9),
                     width=20, anchor="w").pack(side="left", padx=2)
            tk.Label(row,
                     text=loan.loan_type.value if loan.loan_type else "—",
                     bg=bg, fg=_MUTED,
                     font=("Helvetica", 9),
                     width=16, anchor="w").pack(side="left", padx=2)
            tk.Label(row,
                     text=loan.status.value.upper(),
                     bg=bg, fg=_GREEN_DARK,
                     font=("Helvetica", 9, "bold"),
                     width=10, anchor="w").pack(side="left", padx=2)
            tk.Label(row, text=bal_str,
                     bg=bg, fg=_MUTED,
                     font=("Helvetica", 9),
                     width=14, anchor="w").pack(side="left", padx=2)

            tk.Button(row, text="Select →",
                      bg=_GREEN, fg=_WHITE,
                      activebackground=_GREEN_DARK, activeforeground=_WHITE,
                      relief="flat", bd=0,
                      font=("Helvetica", 9, "bold"),
                      padx=10, pady=4, cursor="hand2",
                      command=lambda l=loan: self._select(l)).pack(
                side="right", padx=12, pady=6)

            row.bind("<Enter>",    lambda e, f=row: f.configure(bg="#D5EDD5"))
            row.bind("<Leave>",    lambda e, f=row, b=bg: f.configure(bg=b))
            row.bind("<Button-1>", lambda e, l=loan: self._select(l))

        # Cancel
        bottom = tk.Frame(self, bg=_LIGHT, pady=8)
        bottom.pack(fill="x", padx=12)
        tk.Button(bottom, text="✖  Cancel",
                  bg=_LIGHT, fg=_MUTED,
                  relief="flat", bd=1,
                  font=("Helvetica", 9),
                  padx=14, pady=5, cursor="hand2",
                  command=self._cancel).pack(side="right")

    def _select(self, loan):
        self.result = loan
        self.grab_release()
        self.destroy()

    def _cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
# Repayments screen
# ══════════════════════════════════════════════════════════════════════════════

class RepaymentsScreen(ctk.CTkFrame):
    """Main repayments screen: record payments and view history."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master        = master
        self.current_user  = master.current_user
        self.found_loan    = None
        self._last_receipt = None
        self._build()

    # ── navigation ─────────────────────────────────────────────────────────────

    def _navigate(self, screen: str):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    # ── layout ─────────────────────────────────────────────────────────────────

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        Sidebar(self, "repayments", self._navigate, self.current_user).grid(
            row=0, column=0, sticky="nsew")

        main = ctk.CTkFrame(self, fg_color=COLORS["bg_primary"])
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=2)
        main.columnconfigure(1, weight=3)
        main.rowconfigure(0, weight=1)

        self._build_payment_form(main)
        self._build_history_panel(main)

    # ── payment form ───────────────────────────────────────────────────────────

    def _build_payment_form(self, parent):
        form = ctk.CTkScrollableFrame(
            parent,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"],
            scrollbar_button_color=COLORS["accent_green"],
            scrollbar_button_hover_color=COLORS["accent_green_dark"],
        )
        form.grid(row=0, column=0, sticky="nsew", padx=(24, 8), pady=24)
        form.columnconfigure(0, weight=1)

        # ── Title ──────────────────────────────────────────────────────────────
        ctk.CTkLabel(form, text="Record Payment",
                     font=FONTS["subtitle"],
                     text_color=COLORS["accent_green_dark"]).pack(
            anchor="w", padx=20, pady=(20, 4))
        ctk.CTkLabel(
            form,
            text="Search for a loan, enter payment details, then confirm.",
            font=FONTS["body_small"],
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", padx=20, pady=(0, 12))

        self._divider(form)

        # ── Loan search mode selector ──────────────────────────────────────────
        self._field_label(form, "Search Loan By")

        mode_row = ctk.CTkFrame(form, fg_color="transparent")
        mode_row.pack(fill="x", padx=20, pady=(0, 8))
        mode_row.columnconfigure(0, weight=1)

        self.search_mode_var = ctk.StringVar(value="Loan Number")
        self.search_mode_menu = ctk.CTkOptionMenu(
            mode_row,
            variable=self.search_mode_var,
            values=SEARCH_MODES,
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_green"],
            button_hover_color=COLORS["accent_green_dark"],
            text_color=COLORS["text_primary"],
            font=FONTS["body_small"],
            corner_radius=6,
            command=self._on_search_mode_change,
        )
        self.search_mode_menu.grid(row=0, column=0, sticky="ew")

        # ── Search input (label + entry change with mode) ─────────────────────
        self.search_label_var = ctk.StringVar(value="Loan Number *")
        self.search_label_widget = ctk.CTkLabel(
            form,
            textvariable=self.search_label_var,
            font=FONTS["body_small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        self.search_label_widget.pack(fill="x", padx=20, pady=(4, 2))

        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(
            form,
            textvariable=self.search_var,
            placeholder_text="e.g. BG-2026-00123",
            **input_style(),
        )
        self.search_entry.pack(fill="x", padx=20, pady=(0, 6))
        self.search_entry.bind("<Return>", lambda e: self._find_loan())

        ctk.CTkButton(
            form,
            text="🔍  Find Loan",
            height=36,
            font=FONTS["body_small"],
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["accent_green_dark"],
            text_color=_WHITE,
            corner_radius=6,
            command=self._find_loan,
        ).pack(anchor="w", padx=20, pady=(0, 10))

        # Loan info card
        self.loan_info = ctk.CTkFrame(
            form, fg_color=COLORS["bg_input"], corner_radius=8)
        self.loan_info.pack(fill="x", padx=20, pady=(0, 4))
        self.loan_info_label = ctk.CTkLabel(
            self.loan_info,
            text="Search by loan number, client name, or phone number above.",
            font=FONTS["body_small"],
            text_color=COLORS["text_muted"],
            wraplength=300,
            justify="left",
        )
        self.loan_info_label.pack(padx=14, pady=12, anchor="w")

        self._divider(form)

        # ── Amount ─────────────────────────────────────────────────────────────
        self._field_label(form, "Amount Paid (UGX) *")
        self.amount_var = ctk.StringVar()
        ctk.CTkEntry(
            form,
            textvariable=self.amount_var,
            placeholder_text="e.g. 500,000",
            **input_style(),
        ).pack(fill="x", padx=20, pady=(0, 10))

        # ── Payment date ───────────────────────────────────────────────────────
        self._field_label(form, "Payment Date *")
        date_row = ctk.CTkFrame(form, fg_color="transparent")
        date_row.pack(fill="x", padx=20, pady=(0, 10))
        date_row.columnconfigure(0, weight=1)
        self.payment_date_picker = DatePicker(date_row, initial_date=date.today())
        self.payment_date_picker.grid(row=0, column=0, sticky="ew")

        # ── Payment method ─────────────────────────────────────────────────────
        self._field_label(form, "Payment Method *")
        self.method_var = ctk.StringVar(value="Cash")
        ctk.CTkOptionMenu(
            form,
            variable=self.method_var,
            values=PAYMENT_METHODS,
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_green"],
            button_hover_color=COLORS["accent_green_dark"],
            text_color=COLORS["text_primary"],
            font=FONTS["body_small"],
            corner_radius=6,
        ).pack(fill="x", padx=20, pady=(0, 10))

        # ── Transaction reference ──────────────────────────────────────────────
        self._field_label(form, "Transaction Reference  (optional)")
        self.ref_var = ctk.StringVar()
        ctk.CTkEntry(
            form,
            textvariable=self.ref_var,
            placeholder_text="e.g. MTN-MM-987654 or bank reference number",
            **input_style(),
        ).pack(fill="x", padx=20, pady=(0, 10))

        # ── Notes ──────────────────────────────────────────────────────────────
        self._field_label(form, "Notes  (optional)")
        self.notes_box = ctk.CTkTextbox(
            form,
            height=68,
            fg_color=COLORS["bg_input"],
            text_color=COLORS["text_muted"],
            font=FONTS["body"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=6,
        )
        self.notes_box.pack(fill="x", padx=20, pady=(0, 4))
        self.notes_box.insert("1.0", _NOTES_PLACEHOLDER)
        self.notes_box.bind("<FocusIn>",  self._notes_focus_in)
        self.notes_box.bind("<FocusOut>", self._notes_focus_out)

        # ── Feedback label ─────────────────────────────────────────────────────
        self.form_error = ctk.CTkLabel(
            form, text="",
            font=FONTS["body_small"],
            text_color=COLORS["danger"],
            wraplength=300,
            justify="left",
        )
        self.form_error.pack(padx=20, pady=(8, 4), anchor="w")

        self._divider(form)

        # ── Action buttons ─────────────────────────────────────────────────────
        ctk.CTkButton(
            form,
            text="✔  Confirm Payment",
            command=self._record_payment,
            **primary_button_style(),
        ).pack(fill="x", padx=20, pady=(10, 6))

        self.receipt_btn = ctk.CTkButton(
            form,
            text="🖨  Print Receipt",
            height=40,
            font=FONTS["button"],
            fg_color=COLORS["accent_gold"],
            hover_color=COLORS["accent_gold_dark"],
            text_color=COLORS["text_on_gold"],
            corner_radius=8,
            command=self._print_receipt,
            state="disabled",
        )
        self.receipt_btn.pack(fill="x", padx=20, pady=(0, 24))

    # ── history panel ──────────────────────────────────────────────────────────

    def _build_history_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        panel.grid(row=0, column=1, sticky="nsew", padx=(8, 24), pady=24)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="Payment History",
                     font=FONTS["title"],
                     text_color=COLORS["accent_green_dark"]).grid(
            row=0, column=0, sticky="w")
        ctk.CTkLabel(header,
                     text="Click a row to load its receipt for printing.",
                     font=FONTS["body_small"],
                     text_color=COLORS["text_muted"]).grid(
            row=1, column=0, sticky="w")

        self.history_table = DataTable(
            panel,
            columns=[
                ("receipt_number", "Receipt",  130),
                ("loan_number",    "Loan No.", 110),
                ("amount",         "Amount",   110),
                ("payment_date",   "Date",     100),
                ("method",         "Method",    90),
            ],
            on_select=self._on_history_selected,
        )
        self.history_table.grid(row=1, column=0, sticky="nsew")
        self._load_history()

    # ── helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _divider(parent):
        ctk.CTkFrame(parent, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=20, pady=10)

    @staticmethod
    def _field_label(parent, text: str):
        ctk.CTkLabel(
            parent, text=text,
            font=FONTS["body_small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(fill="x", padx=20, pady=(0, 2))

    def _notes_focus_in(self, _event):
        if self.notes_box.get("1.0", "end").strip() == _NOTES_PLACEHOLDER:
            self.notes_box.delete("1.0", "end")
            self.notes_box.configure(text_color=COLORS["text_primary"])

    def _notes_focus_out(self, _event):
        if not self.notes_box.get("1.0", "end").strip():
            self.notes_box.configure(text_color=COLORS["text_muted"])
            self.notes_box.insert("1.0", _NOTES_PLACEHOLDER)

    def _get_notes(self) -> str | None:
        raw = self.notes_box.get("1.0", "end").strip()
        return None if (not raw or raw == _NOTES_PLACEHOLDER) else raw

    # ── search mode change ─────────────────────────────────────────────────────

    def _on_search_mode_change(self, mode: str):
        """Update label and placeholder when search mode changes."""
        placeholders = {
            "Loan Number":  "e.g. BG-2026-00123",
            "Client Name":  "e.g. John Mukasa",
            "Client Phone": "e.g. 0787022284",
        }
        labels = {
            "Loan Number":  "Loan Number *",
            "Client Name":  "Client Name *",
            "Client Phone": "Client Phone Number *",
        }
        self.search_label_var.set(labels.get(mode, "Search *"))
        self.search_entry.configure(
            placeholder_text=placeholders.get(mode, ""))
        self.search_var.set("")
        # Reset loan info card
        self.loan_info_label.configure(
            text="Enter a value above and click Find Loan.",
            text_color=COLORS["text_muted"])
        self.found_loan = None

    # ── event handlers ─────────────────────────────────────────────────────────

    def _on_history_selected(self, row: dict):
        self._last_receipt = row
        self.receipt_btn.configure(state="normal")
        self.form_error.configure(
            text=f"Receipt {row.get('receipt_number', '')} loaded — click Print Receipt.",
            text_color=COLORS["accent_green"])

    def _find_loan(self):
        from app.core.services.loan_service import LoanService
        from app.core.services.repayment_service import RepaymentService
        from app.core.services.client_service import ClientService

        mode  = self.search_mode_var.get()
        term  = self.search_var.get().strip()

        if not term:
            self.loan_info_label.configure(
                text="Please enter a search value first.",
                text_color=COLORS["danger"])
            return

        # ── Search by Loan Number ──────────────────────────────────────────────
        if mode == "Loan Number":
            loans = LoanService.get_all_loans()
            loan  = next((l for l in loans if l.loan_number == term), None)
            if not loan:
                self.loan_info_label.configure(
                    text=f'No loan found with number "{term}". Check and try again.',
                    text_color=COLORS["danger"])
                self.found_loan = None
                return
            self._set_found_loan(loan)

        # ── Search by Client Name ──────────────────────────────────────────────
        elif mode == "Client Name":
            clients = ClientService.get_all_clients(search=term)
            if not clients:
                self.loan_info_label.configure(
                    text=f'No client found with name "{term}".',
                    text_color=COLORS["danger"])
                self.found_loan = None
                return

            # Gather all loans for matching clients
            all_loans = []
            client_map = {}
            for client in clients:
                c_loans = LoanService.get_loans_by_client(client.id)
                for l in c_loans:
                    all_loans.append(l)
                    client_map[l.client_id] = client

            if not all_loans:
                self.loan_info_label.configure(
                    text=f'Client "{term}" found but has no loans.',
                    text_color=COLORS["warning"] if COLORS.get("warning") else COLORS["danger"])
                self.found_loan = None
                return

            if len(all_loans) == 1:
                self._set_found_loan(all_loans[0])
            else:
                self._open_loan_picker(all_loans, client_map)

        # ── Search by Client Phone ─────────────────────────────────────────────
        elif mode == "Client Phone":
            clients = ClientService.get_all_clients(search=term)
            # Filter by phone specifically
            phone_clients = [
                c for c in clients
                if c.phone_number and term in c.phone_number]

            if not phone_clients:
                # Try broader search
                phone_clients = clients

            if not phone_clients:
                self.loan_info_label.configure(
                    text=f'No client found with phone "{term}".',
                    text_color=COLORS["danger"])
                self.found_loan = None
                return

            all_loans  = []
            client_map = {}
            for client in phone_clients:
                c_loans = LoanService.get_loans_by_client(client.id)
                for l in c_loans:
                    all_loans.append(l)
                    client_map[l.client_id] = client

            if not all_loans:
                self.loan_info_label.configure(
                    text=f'Client with phone "{term}" found but has no loans.',
                    text_color=COLORS["danger"])
                self.found_loan = None
                return

            if len(all_loans) == 1:
                self._set_found_loan(all_loans[0])
            else:
                self._open_loan_picker(all_loans, client_map)

    def _open_loan_picker(self, loans: list, client_map: dict):
        """Open the loan picker dialog when multiple loans match."""
        self.loan_info_label.configure(
            text=f"{len(loans)} loans found — opening picker…",
            text_color=COLORS["text_muted"])

        dialog = LoanPickerDialog(self.winfo_toplevel(), loans, client_map)
        self.wait_window(dialog)

        if dialog.result:
            self._set_found_loan(dialog.result)
        else:
            self.found_loan = None
            self.loan_info_label.configure(
                text="No loan selected. Refine your search and try again.",
                text_color=COLORS["text_muted"])

    def _set_found_loan(self, loan):
        """Confirm a loan has been found and update the info card."""
        from app.core.services.client_service import ClientService
        from app.core.services.repayment_service import RepaymentService

        self.found_loan = loan
        client  = ClientService.get_client_by_id(loan.client_id)
        balance = RepaymentService.get_outstanding_balance(loan.id)

        status_color = (
            COLORS["accent_green"]  if loan.status.value == "active"   else
            COLORS["danger"]        if loan.status.value in ("defaulted", "rejected") else
            COLORS["text_primary"]
        )
        self.loan_info_label.configure(
            text=(
                f"✔  {loan.loan_number}\n"
                f"Client: {client.full_name if client else '—'}  "
                f"|  Phone: {client.phone_number if client else '—'}\n"
                f"Type: {loan.loan_type.value if loan.loan_type else '—'}  "
                f"|  Status: {loan.status.value.upper()}\n"
                f"Outstanding Balance: UGX {float(balance):,.0f}"
            ),
            text_color=status_color,
        )
        self._load_history(loan_id=loan.id)

    # ── record payment ─────────────────────────────────────────────────────────

    def _record_payment(self):
        from app.core.services.repayment_service import RepaymentService

        if not self.found_loan:
            self.form_error.configure(
                text="⚠  Please find and select a loan first.",
                text_color=COLORS["danger"])
            return

        amount_str = self.amount_var.get().strip()
        if not amount_str:
            self.form_error.configure(
                text="⚠  Please enter the amount paid.",
                text_color=COLORS["danger"])
            return

        try:
            amount = float(amount_str.replace(",", "").replace(" ", ""))
        except ValueError:
            self.form_error.configure(
                text="⚠  Invalid amount — enter digits only, e.g. 500000.",
                text_color=COLORS["danger"])
            return

        if amount <= 0:
            self.form_error.configure(
                text="⚠  Amount must be greater than zero.",
                text_color=COLORS["danger"])
            return

        try:
            pay_date  = self.payment_date_picker.get_date()
            method    = self.method_var.get()
            ref       = self.ref_var.get().strip() or None
            notes     = self._get_notes()

            repayment = RepaymentService.record_payment(
                loan_id               = self.found_loan.id,
                amount                = amount,
                payment_method        = method,
                payment_date          = pay_date,
                transaction_reference = ref,
                notes                 = notes,
                recorded_by_id        = self.current_user.id if self.current_user else None,
            )

            self.form_error.configure(
                text=f"✔  Payment recorded — Receipt: {repayment.receipt_number}",
                text_color=COLORS["accent_green"])

            from app.core.services.client_service import ClientService
            from app.core.services.repayment_service import RepaymentService as RS
            client  = ClientService.get_client_by_id(self.found_loan.client_id)
            balance = RS.get_outstanding_balance(self.found_loan.id)

            self._last_receipt = {
                "receipt_number": repayment.receipt_number,
                "loan_number":    self.found_loan.loan_number,
                "client_name":    client.full_name    if client else "—",
                "client_phone":   client.phone_number if client else "—",
                "amount":         f"UGX {amount:,.0f}",
                "payment_date":   str(pay_date),
                "method":         method,
                "reference":      ref or "—",
                "loan_type":      self.found_loan.loan_type.value if self.found_loan.loan_type else "—",
                "balance":        f"UGX {float(balance):,.0f}",
                "recorded_by":    self.current_user.full_name if self.current_user else "—",
            }
            self.receipt_btn.configure(state="normal")

            # Reset fields
            self.amount_var.set("")
            self.ref_var.set("")
            self.notes_box.delete("1.0", "end")
            self._notes_focus_out(None)

            self._load_history(loan_id=self.found_loan.id)

        except Exception as e:
            self.form_error.configure(
                text=f"Error: {e}", text_color=COLORS["danger"])

    # ── print receipt ──────────────────────────────────────────────────────────

    def _print_receipt(self):
        if not self._last_receipt:
            return

        from app.ui.components.save_dialog import SaveDialog
        receipt_num = self._last_receipt.get("receipt_number", "receipt")
        dialog = SaveDialog(
            self.winfo_toplevel(),
            title        = "Save Receipt As",
            default_name = f"receipt_{receipt_num}.pdf",
            extension    = ".pdf",
        )
        self.wait_window(dialog)
        if not dialog.result:
            return

        threading.Thread(
            target=self._generate_receipt_pdf,
            args=(self._last_receipt, dialog.result),
            daemon=True,
        ).start()

    def _generate_receipt_pdf(self, data: dict, save_path: str):
        try:
            from reportlab.lib.pagesizes import A5
            from reportlab.lib import colors as rl_colors
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer,
                Table, TableStyle, HRFlowable,
            )
            from reportlab.lib.units import cm
            from datetime import datetime

            doc = SimpleDocTemplate(
                save_path, pagesize=A5,
                topMargin=1.5*cm, bottomMargin=1.5*cm,
                leftMargin=1.8*cm, rightMargin=1.8*cm,
            )

            GREEN = rl_colors.HexColor("#1A5C1E")
            LGOLD = rl_colors.HexColor("#D4A820")
            LGREY = rl_colors.HexColor("#F0F7F0")

            h1      = ParagraphStyle("h1",    fontSize=18, fontName="Helvetica-Bold",
                                     textColor=GREEN, alignment=1, spaceAfter=2)
            h2      = ParagraphStyle("h2",    fontSize=10, fontName="Helvetica",
                                     textColor=rl_colors.grey, alignment=1, spaceAfter=8)
            title_s = ParagraphStyle("title", fontSize=14, fontName="Helvetica-Bold",
                                     textColor=GREEN, alignment=1, spaceAfter=4)
            lbl     = ParagraphStyle("lbl",   fontSize=9,  fontName="Helvetica",
                                     textColor=rl_colors.grey)
            bold    = ParagraphStyle("bold",  fontSize=10, fontName="Helvetica-Bold",
                                     textColor=rl_colors.black)
            amt_s   = ParagraphStyle("amt",   fontSize=20, fontName="Helvetica-Bold",
                                     textColor=GREEN, alignment=1)
            amt_lbl = ParagraphStyle("amtl",  fontSize=10, fontName="Helvetica",
                                     textColor=rl_colors.grey, alignment=1)
            foot_s  = ParagraphStyle("foot",  fontSize=8,
                                     textColor=rl_colors.grey,
                                     alignment=1, spaceBefore=4)

            elements = []
            elements.append(Paragraph("BINGONGOLD CREDIT", h1))
            elements.append(Paragraph("together as one", h2))
            elements.append(Paragraph(
                "Ham Tower, 4th Floor, Wandegeya, Kampala", h2))
            elements.append(HRFlowable(
                width="100%", thickness=2, color=GREEN, spaceAfter=10))
            elements.append(Paragraph("PAYMENT RECEIPT", title_s))
            elements.append(HRFlowable(
                width="100%", thickness=1, color=LGOLD, spaceAfter=12))

            tdata = [
                ["Receipt No.", data["receipt_number"]],
                ["Date",        data.get("payment_date", "—")],
                ["Client",      data.get("client_name",  "—")],
                ["Phone",       data.get("client_phone", "—")],
                ["Loan No.",    data.get("loan_number",  "—")],
                ["Loan Type",   data.get("loan_type",    "—")],
                ["Method",      data.get("method",       "—")],
                ["Reference",   data.get("reference",    "—")],
            ]
            t = Table(tdata, colWidths=[4*cm, 8*cm])
            t.setStyle(TableStyle([
                ("FONTNAME",       (0,0), (0,-1), "Helvetica-Bold"),
                ("FONTSIZE",       (0,0), (-1,-1), 10),
                ("TEXTCOLOR",      (0,0), (0,-1), rl_colors.grey),
                ("ROWBACKGROUNDS", (0,0), (-1,-1), [LGREY, rl_colors.white]),
                ("TOPPADDING",     (0,0), (-1,-1), 5),
                ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
                ("LEFTPADDING",    (0,0), (-1,-1), 6),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 0.5*cm))

            amt_table = Table(
                [[Paragraph("AMOUNT PAID", amt_lbl)],
                 [Paragraph(data.get("amount", "—"), amt_s)],
                 [Paragraph(
                     f"Outstanding Balance: {data.get('balance','—')}",
                     amt_lbl)]],
                colWidths=[12*cm],
            )
            amt_table.setStyle(TableStyle([
                ("BACKGROUND",    (0,0), (-1,-1), LGREY),
                ("TOPPADDING",    (0,0), (-1,-1), 8),
                ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ]))
            elements.append(amt_table)
            elements.append(Spacer(1, 1*cm))

            elements.append(HRFlowable(
                width="100%", thickness=0.5, color=rl_colors.lightgrey))
            elements.append(Spacer(1, 0.3*cm))

            sig_data = [
                [Paragraph("Received by:", lbl),
                 Paragraph("", lbl),
                 Paragraph("Client signature:", lbl)],
                [Paragraph(data.get("recorded_by", "—"), bold),
                 Paragraph("", lbl),
                 Paragraph("_________________________", lbl)],
            ]
            sig_t = Table(sig_data, colWidths=[5*cm, 2*cm, 5*cm])
            sig_t.setStyle(TableStyle([
                ("TOPPADDING", (0,0), (-1,-1), 4),
                ("ALIGN",      (2,0), (2,-1),  "RIGHT"),
            ]))
            elements.append(sig_t)
            elements.append(Spacer(1, 0.8*cm))
            elements.append(HRFlowable(
                width="100%", thickness=2, color=GREEN))
            elements.append(Paragraph(
                "Thank you for your payment  |  together as one", foot_s))
            elements.append(Paragraph(
                f"Printed: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                foot_s))

            doc.build(elements)

            self.after(0, lambda: self.form_error.configure(
                text=f"✔  Receipt saved: {save_path}",
                text_color=COLORS["accent_green"]))

            import subprocess
            subprocess.Popen(["xdg-open", save_path])

        except Exception as e:
            self.after(0, lambda: self.form_error.configure(
                text=f"Receipt error: {e}",
                text_color=COLORS["danger"]))

    # ── load history ───────────────────────────────────────────────────────────

    def _load_history(self, loan_id: int = None):
        from app.core.services.repayment_service import RepaymentService
        from app.core.services.loan_service import LoanService

        if loan_id:
            repayments = RepaymentService.get_repayments_for_loan(loan_id)
        else:
            repayments = RepaymentService.get_all_recent_repayments(limit=30)

        all_loans = {l.id: l for l in LoanService.get_all_loans()}
        rows = []
        for r in repayments:
            loan = all_loans.get(r.loan_id)
            rows.append({
                "receipt_number": r.receipt_number,
                "loan_number":    loan.loan_number if loan else "—",
                "amount":         f"UGX {r.amount:,.0f}",
                "payment_date":   str(r.payment_date),
                "method":         r.payment_method.value if r.payment_method else "—",
            })

        if hasattr(self, "history_table"):
            self.history_table.update_rows(rows)