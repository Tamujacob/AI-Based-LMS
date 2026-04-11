"""
app/ui/screens/agent_screen.py
─────────────────────────────────────────────
AI Risk Agent panel — risk scoring, portfolio scan,
and loan health summaries via Anthropic Claude API.
"""

import threading
import customtkinter as ctk
from app.ui.styles.theme import COLORS, FONTS, primary_button_style, secondary_button_style
from app.ui.components.sidebar import Sidebar


class AgentScreen(ctk.CTkFrame):
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

        Sidebar(self, "agent", self._navigate, self.current_user).grid(
            row=0, column=0, sticky="nsew"
        )

        main = ctk.CTkFrame(self, fg_color=COLORS["bg_primary"])
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        self._build_controls(main)
        self._build_output(main)

    # ── Left: Controls ─────────────────────────────────────────────────────
    def _build_controls(self, parent):
        panel = ctk.CTkScrollableFrame(parent, fg_color=COLORS["bg_card"],
                                       corner_radius=12,
                                       scrollbar_button_color=COLORS["bg_hover"])
        panel.grid(row=0, column=0, sticky="nsew", padx=(24, 8), pady=24)
        panel.columnconfigure(0, weight=1)

        # Header
        ctk.CTkLabel(panel, text="🤖", font=("Helvetica", 36)).pack(pady=(24, 4))
        ctk.CTkLabel(panel, text="AI Risk Agent", font=FONTS["subtitle"],
                     text_color=COLORS["accent_gold"]).pack()
        ctk.CTkLabel(panel, text="Powered by Anthropic Claude",
                     font=FONTS["caption"], text_color=COLORS["text_muted"]).pack(pady=(2, 24))

        ctk.CTkFrame(panel, fg_color=COLORS["border"], height=1).pack(fill="x", padx=20, pady=(0, 16))

        # Section 1: Single Loan Risk
        ctk.CTkLabel(panel, text="Assess Single Loan", font=FONTS["subheading"],
                     text_color=COLORS["text_primary"], anchor="w").pack(
            fill="x", padx=20, pady=(0, 8))
        ctk.CTkLabel(panel,
                     text="Enter a loan number to get a detailed\nrisk score and recommendation.",
                     font=FONTS["body_small"], text_color=COLORS["text_secondary"],
                     justify="left", anchor="w").pack(fill="x", padx=20)

        self.loan_number_var = ctk.StringVar()
        ctk.CTkEntry(panel, textvariable=self.loan_number_var,
                     placeholder_text="e.g. BG-2025-12345",
                     fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                     text_color=COLORS["text_primary"], font=FONTS["body"],
                     corner_radius=8, height=38, border_width=1).pack(
            fill="x", padx=20, pady=(8, 8))

        ctk.CTkButton(panel, text="⚡  Assess Risk",
                      command=self._assess_single_loan,
                      **primary_button_style()).pack(fill="x", padx=20, pady=(0, 16))

        ctk.CTkFrame(panel, fg_color=COLORS["border"], height=1).pack(fill="x", padx=20, pady=(0, 16))

        # Section 2: Portfolio Scan
        ctk.CTkLabel(panel, text="Portfolio Scan", font=FONTS["subheading"],
                     text_color=COLORS["text_primary"], anchor="w").pack(
            fill="x", padx=20, pady=(0, 8))
        ctk.CTkLabel(panel,
                     text="Scan all active loans and get a\nprioritised alert report.",
                     font=FONTS["body_small"], text_color=COLORS["text_secondary"],
                     justify="left", anchor="w").pack(fill="x", padx=20)

        ctk.CTkButton(panel, text="🔍  Scan Portfolio",
                      command=self._scan_portfolio,
                      **secondary_button_style()).pack(fill="x", padx=20, pady=(12, 16))

        ctk.CTkFrame(panel, fg_color=COLORS["border"], height=1).pack(fill="x", padx=20, pady=(0, 16))

        # Section 3: Overdue Alert
        ctk.CTkLabel(panel, text="Overdue Alerts", font=FONTS["subheading"],
                     text_color=COLORS["text_primary"], anchor="w").pack(
            fill="x", padx=20, pady=(0, 8))
        ctk.CTkLabel(panel,
                     text="Get a list of overdue loans with\nrecommended next actions.",
                     font=FONTS["body_small"], text_color=COLORS["text_secondary"],
                     justify="left", anchor="w").pack(fill="x", padx=20)

        ctk.CTkButton(panel, text="⚠️  Check Overdue",
                      command=self._check_overdue,
                      fg_color=COLORS["warning"], hover_color="#D68910",
                      text_color=COLORS["text_on_accent"], font=FONTS["button"],
                      corner_radius=8, height=40).pack(fill="x", padx=20, pady=(12, 24))

    # ── Right: Output Panel ─────────────────────────────────────────────────
    def _build_output(self, parent):
        output_frame = ctk.CTkFrame(parent, fg_color="transparent")
        output_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 24), pady=24)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(1, weight=1)

        ctk.CTkLabel(output_frame, text="Agent Output", font=FONTS["title"],
                     text_color=COLORS["text_primary"]).grid(
            row=0, column=0, sticky="w", pady=(0, 12))

        self.output_box = ctk.CTkTextbox(
            output_frame,
            fg_color=COLORS["bg_card"],
            text_color=COLORS["text_primary"],
            font=FONTS["mono"],
            corner_radius=12,
            wrap="word",
            state="disabled",
        )
        self.output_box.grid(row=1, column=0, sticky="nsew")

        ctk.CTkButton(output_frame, text="Clear Output", height=32,
                      font=FONTS["body_small"],
                      fg_color=COLORS["bg_hover"], hover_color=COLORS["bg_input"],
                      text_color=COLORS["text_secondary"], corner_radius=6,
                      command=self._clear_output).grid(
            row=2, column=0, sticky="e", pady=(8, 0))

        self._write_output(
            "Welcome to the AI Risk Agent.\n\n"
            "Choose an action on the left to get started.\n\n"
            "• Assess Single Loan — get a detailed risk score for one loan\n"
            "• Portfolio Scan — analyse all active loans at once\n"
            "• Check Overdue — get alerts on loans past their due date\n"
        )

    def _write_output(self, text: str):
        self.output_box.configure(state="normal")
        self.output_box.delete("1.0", "end")
        self.output_box.insert("1.0", text)
        self.output_box.configure(state="disabled")

    def _append_output(self, text: str):
        self.output_box.configure(state="normal")
        self.output_box.insert("end", text)
        self.output_box.configure(state="disabled")
        self.output_box.see("end")

    def _clear_output(self):
        self._write_output("")

    def _set_loading(self, message: str):
        self._write_output(f"⏳ {message}\n\nPlease wait...")

    # ── Agent Actions ──────────────────────────────────────────────────────

    def _assess_single_loan(self):
        loan_number = self.loan_number_var.get().strip()
        if not loan_number:
            self._write_output("⚠️ Please enter a loan number first.")
            return
        self._set_loading(f"Assessing loan {loan_number}...")
        threading.Thread(target=self._run_single_assessment,
                         args=(loan_number,), daemon=True).start()

    def _run_single_assessment(self, loan_number: str):
        try:
            from app.core.agents.ai_agent import AIAgent
            from app.core.services.loan_service import LoanService
            from app.core.services.client_service import ClientService
            from app.core.services.repayment_service import RepaymentService

            loans = LoanService.get_all_loans()
            loan = next((l for l in loans if l.loan_number == loan_number), None)
            if not loan:
                self.after(0, lambda: self._write_output(
                    f"✗ Loan '{loan_number}' not found. Check the number and try again."))
                return

            client = ClientService.get_client_by_id(loan.client_id)
            repayments = RepaymentService.get_repayments_for_loan(loan.id)
            balance = RepaymentService.get_outstanding_balance(loan.id)

            result = AIAgent.assess_loan_risk(loan, client, repayments, balance)
            self.after(0, lambda: self._write_output(result))

        except Exception as e:
            self.after(0, lambda: self._write_output(f"Error: {e}"))

    def _scan_portfolio(self):
        self._set_loading("Scanning entire loan portfolio...")
        threading.Thread(target=self._run_portfolio_scan, daemon=True).start()

    def _run_portfolio_scan(self):
        try:
            from app.core.agents.ai_agent import AIAgent
            from app.core.services.loan_service import LoanService
            from app.core.models.loan import LoanStatus

            loans = LoanService.get_all_loans(status="active")
            if not loans:
                self.after(0, lambda: self._write_output("No active loans found to scan."))
                return

            result = AIAgent.scan_portfolio(loans)
            self.after(0, lambda: self._write_output(result))

        except Exception as e:
            self.after(0, lambda: self._write_output(f"Error: {e}"))

    def _check_overdue(self):
        self._set_loading("Checking for overdue loans...")
        threading.Thread(target=self._run_overdue_check, daemon=True).start()

    def _run_overdue_check(self):
        try:
            from app.core.agents.ai_agent import AIAgent
            from app.core.services.loan_service import LoanService
            from app.core.services.client_service import ClientService

            overdue = LoanService.get_overdue_loans()
            if not overdue:
                self.after(0, lambda: self._write_output(
                    "✅ Great news! No overdue loans found at this time."))
                return

            result = AIAgent.overdue_alert(overdue, ClientService)
            self.after(0, lambda: self._write_output(result))

        except Exception as e:
            self.after(0, lambda: self._write_output(f"Error: {e}"))