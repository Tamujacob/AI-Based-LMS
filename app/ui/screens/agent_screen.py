"""
app/ui/screens/agent_screen.py
──────────────────────────────────────────────────────────────
AI Agent screen — updated to use AICore (unified AI class).

New additions:
  • Model status indicator (offline/online)
  • Retrain Model button
  • Credit Score lookup
  • Reminders panel
"""

import threading
import customtkinter as ctk
from app.ui.styles.theme import COLORS, FONTS, primary_button_style, secondary_button_style, input_style
from app.ui.components.sidebar import Sidebar


class AgentScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master       = master
        self.current_user = master.current_user
        self._build()
        self._load_model_status()
        self._load_reminders()

    def _navigate(self, screen):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        Sidebar(self, "agent", self._navigate, self.current_user).grid(
            row=0, column=0, sticky="nsew")

        main = ctk.CTkFrame(self, fg_color=COLORS["bg_primary"])
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(1, weight=1)

        self._build_header(main)
        self._build_left(main)
        self._build_right(main)

    def _build_header(self, parent):
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(20, 8))
        hdr.columnconfigure(1, weight=1)

        ctk.CTkLabel(hdr, text="AI Agent", font=FONTS["title"],
                     text_color=COLORS["accent_green_dark"]).grid(
            row=0, column=0, sticky="w")

        self.model_status_label = ctk.CTkLabel(
            hdr, text="Checking model...",
            font=FONTS["caption"], text_color=COLORS["text_muted"])
        self.model_status_label.grid(row=1, column=0, sticky="w")

        ctk.CTkButton(hdr, text="Retrain Local Model", width=160, height=34,
                      fg_color=COLORS["accent_gold"],
                      hover_color=COLORS["accent_gold_dark"],
                      text_color=COLORS["text_on_gold"],
                      font=FONTS["button"], corner_radius=8,
                      command=self._retrain_model).grid(
            row=0, column=2, sticky="e")

    def _build_left(self, parent):
        left = ctk.CTkScrollableFrame(parent, fg_color="transparent",
                                       scrollbar_button_color=COLORS["border"])
        left.grid(row=1, column=0, sticky="nsew", padx=(24, 8), pady=(0, 24))
        left.columnconfigure(0, weight=1)

        # ── Assess Single Loan ────────────────────────────────────────────
        self._card(left, row=0, title="Assess Single Loan",
                   desc="Run a full risk assessment on one loan using the local AI model + Claude.",
                   entry_placeholder="Loan number  e.g. BG-2025-12345",
                   btn_text="Assess Loan",
                   btn_cmd=self._assess_loan,
                   entry_attr="loan_number_entry")

        # ── Scan Portfolio ────────────────────────────────────────────────
        self._card(left, row=1, title="Scan Full Portfolio",
                   desc="Analyse all active loans and get a prioritised action report.",
                   btn_text="Scan Portfolio",
                   btn_cmd=self._scan_portfolio)

        # ── Overdue Alerts ────────────────────────────────────────────────
        self._card(left, row=2, title="Overdue Alerts & Collections",
                   desc="Generate a collections action plan for all overdue loans.",
                   btn_text="Check Overdue",
                   btn_cmd=self._check_overdue)

        # ── Credit Score ──────────────────────────────────────────────────
        self._card(left, row=3, title="Client Credit Score",
                   desc="Calculate the internal credit score (0–100) for a client.",
                   entry_placeholder="Client name or NIN",
                   btn_text="Get Credit Score",
                   btn_cmd=self._get_credit_score,
                   entry_attr="credit_client_entry")

    def _card(self, parent, row, title, desc, btn_text, btn_cmd,
              entry_placeholder=None, entry_attr=None):
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"],
                             corner_radius=10, border_width=1,
                             border_color=COLORS["border"])
        card.grid(row=row, column=0, sticky="ew", pady=8)
        card.columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text=title, font=FONTS["subheading"],
                     text_color=COLORS["accent_green_dark"],
                     anchor="w").pack(fill="x", padx=16, pady=(14, 2))
        ctk.CTkLabel(card, text=desc, font=FONTS["caption"],
                     text_color=COLORS["text_muted"],
                     anchor="w", wraplength=320).pack(fill="x", padx=16, pady=(0, 8))

        if entry_placeholder:
            entry = ctk.CTkEntry(card, placeholder_text=entry_placeholder,
                                 **input_style())
            entry.pack(fill="x", padx=16, pady=(0, 8))
            if entry_attr:
                setattr(self, entry_attr, entry)

        ctk.CTkButton(card, text=btn_text, height=36,
                      fg_color=COLORS["accent_green"],
                      hover_color=COLORS["accent_green_dark"],
                      text_color="#FFFFFF", font=FONTS["button"],
                      corner_radius=8,
                      command=btn_cmd).pack(fill="x", padx=16, pady=(0, 16))

    def _build_right(self, parent):
        right = ctk.CTkFrame(parent, fg_color="transparent")
        right.grid(row=1, column=1, sticky="nsew", padx=(8, 24), pady=(0, 24))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        right.rowconfigure(3, weight=0)

        ctk.CTkLabel(right, text="AI Output", font=FONTS["subheading"],
                     text_color=COLORS["accent_green_dark"],
                     anchor="w").grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.output_box = ctk.CTkTextbox(
            right, fg_color=COLORS["bg_card"],
            text_color=COLORS["text_primary"],
            font=("Courier", 11), wrap="word",
            corner_radius=10, border_width=1,
            border_color=COLORS["border"])
        self.output_box.grid(row=1, column=0, sticky="nsew")
        self.output_box.insert("end", "Click any action on the left to run an AI analysis.\n\n"
                               "Results will appear here.")
        self.output_box.configure(state="disabled")

        # Reminders panel
        ctk.CTkLabel(right, text="Payment Reminders",
                     font=FONTS["subheading"],
                     text_color=COLORS["accent_green_dark"],
                     anchor="w").grid(row=2, column=0, sticky="w", pady=(16, 4))

        self.reminders_frame = ctk.CTkScrollableFrame(
            right, fg_color=COLORS["bg_card"],
            corner_radius=10, border_width=1,
            border_color=COLORS["border"], height=200,
            scrollbar_button_color=COLORS["border"])
        self.reminders_frame.grid(row=3, column=0, sticky="ew")
        self.reminders_frame.columnconfigure(0, weight=1)

    # ── Actions ────────────────────────────────────────────────────────────────

    def _set_output(self, text: str):
        self.after(0, lambda: self._do_set_output(text))

    def _do_set_output(self, text: str):
        self.output_box.configure(state="normal")
        self.output_box.delete("1.0", "end")
        self.output_box.insert("end", text)
        self.output_box.configure(state="disabled")

    def _assess_loan(self):
        loan_num = self.loan_number_entry.get().strip()
        if not loan_num:
            self._set_output("Please enter a loan number first.")
            return
        self._set_output("Running risk assessment... please wait.")

        def run():
            from app.core.services.loan_service import LoanService
            from app.core.agents.ai_core import AICore
            loans = LoanService.get_all_loans()
            loan  = next((l for l in loans if l.loan_number.upper() == loan_num.upper()), None)
            if not loan:
                self._set_output(f"Loan '{loan_num}' not found.")
                return
            AICore.assess_single_loan(loan.id, callback=self._set_output)

        threading.Thread(target=run, daemon=True).start()

    def _scan_portfolio(self):
        self._set_output("Scanning portfolio... please wait.")
        threading.Thread(
            target=lambda: __import__("app.core.agents.ai_core", fromlist=["AICore"])
            .AICore.scan_portfolio(callback=self._set_output),
            daemon=True).start()

    def _check_overdue(self):
        self._set_output("Checking overdue loans... please wait.")
        threading.Thread(
            target=lambda: __import__("app.core.agents.ai_core", fromlist=["AICore"])
            .AICore.overdue_alerts(callback=self._set_output),
            daemon=True).start()

    def _get_credit_score(self):
        term = self.credit_client_entry.get().strip()
        if not term:
            self._set_output("Please enter a client name or NIN.")
            return
        self._set_output("Calculating credit score...")

        def run():
            from app.core.services.client_service import ClientService
            from app.core.agents.credit_scorer import CreditScorer
            clients = ClientService.get_all_clients(search=term)
            if not clients:
                self._set_output(f"No client found for '{term}'.")
                return
            c      = clients[0]
            result = CreditScorer.score_client(c.id)
            output = (
                f"CLIENT CREDIT SCORE\n"
                f"{'='*40}\n"
                f"Client:  {result.client_name}\n"
                f"Score:   {result.score}/100  [{result.band}]\n\n"
                f"{result.summary}\n\n"
                f"Factors:\n"
                + "\n".join(f"  • {f}" for f in result.factors)
            )
            self._set_output(output)

        threading.Thread(target=run, daemon=True).start()

    def _retrain_model(self):
        self._set_output("Starting model training...\n")

        def run():
            from app.core.agents.model_trainer import ModelTrainer

            def progress(msg):
                self.after(0, lambda m=msg: self._append_output(m))

            result = ModelTrainer.train(progress_callback=progress)
            self._set_output(
                f"{'✓ SUCCESS' if result['success'] else '✗ FAILED'}\n\n"
                f"{result['message']}"
            )
            self._load_model_status()

        threading.Thread(target=run, daemon=True).start()

    def _append_output(self, text: str):
        self.output_box.configure(state="normal")
        self.output_box.insert("end", text + "\n")
        self.output_box.configure(state="disabled")

    def _load_model_status(self):
        try:
            from app.core.agents.local_scorer import LocalScorer
            status = LocalScorer.model_status()
            self.after(0, lambda: self.model_status_label.configure(text=status))
        except Exception:
            pass

    def _load_reminders(self):
        def run():
            try:
                from app.core.agents.reminder_service import ReminderService
                reminders = ReminderService.get_all_due_reminders()
                self.after(0, lambda: self._render_reminders(reminders))
            except Exception:
                pass

        threading.Thread(target=run, daemon=True).start()

    def _render_reminders(self, reminders):
        for w in self.reminders_frame.winfo_children():
            w.destroy()

        if not reminders:
            ctk.CTkLabel(self.reminders_frame,
                         text="No upcoming or overdue payments.",
                         font=FONTS["body_small"],
                         text_color=COLORS["text_muted"]).pack(pady=16)
            return

        urgency_colors = {
            "overdue":  COLORS["danger"],
            "urgent":   COLORS["warning"],
            "standard": COLORS["accent_green"],
            "gentle":   COLORS["text_muted"],
        }

        for r in reminders[:10]:
            color = urgency_colors.get(r.urgency, COLORS["text_secondary"])
            row   = ctk.CTkFrame(self.reminders_frame, fg_color="transparent")
            row.pack(fill="x", pady=3)

            ctk.CTkLabel(row, text=r.loan_number, font=FONTS["badge"],
                         text_color=color, width=120, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=r.client_name[:18],
                         font=FONTS["body_small"],
                         text_color=COLORS["text_primary"],
                         anchor="w").pack(side="left", padx=(4, 0))

            days_text = (f"{abs(r.days_until)}d overdue"
                         if r.days_until < 0 else
                         f"due in {r.days_until}d")
            ctk.CTkLabel(row, text=days_text, font=FONTS["caption"],
                         text_color=color).pack(side="right", padx=8)

            # Copy message button
            ctk.CTkButton(
                row, text="Copy", width=50, height=24,
                fg_color=COLORS["bg_input"],
                hover_color=COLORS["border"],
                text_color=COLORS["text_secondary"],
                font=FONTS["caption"], corner_radius=4,
                command=lambda msg=r.message: self._copy_to_clipboard(msg)
            ).pack(side="right")

    def _copy_to_clipboard(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        self._set_output(
            "Message copied to clipboard!\n\n"
            "Paste it directly into WhatsApp or SMS.\n\n"
            "─────────────────────────────────\n"
            + text
        )