"""
app/ui/screens/loans_screen.py
Updated: date pickers, collateral photo upload, icon labels restored, placeholders added
"""

import customtkinter as ctk
import os
import shutil
from datetime import date
from PIL import Image
from app.ui.styles.theme import COLORS, FONTS, primary_button_style, secondary_button_style, input_style, danger_button_style
from app.ui.components.sidebar import Sidebar
from app.ui.components.data_table import DataTable
from app.ui.components.date_picker import DatePicker
from app.config.settings import LOAN_TYPES, COLLATERAL_UPLOAD_DIR


class LoansScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master = master
        self.current_user = master.current_user
        self.selected_loan = None
        self._collateral_files = []
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
            row=0, column=0, sticky="nsew")
        main = ctk.CTkFrame(self, fg_color=COLORS["bg_primary"])
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)
        self._build_list_panel(main)
        self._build_detail_panel(main)

    # ── LEFT: Loan list ──────────────────────────────────────────────────
    def _build_list_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        panel.grid(row=0, column=0, sticky="nsew", padx=(24, 8), pady=24)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(2, weight=1)

        ctk.CTkLabel(panel, text="Loans", font=FONTS["title"],
                     text_color=COLORS["accent_green_dark"]).grid(
            row=0, column=0, sticky="w", pady=(0, 16))

        filter_row = ctk.CTkFrame(panel, fg_color="transparent")
        filter_row.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        filter_row.columnconfigure(1, weight=1)

        self.status_filter = ctk.CTkOptionMenu(
            filter_row,
            values=["All", "pending", "approved", "active", "completed", "defaulted"],
            command=lambda v: self._load_loans(),
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_green"],
            text_color=COLORS["text_primary"],
            font=FONTS["body_small"], width=120)
        self.status_filter.grid(row=0, column=0, padx=(0, 8))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._load_loans())
        ctk.CTkEntry(filter_row, textvariable=self.search_var,
                     placeholder_text="🔍  Search by client name...",
                     **input_style()).grid(row=0, column=1, sticky="ew", padx=(0, 8))

        ctk.CTkButton(filter_row, text="+ New Loan", width=120,
                      command=self._new_loan_form,
                      **primary_button_style()).grid(row=0, column=2)

        self.table = DataTable(
            panel,
            columns=[
                ("loan_number", "Loan No.",  110),
                ("client_name", "Client",    160),
                ("loan_type",   "Type",      120),
                ("principal",   "Principal", 110),
                ("status",      "Status",     90),
            ],
            on_select=self._on_loan_selected)
        self.table.grid(row=2, column=0, sticky="nsew")

    # ── RIGHT: Detail / form ─────────────────────────────────────────────
    def _build_detail_panel(self, parent):
        self.detail_panel = ctk.CTkScrollableFrame(
            parent, fg_color=COLORS["bg_card"], corner_radius=12,
            border_width=1, border_color=COLORS["border"],
            scrollbar_button_color=COLORS["border"])
        self.detail_panel.grid(row=0, column=1, sticky="nsew",
                                padx=(8, 24), pady=24)
        self.detail_panel.columnconfigure(0, weight=1)
        self._show_empty_state()

    def _show_empty_state(self):
        for w in self.detail_panel.winfo_children(): w.destroy()
        ctk.CTkLabel(self.detail_panel,
                     text="Select a loan\nor click + New Loan",
                     font=FONTS["body"], text_color=COLORS["text_muted"],
                     justify="center").pack(expand=True, pady=80)

    # ── Loan detail view ─────────────────────────────────────────────────
    def _on_loan_selected(self, row):
        from app.core.services.loan_service import LoanService
        loan = LoanService.get_loan_by_id(row["id"])
        self.selected_loan = loan
        if loan: self._render_loan_detail(loan)

    def _render_loan_detail(self, loan):
        for w in self.detail_panel.winfo_children(): w.destroy()
        ctk.CTkLabel(self.detail_panel, text=loan.loan_number,
                     font=FONTS["subtitle"],
                     text_color=COLORS["accent_green_dark"]).pack(
            anchor="w", padx=20, pady=(20, 4))

        status_colors = {
            "pending":   COLORS["warning"],
            "approved":  COLORS["info"],
            "active":    COLORS["accent_green"],
            "completed": COLORS["text_muted"],
            "defaulted": COLORS["danger"],
            "rejected":  COLORS["danger"],
        }
        sc = status_colors.get(loan.status.value, COLORS["text_secondary"])
        ctk.CTkLabel(self.detail_panel, text=loan.status.value.upper(),
                     font=FONTS["badge"], text_color=sc).pack(anchor="w", padx=20)
        ctk.CTkFrame(self.detail_panel, fg_color=COLORS["border"],
                     height=1).pack(fill="x", padx=20, pady=12)

        from app.core.services.client_service import ClientService
        from app.core.services.repayment_service import RepaymentService
        client  = ClientService.get_client_by_id(loan.client_id)
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
            row.pack(fill="x", padx=20, pady=2)
            ctk.CTkLabel(row, text=label, font=FONTS["body_small"],
                         text_color=COLORS["text_muted"],
                         width=130, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value, font=FONTS["body_small"],
                         text_color=COLORS["text_primary"],
                         anchor="w").pack(side="left")

        # Collateral thumbnails
        from app.database.connection import get_db
        from app.core.models.collateral import Collateral
        with get_db() as db:
            collaterals = db.query(Collateral).filter_by(loan_id=loan.id).all()
            coll_data   = [(c.description, c.file_path) for c in collaterals]

        if coll_data:
            ctk.CTkFrame(self.detail_panel, fg_color=COLORS["border"],
                         height=1).pack(fill="x", padx=20, pady=8)
            ctk.CTkLabel(self.detail_panel, text="Collateral Documents",
                         font=FONTS["subheading"],
                         text_color=COLORS["text_secondary"]).pack(anchor="w", padx=20)
            coll_grid = ctk.CTkFrame(self.detail_panel, fg_color="transparent")
            coll_grid.pack(fill="x", padx=20, pady=8)
            for i, (desc, fpath) in enumerate(coll_data):
                tile = ctk.CTkFrame(coll_grid, fg_color=COLORS["bg_input"],
                                    corner_radius=6, width=80, height=80)
                tile.grid(row=0, column=i, padx=4)
                tile.grid_propagate(False)
                if os.path.exists(fpath):
                    try:
                        img = Image.open(fpath)
                        img.thumbnail((72, 72))
                        ctkimg = ctk.CTkImage(light_image=img, dark_image=img, size=(72, 72))
                        ctk.CTkLabel(tile, image=ctkimg, text="",
                                     fg_color="transparent").pack(expand=True)
                    except Exception:
                        ctk.CTkLabel(tile, text="DOC", font=FONTS["caption"],
                                     text_color=COLORS["text_muted"]).pack(expand=True)
                else:
                    ctk.CTkLabel(tile, text="DOC", font=FONTS["caption"],
                                 text_color=COLORS["text_muted"]).pack(expand=True)
                ctk.CTkLabel(coll_grid, text=desc[:12], font=FONTS["caption"],
                             text_color=COLORS["text_muted"]).grid(row=1, column=i, padx=4)

        ctk.CTkFrame(self.detail_panel, fg_color=COLORS["border"],
                     height=1).pack(fill="x", padx=20, pady=12)

        btn_frame = ctk.CTkFrame(self.detail_panel, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 8))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        if loan.status.value == "pending":
            ctk.CTkButton(btn_frame, text="✔  Approve",
                          fg_color=COLORS["accent_green"],
                          hover_color=COLORS["accent_green_dark"],
                          text_color="#FFFFFF", font=FONTS["button"],
                          corner_radius=8, height=38,
                          command=lambda: self._approve_loan(loan.id)).grid(
                row=0, column=0, padx=(0, 4), sticky="ew")
            ctk.CTkButton(btn_frame, text="✖  Reject",
                          command=lambda: self._reject_loan(loan.id),
                          **danger_button_style()).grid(
                row=0, column=1, padx=(4, 0), sticky="ew")
        elif loan.status.value == "active":
            ctk.CTkButton(btn_frame, text="💳  Record Payment",
                          command=lambda: self.master.show_screen("repayments"),
                          **primary_button_style()).grid(
                row=0, column=0, columnspan=2, sticky="ew")

        if loan.risk_score is None:
            ctk.CTkButton(self.detail_panel, text="🤖  Run AI Risk Assessment",
                          command=lambda: self.master.show_screen("agent"),
                          **secondary_button_style()).pack(
                fill="x", padx=20, pady=(0, 20))

    # ── New loan form ─────────────────────────────────────────────────────
    def _new_loan_form(self):
        self.selected_loan   = None
        self._collateral_files = []
        for w in self.detail_panel.winfo_children(): w.destroy()

        ctk.CTkLabel(self.detail_panel, text="New Loan Application",
                     font=FONTS["subtitle"],
                     text_color=COLORS["accent_green_dark"]).pack(
            anchor="w", padx=20, pady=(20, 16))

        self.loan_vars = {}

        # ── Client finder ─────────────────────────────────────────────
        self._section_label("Client Information")

        ctk.CTkLabel(self.detail_panel, text="Client NIN or Name *",
                     font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"],
                     anchor="w").pack(fill="x", padx=20, pady=(0, 2))
        self.client_search_var = ctk.StringVar()
        ctk.CTkEntry(
            self.detail_panel,
            textvariable=self.client_search_var,
            placeholder_text="e.g.  CM12345678  or  John Mukasa",
            **input_style(),
        ).pack(fill="x", padx=20)

        self.client_result_label = ctk.CTkLabel(
            self.detail_panel, text="", font=FONTS["caption"],
            text_color=COLORS["text_muted"])
        self.client_result_label.pack(anchor="w", padx=20)

        ctk.CTkButton(
            self.detail_panel, text="🔍  Find Client", height=32,
            font=FONTS["body_small"],
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            corner_radius=6,
            command=self._find_client,
        ).pack(anchor="w", padx=20, pady=(4, 12))

        # ── Loan details ──────────────────────────────────────────────
        self._section_label("Loan Details")

        ctk.CTkLabel(self.detail_panel, text="Loan Type *",
                     font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"],
                     anchor="w").pack(fill="x", padx=20, pady=(0, 2))
        self.loan_type_var = ctk.StringVar(value=LOAN_TYPES[0])
        ctk.CTkOptionMenu(
            self.detail_panel,
            variable=self.loan_type_var,
            values=LOAN_TYPES,
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_green"],
            text_color=COLORS["text_primary"],
            font=FONTS["body_small"],
        ).pack(fill="x", padx=20)

        # Principal amount
        ctk.CTkLabel(self.detail_panel, text="Principal Amount (UGX) *",
                     font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"],
                     anchor="w").pack(fill="x", padx=20, pady=(10, 2))
        var_p = ctk.StringVar()
        self.loan_vars["principal_amount"] = var_p
        ctk.CTkEntry(
            self.detail_panel,
            textvariable=var_p,
            placeholder_text="e.g.  500000",
            **input_style(),
        ).pack(fill="x", padx=20)

        # Duration
        ctk.CTkLabel(self.detail_panel, text="Duration (months) *",
                     font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"],
                     anchor="w").pack(fill="x", padx=20, pady=(10, 2))
        var_d = ctk.StringVar()
        self.loan_vars["duration_months"] = var_d
        ctk.CTkEntry(
            self.detail_panel,
            textvariable=var_d,
            placeholder_text="e.g.  12",
            **input_style(),
        ).pack(fill="x", padx=20)

        self.loan_vars["principal_amount"].trace_add("write", self._update_interest_preview)
        self.loan_vars["duration_months"].trace_add("write", self._update_interest_preview)

        # ── Application date ──────────────────────────────────────────
        ctk.CTkLabel(self.detail_panel, text="Application Date *",
                     font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"],
                     anchor="w").pack(fill="x", padx=20, pady=(10, 2))
        date_row = ctk.CTkFrame(self.detail_panel, fg_color="transparent")
        date_row.pack(fill="x", padx=20)
        date_row.columnconfigure(0, weight=1)
        self.application_date_picker = DatePicker(date_row, initial_date=date.today())
        self.application_date_picker.grid(row=0, column=0, sticky="ew")

        # ── Purpose ───────────────────────────────────────────────────
        ctk.CTkLabel(self.detail_panel, text="Purpose / Reason",
                     font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"],
                     anchor="w").pack(fill="x", padx=20, pady=(10, 2))
        self.purpose_var = ctk.StringVar()
        ctk.CTkEntry(
            self.detail_panel,
            textvariable=self.purpose_var,
            placeholder_text="e.g.  School fees, Business capital, Asset purchase...",
            **input_style(),
        ).pack(fill="x", padx=20)

        # Interest preview
        self.interest_preview = ctk.CTkLabel(
            self.detail_panel, text="",
            font=FONTS["body_small"],
            text_color=COLORS["accent_green_dark"])
        self.interest_preview.pack(anchor="w", padx=20, pady=(8, 0))

        # ── Collateral ────────────────────────────────────────────────
        self._section_label("Collateral Documents")

        ctk.CTkLabel(
            self.detail_panel,
            text="Attach photos or scans of collateral (land title, logbook, etc.)",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", padx=20, pady=(0, 8))

        coll_btn_row = ctk.CTkFrame(self.detail_panel, fg_color="transparent")
        coll_btn_row.pack(fill="x", padx=20)
        ctk.CTkButton(
            coll_btn_row, text="📎  Add Photo / Document",
            height=36, font=FONTS["body_small"],
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["accent_green_dark"],
            text_color="#FFFFFF", corner_radius=8,
            command=self._add_collateral,
        ).pack(side="left")

        self.coll_count_label = ctk.CTkLabel(
            coll_btn_row, text="No files added yet",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"])
        self.coll_count_label.pack(side="left", padx=(12, 0))

        self.coll_thumb_frame = ctk.CTkFrame(self.detail_panel, fg_color="transparent")
        self.coll_thumb_frame.pack(fill="x", padx=20, pady=8)

        # ── Error + Submit ─────────────────────────────────────────────
        self.loan_form_error = ctk.CTkLabel(
            self.detail_panel, text="",
            font=FONTS["body_small"], text_color=COLORS["danger"])
        self.loan_form_error.pack(padx=20, pady=(8, 0))

        ctk.CTkButton(
            self.detail_panel,
            text="✔  Submit Loan Application",
            command=self._submit_loan,
            **primary_button_style(),
        ).pack(fill="x", padx=20, pady=(12, 20))

        self.found_client_id = None

    def _section_label(self, text: str):
        """Render a styled section divider with a label."""
        ctk.CTkFrame(self.detail_panel, fg_color=COLORS["border"],
                     height=1).pack(fill="x", padx=20, pady=(14, 0))
        ctk.CTkLabel(
            self.detail_panel, text=text,
            font=FONTS["subheading"],
            text_color=COLORS["accent_green_dark"],
            anchor="w",
        ).pack(fill="x", padx=20, pady=(6, 6))

    # ── Collateral helpers ────────────────────────────────────────────────
    def _add_collateral(self):
        from tkinter import filedialog
        files = filedialog.askopenfilenames(
            title="Select Collateral Documents",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.bmp *.gif *.tiff"),
                ("PDF files",   "*.pdf"),
                ("All files",   "*.*"),
            ])
        if files:
            for f in files:
                if f not in self._collateral_files:
                    self._collateral_files.append(f)
            self._refresh_collateral_thumbs()

    def _refresh_collateral_thumbs(self):
        for w in self.coll_thumb_frame.winfo_children(): w.destroy()
        count = len(self._collateral_files)
        self.coll_count_label.configure(
            text=f"{count} file{'s' if count != 1 else ''} added")
        for i, fpath in enumerate(self._collateral_files):
            tile = ctk.CTkFrame(self.coll_thumb_frame,
                                fg_color=COLORS["bg_input"],
                                corner_radius=6, width=72, height=72)
            tile.grid(row=0, column=i * 2, padx=4, pady=4)
            tile.grid_propagate(False)
            try:
                img = Image.open(fpath)
                img.thumbnail((66, 66))
                ctkimg = ctk.CTkImage(light_image=img, dark_image=img, size=(66, 66))
                ctk.CTkLabel(tile, image=ctkimg, text="",
                             fg_color="transparent").pack(expand=True)
            except Exception:
                ext = os.path.splitext(fpath)[1].upper()
                ctk.CTkLabel(tile, text=ext or "DOC",
                             font=FONTS["caption"],
                             text_color=COLORS["text_muted"]).pack(expand=True)
            fname = os.path.basename(fpath)[:10]
            ctk.CTkLabel(self.coll_thumb_frame, text=fname,
                         font=FONTS["caption"],
                         text_color=COLORS["text_muted"]).grid(row=1, column=i * 2, padx=4)
            ctk.CTkButton(
                self.coll_thumb_frame, text="✕", width=20, height=20,
                fg_color=COLORS["danger"], hover_color="#A93226",
                text_color="#FFFFFF", font=("Helvetica", 10), corner_radius=4,
                command=lambda p=fpath: self._remove_collateral(p),
            ).grid(row=0, column=i * 2 + 1, sticky="n")

    def _remove_collateral(self, fpath):
        if fpath in self._collateral_files:
            self._collateral_files.remove(fpath)
        self._refresh_collateral_thumbs()

    # ── Client search ─────────────────────────────────────────────────────
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
                text=f"✔  Found: {c.full_name}  (NIN: {c.nin or '—'})",
                text_color=COLORS["accent_green"])
        else:
            self.found_client_id = None
            self.client_result_label.configure(
                text="✖  No client found. Please register the client first.",
                text_color=COLORS["danger"])

    # ── Interest preview ──────────────────────────────────────────────────
    def _update_interest_preview(self, *args):
        try:
            principal = float(self.loan_vars["principal_amount"].get())
            months    = int(self.loan_vars["duration_months"].get())
            interest  = principal * 0.10
            total     = principal + interest
            monthly   = total / months
            self.interest_preview.configure(
                text=(f"Interest: UGX {interest:,.0f}  |  "
                      f"Total: UGX {total:,.0f}  |  "
                      f"Monthly: UGX {monthly:,.0f}"))
        except Exception:
            self.interest_preview.configure(text="")

    # ── Submit ────────────────────────────────────────────────────────────
    def _submit_loan(self):
        from app.core.services.loan_service import LoanService
        from app.database.connection import get_db
        from app.core.models.collateral import Collateral
        from app.core.models.loan import Loan

        if not getattr(self, "found_client_id", None):
            self.loan_form_error.configure(
                text="⚠  Please find and select a client first.")
            return
        try:
            principal = float(self.loan_vars["principal_amount"].get())
            duration  = int(self.loan_vars["duration_months"].get())
            loan_type = self.loan_type_var.get()
            purpose   = self.purpose_var.get().strip() or None
            app_date  = self.application_date_picker.get_date()

            loan = LoanService.create_loan(
                client_id=self.found_client_id,
                loan_type=loan_type,
                principal_amount=principal,
                duration_months=duration,
                purpose=purpose,
                created_by_id=self.current_user.id if self.current_user else None,
            )
            with get_db() as db:
                l = db.query(Loan).filter_by(id=loan.id).first()
                if l:
                    l.application_date = app_date
                    db.commit()

            os.makedirs(COLLATERAL_UPLOAD_DIR, exist_ok=True)
            with get_db() as db:
                for fpath in self._collateral_files:
                    fname = f"loan_{loan.id}_{os.path.basename(fpath)}"
                    dest  = os.path.join(COLLATERAL_UPLOAD_DIR, fname)
                    shutil.copy2(fpath, dest)
                    coll = Collateral(
                        loan_id=loan.id,
                        description=os.path.splitext(
                            os.path.basename(fpath))[0][:100],
                        file_name=fname,
                        file_path=dest,
                        file_type=os.path.splitext(fpath)[1].lower(),
                        file_size_kb=int(os.path.getsize(fpath) / 1024),
                        uploaded_by_id=self.current_user.id if self.current_user else None,
                    )
                    db.add(coll)
                    db.commit()

            self.loan_form_error.configure(text="")
            self._collateral_files = []
            self._load_loans()
            self._show_empty_state()

        except Exception as e:
            self.loan_form_error.configure(text=f"⚠  {e}")

    # ── Approve / reject ──────────────────────────────────────────────────
    def _approve_loan(self, loan_id):
        from app.core.services.loan_service import LoanService
        LoanService.approve_loan(
            loan_id,
            approved_by_id=self.current_user.id if self.current_user else None)
        self._load_loans()
        self._show_empty_state()

    def _reject_loan(self, loan_id):
        from app.core.services.loan_service import LoanService
        LoanService.reject_loan(loan_id, reason="Rejected by officer.")
        self._load_loans()
        self._show_empty_state()

    # ── Load loans table ──────────────────────────────────────────────────
    def _load_loans(self, *args):
        from app.core.services.loan_service import LoanService
        from app.core.services.client_service import ClientService
        status = self.status_filter.get() if hasattr(self, "status_filter") else "All"
        search = self.search_var.get().strip() if hasattr(self, "search_var") else None
        loans  = LoanService.get_all_loans(
            status=None if status == "All" else status,
            search=search or None)
        rows = []
        for loan in loans:
            client = ClientService.get_client_by_id(loan.client_id)
            rows.append({
                "id":          loan.id,
                "loan_number": loan.loan_number,
                "client_name": client.full_name if client else "—",
                "loan_type":   loan.loan_type.value if loan.loan_type else "—",
                "principal":   f"UGX {loan.principal_amount:,.0f}",
                "status":      loan.status.value.upper(),
            })
        if hasattr(self, "table"):
            self.table.update_rows(rows)