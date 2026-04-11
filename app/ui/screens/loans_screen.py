"""
app/ui/screens/loans_screen.py
─────────────────────────────────────────────
Loan management — list all loans with status filter,
new loan application form, approve/reject actions.
"""

import customtkinter as ctk
from app.ui.styles.theme import COLORS, FONTS, primary_button_style, secondary_button_style, input_style, danger_button_style
from app.ui.components.sidebar import Sidebar
from app.ui.components.data_table import DataTable
from app.config.settings import LOAN_TYPES


class LoansScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master = master
        self.current_user = master.current_user
        self.selected_loan = None
        self._build()
        self._load_loans()

    def _navigate(self, screen):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        Sidebar(self, "loans", self._navigate, self.current_user).grid(
            row=0, column=0, sticky="nsew"
        )

        main = ctk.CTkFrame(self, fg_color=COLORS["bg_primary"])
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        self._build_list_panel(main)
        self._build_detail_panel(main)

    # ── Left: Loan List ────────────────────────────────────────────────────
    def _build_list_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        panel.grid(row=0, column=0, sticky="nsew", padx=(24, 8), pady=24)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(2, weight=1)

        ctk.CTkLabel(panel, text="Loans", font=FONTS["title"],
                     text_color=COLORS["text_primary"]).grid(
            row=0, column=0, sticky="w", pady=(0, 16))

        # Filter + search row
        filter_row = ctk.CTkFrame(panel, fg_color="transparent")
        filter_row.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        filter_row.columnconfigure(1, weight=1)

        self.status_filter = ctk.CTkOptionMenu(
            filter_row,
            values=["All", "pending", "approved", "active", "completed", "defaulted"],
            command=lambda v: self._load_loans(),
            fg_color=COLORS["bg_input"],
            button_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"],
            font=FONTS["body_small"],
            width=120,
        )
        self.status_filter.grid(row=0, column=0, padx=(0, 8))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._load_loans())
        ctk.CTkEntry(
            filter_row,
            textvariable=self.search_var,
            placeholder_text="🔍  Search client name...",
            **input_style(),
        ).grid(row=0, column=1, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            filter_row, text="+ New Loan", width=120,
            command=self._new_loan_form,
            **primary_button_style(),
        ).grid(row=0, column=2)

        self.table = DataTable(
            panel,
            columns=[
                ("loan_number", "Loan No.",    110),
                ("client_name", "Client",      160),
                ("loan_type",   "Type",        140),
                ("principal",   "Principal",   110),
                ("status",      "Status",       90),
            ],
            on_select=self._on_loan_selected,
        )
        self.table.grid(row=2, column=0, sticky="nsew")

    # ── Right: Detail / Form Panel ─────────────────────────────────────────
    def _build_detail_panel(self, parent):
        self.detail_panel = ctk.CTkScrollableFrame(
            parent,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
            scrollbar_button_color=COLORS["bg_hover"],
        )
        self.detail_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 24), pady=24)
        self.detail_panel.columnconfigure(0, weight=1)
        self._show_empty_state()

    def _show_empty_state(self):
        for w in self.detail_panel.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.detail_panel,
            text="Select a loan\nor click + New Loan",
            font=FONTS["body"],
            text_color=COLORS["text_muted"],
            justify="center",
        ).pack(expand=True, pady=80)

    def _on_loan_selected(self, row):
        from app.core.services.loan_service import LoanService
        loan = LoanService.get_loan_by_id(row["id"])
        self.selected_loan = loan
        if loan:
            self._render_loan_detail(loan)

    def _render_loan_detail(self, loan):
        for w in self.detail_panel.winfo_children():
            w.destroy()

        # Header
        ctk.CTkLabel(self.detail_panel, text=loan.loan_number,
                     font=FONTS["subtitle"], text_color=COLORS["accent_gold"]).pack(
            anchor="w", padx=20, pady=(20, 4))

        status_color = {
            "pending": COLORS["warning"], "approved": COLORS["info"],
            "active": COLORS["success"], "completed": COLORS["text_muted"],
            "defaulted": COLORS["danger"], "rejected": COLORS["danger"],
        }.get(loan.status.value, COLORS["text_secondary"])

        ctk.CTkLabel(self.detail_panel,
                     text=loan.status.value.upper(),
                     font=FONTS["badge"],
                     text_color=status_color).pack(anchor="w", padx=20)

        ctk.CTkFrame(self.detail_panel, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=20, pady=12)

        # Details
        from app.core.services.client_service import ClientService
        from app.core.services.repayment_service import RepaymentService

        client = ClientService.get_client_by_id(loan.client_id)
        balance = RepaymentService.get_outstanding_balance(loan.id)

        details = [
            ("Client",           client.full_name if client else "—"),
            ("Loan Type",        loan.loan_type.value if loan.loan_type else "—"),
            ("Principal",        f"UGX {loan.principal_amount:,.0f}"),
            ("Interest (10%)",   f"UGX {loan.total_interest:,.0f}" if loan.total_interest else "—"),
            ("Total Repayable",  f"UGX {loan.total_repayable:,.0f}" if loan.total_repayable else "—"),
            ("Monthly Install.", f"UGX {loan.monthly_installment:,.0f}" if loan.monthly_installment else "—"),
            ("Duration",         f"{loan.duration_months} months"),
            ("Application Date", str(loan.application_date)),
            ("Due Date",         str(loan.due_date) if loan.due_date else "—"),
            ("Outstanding",      f"UGX {balance:,.0f}"),
            ("Purpose",          loan.purpose or "—"),
            ("Risk Score",       loan.risk_score or "Not assessed"),
        ]

        for label, value in details:
            row = ctk.CTkFrame(self.detail_panel, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=3)
            ctk.CTkLabel(row, text=label, font=FONTS["body_small"],
                         text_color=COLORS["text_muted"], width=130, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value, font=FONTS["body_small"],
                         text_color=COLORS["text_primary"], anchor="w").pack(side="left")

        # Action buttons
        ctk.CTkFrame(self.detail_panel, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=20, pady=12)

        btn_frame = ctk.CTkFrame(self.detail_panel, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 8))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        if loan.status.value == "pending":
            ctk.CTkButton(btn_frame, text="✔ Approve",
                          fg_color=COLORS["success"], hover_color="#1E8449",
                          text_color="white", font=FONTS["button"],
                          corner_radius=8, height=38,
                          command=lambda: self._approve_loan(loan.id)).grid(
                row=0, column=0, padx=(0, 4), sticky="ew")
            ctk.CTkButton(btn_frame, text="✗ Reject",
                          command=lambda: self._reject_loan(loan.id),
                          **danger_button_style()).grid(
                row=0, column=1, padx=(4, 0), sticky="ew")

        elif loan.status.value == "active":
            ctk.CTkButton(btn_frame, text="💳 Record Payment",
                          command=lambda: self.master.show_screen("repayments"),
                          **primary_button_style()).grid(
                row=0, column=0, columnspan=2, sticky="ew")

        if loan.risk_score is None:
            ctk.CTkButton(self.detail_panel, text="🤖 Run AI Risk Assessment",
                          command=lambda: self.master.show_screen("agent"),
                          **secondary_button_style()).pack(
                fill="x", padx=20, pady=(0, 20))

    def _new_loan_form(self):
        self.selected_loan = None
        self._render_new_loan_form()

    def _render_new_loan_form(self):
        for w in self.detail_panel.winfo_children():
            w.destroy()

        ctk.CTkLabel(self.detail_panel, text="New Loan Application",
                     font=FONTS["subtitle"], text_color=COLORS["text_primary"]).pack(
            anchor="w", padx=20, pady=(20, 16))

        self.loan_vars = {}

        # Client search
        ctk.CTkLabel(self.detail_panel, text="Client NIN or Name *",
                     font=FONTS["body_small"], text_color=COLORS["text_secondary"],
                     anchor="w").pack(fill="x", padx=20, pady=(0, 2))
        self.client_search_var = ctk.StringVar()
        ctk.CTkEntry(self.detail_panel, textvariable=self.client_search_var,
                     placeholder_text="Type NIN or full name...",
                     **input_style()).pack(fill="x", padx=20)

        self.client_result_label = ctk.CTkLabel(
            self.detail_panel, text="", font=FONTS["caption"],
            text_color=COLORS["text_muted"])
        self.client_result_label.pack(anchor="w", padx=20)

        ctk.CTkButton(self.detail_panel, text="Find Client", height=32,
                      font=FONTS["body_small"],
                      fg_color=COLORS["bg_hover"], hover_color=COLORS["bg_input"],
                      text_color=COLORS["text_primary"], corner_radius=6,
                      command=self._find_client).pack(anchor="w", padx=20, pady=(4, 12))

        # Loan fields
        fields = [
            ("loan_type",       "Loan Type *",          "option", LOAN_TYPES),
            ("principal_amount","Principal Amount (UGX) *", "entry", None),
            ("duration_months", "Duration (months) *",   "entry", None),
            ("purpose",         "Purpose / Reason",      "entry", None),
        ]

        for key, label, ftype, options in fields:
            ctk.CTkLabel(self.detail_panel, text=label, font=FONTS["body_small"],
                         text_color=COLORS["text_secondary"], anchor="w").pack(
                fill="x", padx=20, pady=(8, 2))
            var = ctk.StringVar()
            self.loan_vars[key] = var
            if ftype == "option":
                ctk.CTkOptionMenu(
                    self.detail_panel, variable=var, values=options,
                    fg_color=COLORS["bg_input"], button_color=COLORS["bg_hover"],
                    text_color=COLORS["text_primary"], font=FONTS["body_small"],
                ).pack(fill="x", padx=20)
                var.set(options[0])
            else:
                ctk.CTkEntry(self.detail_panel, textvariable=var,
                             **input_style()).pack(fill="x", padx=20)

        # Interest preview
        self.interest_preview = ctk.CTkLabel(
            self.detail_panel, text="",
            font=FONTS["body_small"], text_color=COLORS["accent_gold"])
        self.interest_preview.pack(anchor="w", padx=20, pady=(8, 0))
        self.loan_vars["principal_amount"].trace_add("write", self._update_interest_preview)
        self.loan_vars["duration_months"].trace_add("write", self._update_interest_preview)

        self.loan_form_error = ctk.CTkLabel(self.detail_panel, text="",
                                            font=FONTS["body_small"],
                                            text_color=COLORS["danger"])
        self.loan_form_error.pack(padx=20, pady=(8, 0))

        ctk.CTkButton(self.detail_panel, text="Submit Application",
                      command=self._submit_loan,
                      **primary_button_style()).pack(fill="x", padx=20, pady=(12, 20))

        self.found_client_id = None

    def _find_client(self):
        from app.core.services.client_service import ClientService
        term = self.client_search_var.get().strip()
        if not term:
            return
        clients = ClientService.get_all_clients(search=term)
        if clients:
            c = clients[0]
            self.found_client_id = c.id
            self.client_result_label.configure(
                text=f"✔ Found: {c.full_name} (NIN: {c.nin or '—'})",
                text_color=COLORS["success"])
        else:
            self.found_client_id = None
            self.client_result_label.configure(
                text="✗ No client found. Register the client first.",
                text_color=COLORS["danger"])

    def _update_interest_preview(self, *args):
        try:
            principal = float(self.loan_vars["principal_amount"].get())
            months = int(self.loan_vars["duration_months"].get())
            interest = principal * 0.10
            total = principal + interest
            installment = total / months
            self.interest_preview.configure(
                text=f"Interest: UGX {interest:,.0f}  |  Total: UGX {total:,.0f}  |  Monthly: UGX {installment:,.0f}"
            )
        except Exception:
            self.interest_preview.configure(text="")

    def _submit_loan(self):
        from app.core.services.loan_service import LoanService
        if not getattr(self, "found_client_id", None):
            self.loan_form_error.configure(text="Please find and select a client first.")
            return
        try:
            principal = float(self.loan_vars["principal_amount"].get())
            duration = int(self.loan_vars["duration_months"].get())
            loan_type = self.loan_vars["loan_type"].get()
            purpose = self.loan_vars["purpose"].get().strip() or None
            LoanService.create_loan(
                client_id=self.found_client_id,
                loan_type=loan_type,
                principal_amount=principal,
                duration_months=duration,
                purpose=purpose,
                created_by_id=self.current_user.id if self.current_user else None,
            )
            self.loan_form_error.configure(text="")
            self._load_loans()
            self._show_empty_state()
        except Exception as e:
            self.loan_form_error.configure(text=str(e))

    def _approve_loan(self, loan_id):
        from app.core.services.loan_service import LoanService
        LoanService.approve_loan(
            loan_id,
            approved_by_id=self.current_user.id if self.current_user else None
        )
        self._load_loans()
        self._show_empty_state()

    def _reject_loan(self, loan_id):
        from app.core.services.loan_service import LoanService
        LoanService.reject_loan(loan_id, reason="Rejected by officer.")
        self._load_loans()
        self._show_empty_state()

    def _load_loans(self, *args):
        from app.core.services.loan_service import LoanService
        from app.core.services.client_service import ClientService

        status = self.status_filter.get() if hasattr(self, "status_filter") else "All"
        search = self.search_var.get().strip() if hasattr(self, "search_var") else None
        loans = LoanService.get_all_loans(
            status=None if status == "All" else status,
            search=search or None,
        )
        rows = []
        for loan in loans:
            client = ClientService.get_client_by_id(loan.client_id)
            rows.append({
                "id": loan.id,
                "loan_number": loan.loan_number,
                "client_name": client.full_name if client else "—",
                "loan_type": loan.loan_type.value if loan.loan_type else "—",
                "principal": f"UGX {loan.principal_amount:,.0f}",
                "status": loan.status.value.upper(),
            })
        if hasattr(self, "table"):
            self.table.update_rows(rows)