"""
app/ui/screens/repayments_screen.py
─────────────────────────────────────────────
Record payments against loans and view repayment history.
"""

import customtkinter as ctk
from datetime import date
from app.ui.styles.theme import COLORS, FONTS, primary_button_style, input_style
from app.ui.components.sidebar import Sidebar
from app.ui.components.data_table import DataTable


PAYMENT_METHODS = ["Cash", "Mobile Money", "Bank Transfer", "Cheque"]


class RepaymentsScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master = master
        self.current_user = master.current_user
        self.found_loan = None
        self._build()

    def _navigate(self, screen):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        Sidebar(self, "repayments", self._navigate, self.current_user).grid(
            row=0, column=0, sticky="nsew"
        )

        main = ctk.CTkFrame(self, fg_color=COLORS["bg_primary"])
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=2)
        main.columnconfigure(1, weight=3)
        main.rowconfigure(0, weight=1)

        self._build_payment_form(main)
        self._build_history_panel(main)

    # ── Left: Payment Form ─────────────────────────────────────────────────
    def _build_payment_form(self, parent):
        form = ctk.CTkScrollableFrame(parent, fg_color=COLORS["bg_card"],
                                      corner_radius=12,
                                      scrollbar_button_color=COLORS["bg_hover"])
        form.grid(row=0, column=0, sticky="nsew", padx=(24, 8), pady=24)
        form.columnconfigure(0, weight=1)

        ctk.CTkLabel(form, text="Record Payment", font=FONTS["subtitle"],
                     text_color=COLORS["text_primary"]).pack(
            anchor="w", padx=20, pady=(20, 16))

        # Loan lookup
        ctk.CTkLabel(form, text="Loan Number *", font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"], anchor="w").pack(
            fill="x", padx=20, pady=(0, 2))
        self.loan_number_var = ctk.StringVar()
        ctk.CTkEntry(form, textvariable=self.loan_number_var,
                     placeholder_text="e.g. BG-2025-12345",
                     **input_style()).pack(fill="x", padx=20)

        ctk.CTkButton(form, text="Find Loan", height=32,
                      font=FONTS["body_small"],
                      fg_color=COLORS["bg_hover"], hover_color=COLORS["bg_input"],
                      text_color=COLORS["text_primary"], corner_radius=6,
                      command=self._find_loan).pack(anchor="w", padx=20, pady=(6, 0))

        # Loan info preview
        self.loan_info = ctk.CTkFrame(form, fg_color=COLORS["bg_input"], corner_radius=8)
        self.loan_info.pack(fill="x", padx=20, pady=(10, 8))
        self.loan_info_label = ctk.CTkLabel(
            self.loan_info, text="No loan loaded.",
            font=FONTS["body_small"], text_color=COLORS["text_muted"])
        self.loan_info_label.pack(padx=12, pady=10)

        ctk.CTkFrame(form, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=20, pady=8)

        # Amount
        ctk.CTkLabel(form, text="Amount Paid (UGX) *", font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"], anchor="w").pack(
            fill="x", padx=20, pady=(0, 2))
        self.amount_var = ctk.StringVar()
        ctk.CTkEntry(form, textvariable=self.amount_var,
                     placeholder_text="e.g. 500000",
                     **input_style()).pack(fill="x", padx=20)

        # Payment date
        ctk.CTkLabel(form, text="Payment Date *", font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"], anchor="w").pack(
            fill="x", padx=20, pady=(10, 2))
        self.date_var = ctk.StringVar(value=str(date.today()))
        ctk.CTkEntry(form, textvariable=self.date_var,
                     **input_style()).pack(fill="x", padx=20)

        # Payment method
        ctk.CTkLabel(form, text="Payment Method *", font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"], anchor="w").pack(
            fill="x", padx=20, pady=(10, 2))
        self.method_var = ctk.StringVar(value="Cash")
        ctk.CTkOptionMenu(form, variable=self.method_var, values=PAYMENT_METHODS,
                          fg_color=COLORS["bg_input"], button_color=COLORS["bg_hover"],
                          text_color=COLORS["text_primary"],
                          font=FONTS["body_small"]).pack(fill="x", padx=20)

        # Reference
        ctk.CTkLabel(form, text="Transaction Reference (optional)",
                     font=FONTS["body_small"], text_color=COLORS["text_secondary"],
                     anchor="w").pack(fill="x", padx=20, pady=(10, 2))
        self.ref_var = ctk.StringVar()
        ctk.CTkEntry(form, textvariable=self.ref_var,
                     placeholder_text="Mobile money or bank reference",
                     **input_style()).pack(fill="x", padx=20)

        # Notes
        ctk.CTkLabel(form, text="Notes (optional)", font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"], anchor="w").pack(
            fill="x", padx=20, pady=(10, 2))
        self.notes_box = ctk.CTkTextbox(form, height=60,
                                        fg_color=COLORS["bg_input"],
                                        text_color=COLORS["text_primary"],
                                        font=FONTS["body"])
        self.notes_box.pack(fill="x", padx=20)

        self.form_error = ctk.CTkLabel(form, text="", font=FONTS["body_small"],
                                       text_color=COLORS["danger"])
        self.form_error.pack(padx=20, pady=(8, 0))

        ctk.CTkButton(form, text="💳  Confirm Payment",
                      command=self._record_payment,
                      **primary_button_style()).pack(fill="x", padx=20, pady=(12, 20))

    # ── Right: History Panel ───────────────────────────────────────────────
    def _build_history_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        panel.grid(row=0, column=1, sticky="nsew", padx=(8, 24), pady=24)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)

        ctk.CTkLabel(panel, text="Payment History", font=FONTS["title"],
                     text_color=COLORS["text_primary"]).grid(
            row=0, column=0, sticky="w", pady=(0, 12))

        self.history_table = DataTable(
            panel,
            columns=[
                ("receipt_number", "Receipt",      130),
                ("loan_number",    "Loan No.",     110),
                ("amount",         "Amount",        110),
                ("payment_date",   "Date",          100),
                ("method",         "Method",         90),
            ],
        )
        self.history_table.grid(row=1, column=0, sticky="nsew")
        self._load_history()

    def _find_loan(self):
        from app.core.services.loan_service import LoanService
        from app.core.services.repayment_service import RepaymentService
        from app.core.services.client_service import ClientService

        number = self.loan_number_var.get().strip()
        if not number:
            return

        loans = LoanService.get_all_loans()
        loan = next((l for l in loans if l.loan_number == number), None)

        if not loan:
            self.loan_info_label.configure(
                text="✗ Loan not found.", text_color=COLORS["danger"])
            self.found_loan = None
            return

        self.found_loan = loan
        client = ClientService.get_client_by_id(loan.client_id)
        balance = RepaymentService.get_outstanding_balance(loan.id)

        info = (f"Client: {client.full_name if client else '—'}  |  "
                f"Type: {loan.loan_type.value if loan.loan_type else '—'}  |  "
                f"Outstanding: UGX {balance:,.0f}  |  Status: {loan.status.value.upper()}")

        self.loan_info_label.configure(text=info, text_color=COLORS["text_primary"])
        self._load_history(loan_id=loan.id)

    def _record_payment(self):
        from app.core.services.repayment_service import RepaymentService
        from datetime import datetime

        if not self.found_loan:
            self.form_error.configure(text="Please find a loan first.")
            return

        try:
            amount = float(self.amount_var.get())
            pay_date = datetime.strptime(self.date_var.get(), "%Y-%m-%d").date()
            method = self.method_var.get()
            ref = self.ref_var.get().strip() or None
            notes = self.notes_box.get("1.0", "end").strip() or None

            RepaymentService.record_payment(
                loan_id=self.found_loan.id,
                amount=amount,
                payment_method=method,
                payment_date=pay_date,
                transaction_reference=ref,
                notes=notes,
                recorded_by_id=self.current_user.id if self.current_user else None,
            )
            self.form_error.configure(text="✔ Payment recorded successfully.",
                                       text_color=COLORS["success"])
            self.amount_var.set("")
            self.ref_var.set("")
            self.notes_box.delete("1.0", "end")
            self._load_history(loan_id=self.found_loan.id)

        except Exception as e:
            self.form_error.configure(text=str(e), text_color=COLORS["danger"])

    def _load_history(self, loan_id: int = None):
        from app.core.services.repayment_service import RepaymentService
        from app.core.services.loan_service import LoanService

        if loan_id:
            repayments = RepaymentService.get_repayments_for_loan(loan_id)
        else:
            repayments = RepaymentService.get_all_recent_repayments(limit=30)

        rows = []
        all_loans = {l.id: l for l in LoanService.get_all_loans()}
        for r in repayments:
            loan = all_loans.get(r.loan_id)
            rows.append({
                "receipt_number": r.receipt_number,
                "loan_number": loan.loan_number if loan else "—",
                "amount": f"UGX {r.amount:,.0f}",
                "payment_date": str(r.payment_date),
                "method": r.payment_method.value if r.payment_method else "—",
            })
        if hasattr(self, "history_table"):
            self.history_table.update_rows(rows)