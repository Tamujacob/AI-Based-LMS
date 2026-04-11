"""
app/ui/screens/reports_screen.py
─────────────────────────────────────────────
Generate PDF and Word reports for loan portfolio,
individual loans, and repayment summaries.
"""

import threading
import customtkinter as ctk
from datetime import date
from app.ui.styles.theme import COLORS, FONTS, primary_button_style, secondary_button_style
from app.ui.components.sidebar import Sidebar


class ReportsScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master = master
        self.current_user = master.current_user
        self._build()

    def _navigate(self, screen):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        Sidebar(self, "reports", self._navigate, self.current_user).grid(
            row=0, column=0, sticky="nsew"
        )

        main = ctk.CTkScrollableFrame(
            self, fg_color=COLORS["bg_primary"],
            scrollbar_button_color=COLORS["bg_hover"])
        main.grid(row=0, column=1, sticky="nsew", padx=0)
        main.columnconfigure(0, weight=1)

        # Header
        ctk.CTkLabel(main, text="Reports", font=FONTS["title"],
                     text_color=COLORS["text_primary"]).grid(
            row=0, column=0, sticky="w", padx=32, pady=(28, 4))
        ctk.CTkLabel(main, text="Generate PDF and Word reports for management and auditing.",
                     font=FONTS["body"], text_color=COLORS["text_secondary"]).grid(
            row=1, column=0, sticky="w", padx=32, pady=(0, 24))

        # Status label
        self.status_label = ctk.CTkLabel(main, text="", font=FONTS["body_small"],
                                          text_color=COLORS["success"])
        self.status_label.grid(row=2, column=0, sticky="w", padx=32, pady=(0, 16))

        # Report cards
        reports = [
            {
                "icon": "📊",
                "title": "Portfolio Summary",
                "desc": "Full overview of all loans — counts by status, total portfolio value, outstanding balances.",
                "pdf_action": self._gen_portfolio_pdf,
                "word_action": self._gen_portfolio_word,
            },
            {
                "icon": "⚠️",
                "title": "Overdue Loans Report",
                "desc": "List of all loans past their due date with client contact details.",
                "pdf_action": self._gen_overdue_pdf,
                "word_action": None,
            },
            {
                "icon": "💳",
                "title": "Repayment History",
                "desc": "All payments recorded, grouped by loan. Useful for auditing.",
                "pdf_action": self._gen_repayments_pdf,
                "word_action": None,
            },
            {
                "icon": "👥",
                "title": "Client Register",
                "desc": "Full list of registered clients with contact and NIN details.",
                "pdf_action": self._gen_clients_pdf,
                "word_action": self._gen_clients_word,
            },
        ]

        for i, r in enumerate(reports):
            self._build_report_card(main, r, row=3 + i)

    def _build_report_card(self, parent, report: dict, row: int):
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=12)
        card.grid(row=row, column=0, sticky="ew", padx=32, pady=8)
        card.columnconfigure(1, weight=1)

        # Icon
        ctk.CTkLabel(card, text=report["icon"], font=("Helvetica", 30)).grid(
            row=0, column=0, rowspan=2, padx=24, pady=20)

        # Title + desc
        ctk.CTkLabel(card, text=report["title"], font=FONTS["subheading"],
                     text_color=COLORS["text_primary"], anchor="w").grid(
            row=0, column=1, sticky="w", padx=(0, 16), pady=(20, 2))
        ctk.CTkLabel(card, text=report["desc"], font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"], anchor="w",
                     wraplength=500).grid(
            row=1, column=1, sticky="w", padx=(0, 16), pady=(0, 20))

        # Buttons
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.grid(row=0, column=2, rowspan=2, padx=16, pady=16)

        ctk.CTkButton(btn_frame, text="📄 PDF", width=100, height=36,
                      fg_color=COLORS["danger"], hover_color="#C0392B",
                      text_color="white", font=FONTS["button"], corner_radius=8,
                      command=report["pdf_action"]).pack(pady=4)

        if report["word_action"]:
            ctk.CTkButton(btn_frame, text="📝 Word", width=100, height=36,
                          fg_color=COLORS["info"], hover_color="#1A5276",
                          text_color="white", font=FONTS["button"], corner_radius=8,
                          command=report["word_action"]).pack(pady=4)

    def _set_status(self, msg: str, color: str = None):
        self.after(0, lambda: self.status_label.configure(
            text=msg,
            text_color=color or COLORS["success"]
        ))

    # ── PDF Generators ─────────────────────────────────────────────────────

    def _gen_portfolio_pdf(self):
        threading.Thread(target=self._run_portfolio_pdf, daemon=True).start()

    def _run_portfolio_pdf(self):
        try:
            from app.core.services.report_service import ReportService
            path = ReportService.portfolio_summary_pdf()
            self._set_status(f"✔ PDF saved: {path}")
        except Exception as e:
            self._set_status(f"Error: {e}", COLORS["danger"])

    def _gen_portfolio_word(self):
        threading.Thread(target=self._run_portfolio_word, daemon=True).start()

    def _run_portfolio_word(self):
        try:
            from app.core.services.report_service import ReportService
            path = ReportService.portfolio_summary_word()
            self._set_status(f"✔ Word doc saved: {path}")
        except Exception as e:
            self._set_status(f"Error: {e}", COLORS["danger"])

    def _gen_overdue_pdf(self):
        threading.Thread(target=self._run_overdue_pdf, daemon=True).start()

    def _run_overdue_pdf(self):
        try:
            from app.core.services.report_service import ReportService
            path = ReportService.overdue_report_pdf()
            self._set_status(f"✔ PDF saved: {path}")
        except Exception as e:
            self._set_status(f"Error: {e}", COLORS["danger"])

    def _gen_repayments_pdf(self):
        threading.Thread(target=self._run_repayments_pdf, daemon=True).start()

    def _run_repayments_pdf(self):
        try:
            from app.core.services.report_service import ReportService
            path = ReportService.repayment_history_pdf()
            self._set_status(f"✔ PDF saved: {path}")
        except Exception as e:
            self._set_status(f"Error: {e}", COLORS["danger"])

    def _gen_clients_pdf(self):
        threading.Thread(target=self._run_clients_pdf, daemon=True).start()

    def _run_clients_pdf(self):
        try:
            from app.core.services.report_service import ReportService
            path = ReportService.client_register_pdf()
            self._set_status(f"✔ PDF saved: {path}")
        except Exception as e:
            self._set_status(f"Error: {e}", COLORS["danger"])

    def _gen_clients_word(self):
        threading.Thread(target=self._run_clients_word, daemon=True).start()

    def _run_clients_word(self):
        try:
            from app.core.services.report_service import ReportService
            path = ReportService.client_register_word()
            self._set_status(f"✔ Word doc saved: {path}")
        except Exception as e:
            self._set_status(f"Error: {e}", COLORS["danger"])