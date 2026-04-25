"""
app/ui/screens/reports_screen.py
─────────────────────────────────
Reports screen — generate PDF and Word reports.
Each report asks the user WHERE to save via a native
file save dialog, instead of auto-saving to ./reports/.
"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import date

import customtkinter as ctk
from app.ui.styles.theme import COLORS, FONTS, primary_button_style, input_style
from app.ui.components.sidebar import Sidebar


class ReportsScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master       = master
        self.current_user = master.current_user
        self._build()

    # ── Navigation ─────────────────────────────────────────────────────────────

    def _navigate(self, screen: str):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    # ── Layout ─────────────────────────────────────────────────────────────────

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        Sidebar(self, "reports", self._navigate, self.current_user).grid(
            row=0, column=0, sticky="nsew")

        main = ctk.CTkScrollableFrame(
            self, fg_color=COLORS["bg_primary"],
            scrollbar_button_color=COLORS["accent_green"],
            scrollbar_button_hover_color=COLORS["accent_green_dark"],
        )
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)

        # ── Header ────────────────────────────────────────────────────────
        ctk.CTkFrame(main, fg_color=COLORS["accent_green"],
                     height=4, corner_radius=0).grid(
            row=0, column=0, sticky="ew")

        header = ctk.CTkFrame(main, fg_color="transparent")
        header.grid(row=1, column=0, sticky="ew", padx=32, pady=(20, 4))
        header.columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="Reports",
                     font=FONTS["title"],
                     text_color=COLORS["accent_green_dark"]).grid(
            row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text="Generate reports and agreements. "
                 "You will be asked where to save each file.",
            font=FONTS["body_small"],
            text_color=COLORS["text_muted"],
        ).grid(row=1, column=0, sticky="w")

        # Status / feedback label
        self.status_label = ctk.CTkLabel(
            main, text="",
            font=FONTS["body_small"],
            text_color=COLORS["accent_green"],
            wraplength=700, justify="left",
        )
        self.status_label.grid(row=2, column=0, sticky="w", padx=32, pady=(8, 4))

        # ── Report cards ───────────────────────────────────────────────────
        reports = [
            {
                "icon":  "P",
                "title": "Portfolio Summary",
                "desc":  "Full overview of all loans — counts by status and total portfolio value.",
                "pdf":   self._gen_portfolio_pdf,
                "word":  self._gen_portfolio_word,
            },
            {
                "icon":  "L",
                "title": "Loan Agreement  (with Collateral & Signatures)",
                "desc":  (
                    "Official loan agreement for a specific loan. Includes borrower details, "
                    "financial breakdown, terms, signature lines, and collateral documents. "
                    "Enter the loan number below."
                ),
                "pdf":       self._gen_loan_agreement,
                "word":      None,
                "extra":     "loan_number",
            },
            {
                "icon":  "!",
                "title": "Overdue Loans Report",
                "desc":  "All loans past their due date with client contact details and days overdue.",
                "pdf":   self._gen_overdue_pdf,
                "word":  None,
            },
            {
                "icon":  "R",
                "title": "Repayment History",
                "desc":  "All recorded payments across all loans — useful for auditing and reconciliation.",
                "pdf":   self._gen_repayments_pdf,
                "word":  None,
            },
            {
                "icon":  "C",
                "title": "Client Register",
                "desc":  "Full list of all registered clients with NIN, phone, district, and occupation.",
                "pdf":   self._gen_clients_pdf,
                "word":  self._gen_clients_word,
            },
        ]

        for i, r in enumerate(reports):
            self._build_report_card(main, r, row=3 + i)

        # Bottom padding
        ctk.CTkFrame(main, fg_color="transparent", height=32).grid(
            row=3 + len(reports), column=0)

    # ── Report card widget ─────────────────────────────────────────────────────

    def _build_report_card(self, parent, report: dict, row: int):
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(row=row, column=0, sticky="ew", padx=32, pady=8)
        card.columnconfigure(1, weight=1)

        # Badge
        badge = ctk.CTkFrame(
            card, fg_color=COLORS["accent_green"],
            width=42, height=42, corner_radius=21)
        badge.grid(row=0, column=0, rowspan=2, padx=20, pady=20, sticky="n")
        badge.pack_propagate(False)
        ctk.CTkLabel(
            badge, text=report["icon"],
            font=("Helvetica", 15, "bold"),
            text_color="#FFFFFF",
        ).pack(expand=True)

        # Title & description
        ctk.CTkLabel(
            card, text=report["title"],
            font=FONTS["subheading"],
            text_color=COLORS["accent_green_dark"],
            anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=(0, 16), pady=(18, 2))

        ctk.CTkLabel(
            card, text=report["desc"],
            font=FONTS["body_small"],
            text_color=COLORS["text_secondary"],
            anchor="w", wraplength=520, justify="left",
        ).grid(row=1, column=1, sticky="w", padx=(0, 16), pady=(0, 10))

        # Optional loan number input (for loan agreement)
        if report.get("extra") == "loan_number":
            input_row = ctk.CTkFrame(card, fg_color="transparent")
            input_row.grid(row=2, column=1, sticky="w", pady=(0, 12))
            ctk.CTkLabel(
                input_row, text="Loan Number:",
                font=FONTS["body_small"],
                text_color=COLORS["text_secondary"],
            ).pack(side="left")
            self.agreement_loan_var = ctk.StringVar()
            ctk.CTkEntry(
                input_row,
                textvariable=self.agreement_loan_var,
                placeholder_text="e.g. BG-2026-12345",
                width=200, height=36,
                fg_color=COLORS["bg_input"],
                border_color=COLORS["border"],
                border_width=1,
                text_color=COLORS["text_primary"],
                font=FONTS["body_small"],
                corner_radius=8,
            ).pack(side="left", padx=(8, 0))

        # Buttons
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.grid(row=0, column=2, rowspan=3, padx=16, pady=16, sticky="e")

        ctk.CTkButton(
            btn_frame, text="📄  PDF",
            width=100, height=38,
            fg_color=COLORS["danger"],
            hover_color="#A93226",
            text_color="white",
            font=FONTS["button"],
            corner_radius=8,
            command=report["pdf"],
        ).pack(pady=4)

        if report.get("word"):
            ctk.CTkButton(
                btn_frame, text="📝  Word",
                width=100, height=38,
                fg_color=COLORS.get("info", "#1A5276"),
                hover_color="#154360",
                text_color="white",
                font=FONTS["button"],
                corner_radius=8,
                command=report["word"],
            ).pack(pady=4)

    # ── Status helpers ─────────────────────────────────────────────────────────

    def _set_status(self, msg: str, color: str = None):
        self.after(0, lambda: self.status_label.configure(
            text=msg,
            text_color=color or COLORS["accent_green"],
        ))

    def _set_busy(self, busy: bool):
        """Show/hide a 'Generating…' indicator."""
        self.after(0, lambda: self.status_label.configure(
            text="⏳  Generating report, please wait…" if busy else "",
            text_color=COLORS["text_muted"],
        ))

    # ── Save dialog helper ─────────────────────────────────────────────────────

    def _ask_save_path(self, default_name: str, file_type: str) -> str | None:
        from app.ui.components.save_dialog import SaveDialog

        extension = ".pdf" if file_type == "pdf" else ".docx"
        dialog = SaveDialog(
            self.winfo_toplevel(),
            title        = "Save Report As",
            default_name = default_name,
            extension    = extension,
        )
        self.wait_window(dialog)
        return dialog.result
    def _open_file(self, path: str):
        """Open the saved file with the system default viewer."""
        try:
            import subprocess
            subprocess.Popen(["xdg-open", path])
        except Exception:
            pass

    # ── Generic runner ─────────────────────────────────────────────────────────

    def _run_report(self, default_name: str, file_type: str, generator_fn):
        """
        1. Ask the user where to save.
        2. Run generator_fn(save_path) in a background thread.
        3. Open the file on completion.

        generator_fn receives the chosen save path and must return it.
        """
        save_path = self._ask_save_path(default_name, file_type)
        if not save_path:
            self._set_status("Report cancelled.")
            return

        def _worker():
            self._set_busy(True)
            try:
                result_path = generator_fn(save_path)
                self._set_status(f"✔  Saved: {result_path}")
                self._open_file(result_path)
            except Exception as e:
                self._set_status(f"Error: {e}", COLORS["danger"])
            finally:
                self._set_busy(False)

        threading.Thread(target=_worker, daemon=True).start()

    # ── Report generators ──────────────────────────────────────────────────────

    def _gen_portfolio_pdf(self):
        self._run_report(
            default_name  = f"portfolio_summary_{date.today()}.pdf",
            file_type     = "pdf",
            generator_fn  = self._do_portfolio_pdf,
        )

    def _do_portfolio_pdf(self, save_path: str) -> str:
        from app.core.services.report_service import ReportService
        uid = self.current_user.id if self.current_user else None
        # Generate to temp location first, then copy to chosen path
        temp_path = ReportService.portfolio_summary_pdf(generated_by_id=uid)
        self._move(temp_path, save_path)
        return save_path

    def _gen_portfolio_word(self):
        self._run_report(
            default_name  = f"portfolio_summary_{date.today()}.docx",
            file_type     = "word",
            generator_fn  = self._do_portfolio_word,
        )

    def _do_portfolio_word(self, save_path: str) -> str:
        from app.core.services.report_service import ReportService
        uid = self.current_user.id if self.current_user else None
        temp_path = ReportService.portfolio_summary_word(generated_by_id=uid)
        self._move(temp_path, save_path)
        return save_path

    def _gen_overdue_pdf(self):
        self._run_report(
            default_name  = f"overdue_loans_{date.today()}.pdf",
            file_type     = "pdf",
            generator_fn  = self._do_overdue_pdf,
        )

    def _do_overdue_pdf(self, save_path: str) -> str:
        from app.core.services.report_service import ReportService
        uid = self.current_user.id if self.current_user else None
        temp_path = ReportService.overdue_report_pdf(generated_by_id=uid)
        self._move(temp_path, save_path)
        return save_path

    def _gen_repayments_pdf(self):
        self._run_report(
            default_name  = f"repayment_history_{date.today()}.pdf",
            file_type     = "pdf",
            generator_fn  = self._do_repayments_pdf,
        )

    def _do_repayments_pdf(self, save_path: str) -> str:
        from app.core.services.report_service import ReportService
        uid = self.current_user.id if self.current_user else None
        temp_path = ReportService.repayment_history_pdf(generated_by_id=uid)
        self._move(temp_path, save_path)
        return save_path

    def _gen_clients_pdf(self):
        self._run_report(
            default_name  = f"client_register_{date.today()}.pdf",
            file_type     = "pdf",
            generator_fn  = self._do_clients_pdf,
        )

    def _do_clients_pdf(self, save_path: str) -> str:
        from app.core.services.report_service import ReportService
        uid = self.current_user.id if self.current_user else None
        temp_path = ReportService.client_register_pdf(generated_by_id=uid)
        self._move(temp_path, save_path)
        return save_path

    def _gen_clients_word(self):
        self._run_report(
            default_name  = f"client_register_{date.today()}.docx",
            file_type     = "word",
            generator_fn  = self._do_clients_word,
        )

    def _do_clients_word(self, save_path: str) -> str:
        from app.core.services.report_service import ReportService
        uid = self.current_user.id if self.current_user else None
        temp_path = ReportService.client_register_word(generated_by_id=uid)
        self._move(temp_path, save_path)
        return save_path

    # ── Loan agreement ─────────────────────────────────────────────────────────

    def _gen_loan_agreement(self):
        loan_number = self.agreement_loan_var.get().strip()
        if not loan_number:
            self._set_status(
                "Please enter a loan number before generating the agreement.",
                COLORS["danger"])
            return

        self._run_report(
            default_name  = f"loan_agreement_{loan_number}.pdf",
            file_type     = "pdf",
            generator_fn  = lambda path: self._do_loan_agreement(loan_number, path),
        )

    def _do_loan_agreement(self, loan_number: str, save_path: str) -> str:
        from app.core.services.loan_service import LoanService
        from app.core.services.client_service import ClientService
        from app.core.services.report_service import ReportService

        # Find the loan
        loans = LoanService.get_all_loans()
        loan  = next((l for l in loans if l.loan_number == loan_number), None)
        if not loan:
            raise ValueError(f"Loan '{loan_number}' not found. Please check the loan number.")

        client    = ClientService.get_client_by_id(loan.client_id)
        uid       = self.current_user.id if self.current_user else None
        temp_path = ReportService.generate_loan_agreement(
            loan=loan, client=client, generated_by_id=uid)
        self._move(temp_path, save_path)
        return save_path

    # ── File move helper ───────────────────────────────────────────────────────

    @staticmethod
    def _move(src: str, dst: str):
        """
        Move generated report from the temp ./reports/ location
        to the user-chosen save path.
        """
        import shutil
        if os.path.abspath(src) != os.path.abspath(dst):
            shutil.move(src, dst)