"""
app/ui/components/statement_analysis_widget.py
──────────────────────────────────────────────────────────────
Reusable widget for uploading and analysing financial statements.

Embedded inside the new loan form in loans_screen.py.

v3 — brought to parity with the chatbot screen's StatementResultCard:
  - Identity row: client name, NIN, account number, period
  - KPI row: income used (ceiling), recent 3-month avg, avg expense,
    net monthly flow, latest balance
  - Monthly breakdown: 6 cards per row showing actual In/Out amounts
    (not just the old plain text dump)
  - Password field shrunk to small fixed width (4 digits only) with
    an eye toggle to show/hide, matching the chatbot screen's pattern
  - Stated income field shrunk to a reasonable width — it no longer
    stretches to fill the whole panel

v2 fix (kept): scenario cards keyed by duration_months (1/3/6), not by
name (Conservative/Standard/Extended) — matches the rewritten
LoanCeilingEngine/LoanScenario structure for Bingongold Credit's real
lending rule (max 6 months, typically 3 months).

on_accept callback signature unchanged:
    callback(principal: float, duration: int, ceiling_result)
"""

import os
import threading
import customtkinter as ctk
from app.ui.styles.theme import COLORS, FONTS, input_style


def _ugx(value) -> str:
    try:
        return f"UGX {int(float(value)):,}"
    except (TypeError, ValueError):
        return "UGX 0"


class StatementAnalysisWidget(ctk.CTkFrame):
    """
    Statement upload and analysis panel.
    Shows upload button, runs analysis, displays a full result card
    (identity, KPIs, monthly breakdown) and provides Accept buttons
    for the 1/3/6-month loan scenarios.
    """

    def __init__(self, master, on_accept=None, current_user=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_accept    = on_accept
        self.current_user = current_user
        self._result      = None
        self._ceiling     = None
        self._file_path   = None
        self._pw_visible  = False
        self._build()

    # ── Layout ─────────────────────────────────────────────────────────────────

    def _build(self):
        self.columnconfigure(0, weight=1)

        # Section header
        ctk.CTkLabel(
            self,
            text="Financial Statement Analysis",
            font=FONTS["subheading"],
            text_color=COLORS["accent_green_dark"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        ctk.CTkLabel(
            self,
            text="Upload a Mobile Money or bank statement PDF for AI-powered loan sizing.  "
                 "Optional — borrowers without digital accounts can use manual income entry below.",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="w",
            wraplength=360,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(0, 8))

        # ── Upload row ─────────────────────────────────────────────────────
        upload_row = ctk.CTkFrame(self, fg_color="transparent")
        upload_row.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        upload_row.columnconfigure(1, weight=1)

        self.upload_btn = ctk.CTkButton(
            upload_row,
            text="📎  Upload Statement",
            height=36, font=FONTS["button"],
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["accent_green_dark"],
            text_color="#FFFFFF", corner_radius=8,
            command=self._upload_statement,
        )
        self.upload_btn.grid(row=0, column=0, padx=(0, 8))

        self.file_label = ctk.CTkLabel(
            upload_row,
            text="No file selected",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self.file_label.grid(row=0, column=1, sticky="w")

        # Remove button — hidden until file selected
        self.remove_btn = ctk.CTkButton(
            upload_row,
            text="✕",
            width=32, height=32,
            fg_color=COLORS["danger"],
            hover_color="#A93226",
            text_color="#FFFFFF",
            font=("Helvetica", 11, "bold"),
            corner_radius=6,
            command=self._remove_file,
        )
        # Not gridded yet

        # ── Password field for encrypted PDFs ───────────────────────────────
        # Shrunk to a small fixed width (4 digits only) with an eye toggle,
        # matching the same pattern used in the chatbot screen's attachment
        # bar — no more stretching to fill the whole panel width.
        pwd_row = ctk.CTkFrame(self, fg_color="transparent")
        pwd_row.grid(row=3, column=0, sticky="w", pady=(0, 6))

        ctk.CTkLabel(
            pwd_row,
            text="🔒 PDF Password:",
            font=FONTS["body_small"],
            text_color=COLORS["text_secondary"],
        ).pack(side="left", padx=(0, 8))

        self.pdf_password_var = ctk.StringVar()

        # Digits-only, max 4 chars — enforced via StringVar trace (not
        # self.register()/validatecommand, which can crash on teardown).
        def _enforce_pw_format(*_args):
            raw = self.pdf_password_var.get()
            digits = "".join(ch for ch in raw if ch.isdigit())[:4]
            if digits != raw:
                self.pdf_password_var.set(digits)
        self.pdf_password_var.trace_add("write", _enforce_pw_format)

        self.pdf_password_entry = ctk.CTkEntry(
            pwd_row,
            textvariable=self.pdf_password_var,
            placeholder_text="••••",
            show="•",
            width=70,            # small fixed width — only 4 digits needed
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            font=FONTS["body_small"],
            corner_radius=8,
            height=32,
            border_width=1,
            justify="center",
        )
        self.pdf_password_entry.pack(side="left", padx=(0, 4))

        self.pdf_password_toggle = ctk.CTkButton(
            pwd_row,
            text="👁",
            width=32, height=32,
            font=FONTS["body_small"],
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_secondary"],
            corner_radius=8,
            command=self._toggle_password_visibility,
        )
        self.pdf_password_toggle.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            pwd_row,
            text="(last 4 digits of loan number, if encrypted)",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
        ).pack(side="left")

        # ── Stated income fallback ──────────────────────────────────────────
        # Also shrunk — this is a single number, not a paragraph, so it
        # doesn't need to stretch across the whole panel either.
        stated_row = ctk.CTkFrame(self, fg_color="transparent")
        stated_row.grid(row=4, column=0, sticky="w", pady=(0, 8))

        ctk.CTkLabel(
            stated_row,
            text="OR  Stated Monthly Income (UGX):",
            font=FONTS["body_small"],
            text_color=COLORS["text_secondary"],
        ).pack(side="left", padx=(0, 8))

        self.stated_income_var = ctk.StringVar()
        ctk.CTkEntry(
            stated_row,
            textvariable=self.stated_income_var,
            placeholder_text="e.g. 800,000",
            width=160,           # fixed, reasonable width for a number
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            font=FONTS["body_small"],
            corner_radius=8,
            height=32,
            border_width=1,
        ).pack(side="left")

        # ── Analyse button ─────────────────────────────────────────────────
        ctk.CTkButton(
            self,
            text="📊  Analyse & Get Recommendation",
            height=38, font=FONTS["button"],
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["accent_green_dark"],
            text_color="#FFFFFF", corner_radius=8,
            command=self._run_analysis,
        ).grid(row=5, column=0, sticky="ew", pady=(0, 10))

        # ── Full result card — identity / KPIs / monthly breakdown ─────────
        # Replaces the old plain-text results_box dump. Hidden until
        # analysis runs, then rebuilt fresh each time.
        self.result_card_frame = ctk.CTkFrame(self, fg_color="transparent")
        # Not gridded yet — gridded in _build_result_card()

        # ── Scenario cards frame — hidden until analysis runs ──────────────
        self.scenarios_frame = ctk.CTkFrame(self, fg_color="transparent")
        # Not gridded yet

        # ── Red flags frame — hidden until analysis runs ───────────────────
        self.flags_frame = ctk.CTkFrame(self, fg_color="transparent")
        # Not gridded yet

        # ── Single Accept button (original behaviour) ──────────────────────
        self.accept_btn = ctk.CTkButton(
            self,
            text="✔  Accept Standard Recommendation — Fill Loan Form",
            height=40, font=FONTS["button"],
            fg_color=COLORS["accent_gold"],
            hover_color=COLORS["accent_gold_dark"],
            text_color=COLORS["text_on_gold"],
            corner_radius=8,
            command=self._accept_standard,
            state="disabled",
        )
        self.accept_btn.grid(row=9, column=0, sticky="ew", pady=(0, 4))

    # ── Password visibility toggle ──────────────────────────────────────────────

    def _toggle_password_visibility(self):
        self._pw_visible = not self._pw_visible
        if self._pw_visible:
            self.pdf_password_entry.configure(show="")
            self.pdf_password_toggle.configure(text="🙈")
        else:
            self.pdf_password_entry.configure(show="•")
            self.pdf_password_toggle.configure(text="👁")

    # ── File handling ──────────────────────────────────────────────────────────

    def _upload_statement(self):
        from app.ui.components.save_dialog import OpenDialog

        filetypes = [
            ("PDF and Images", "*.pdf *.png *.jpg *.jpeg *.bmp *.tiff"),
            ("PDF files",      "*.pdf"),
            ("Images",         "*.png *.jpg *.jpeg *.bmp *.tiff"),
            ("All files",      "*.*"),
        ]

        dialog = OpenDialog(self.master, title="Select Bank or Mobile Money Statement",
                           filetypes=filetypes)
        self.master.wait_window(dialog)

        path = dialog.result
        if not path:
            return

        self._file_path = path
        fname = os.path.basename(path)

        self.file_label.configure(
            text=f"📄  {fname}",
            text_color=COLORS["accent_green_dark"],
        )
        self.upload_btn.configure(
            text="↻  Change File",
            fg_color=COLORS["accent_green_dark"],
        )
        self.remove_btn.grid(row=0, column=2, padx=(6, 0))

    def _remove_file(self):
        self._file_path = None
        self.file_label.configure(
            text="No file selected",
            text_color=COLORS["text_muted"],
        )
        self.upload_btn.configure(
            text="📎  Upload Statement",
            fg_color=COLORS["accent_green"],
        )
        self.remove_btn.grid_forget()
        self._reset_results()

    # ── Analysis ───────────────────────────────────────────────────────────────

    def _run_analysis(self):
        self._reset_results()
        threading.Thread(target=self._do_analysis, daemon=True).start()

    def _do_analysis(self):
        try:
            from app.core.agents.statement_parser import StatementParser
            from app.core.agents.loan_ceiling_engine import LoanCeilingEngine

            # Stated income
            stated = 0.0
            try:
                raw = self.stated_income_var.get().strip().replace(",", "")
                if raw:
                    stated = float(raw)
            except Exception:
                pass

            password = self.pdf_password_var.get().strip()

            parsed = None
            if self._file_path:
                parsed = StatementParser.parse(
                    self._file_path, password=password if password else None)
                self._result = parsed

            ceiling = LoanCeilingEngine.calculate(
                statement_result=parsed,
                stated_income=stated,
            )
            self._ceiling = ceiling

            self.after(0, self._build_result_card)
            self.after(0, self._show_scenario_cards)
            self.after(0, self._show_flags)
            self.after(0, lambda: self.accept_btn.configure(state="normal"))

        except Exception as e:
            self.after(0, lambda: self._show_analysis_error(str(e)))

    def _show_analysis_error(self, message: str):
        for w in self.result_card_frame.winfo_children():
            w.destroy()
        self.result_card_frame.grid(row=6, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkLabel(
            self.result_card_frame,
            text=f"⚠  Analysis error: {message}",
            font=FONTS["body_small"],
            text_color=COLORS["danger"],
            wraplength=400, justify="left",
        ).pack(anchor="w", padx=4, pady=8)

    # ── Result card — identity / KPIs / monthly breakdown ───────────────────────

    def _build_result_card(self):
        """
        Builds the full result card matching the chatbot screen's
        StatementResultCard: identity row, KPI row, monthly breakdown.
        Replaces the old plain-text dump in results_box.
        """
        for w in self.result_card_frame.winfo_children():
            w.destroy()

        r = self._result
        c = self._ceiling
        if not r and not c:
            return

        self.result_card_frame.grid(row=6, column=0, sticky="ew", pady=(0, 8))
        self.result_card_frame.columnconfigure(0, weight=1)

        card = ctk.CTkFrame(
            self.result_card_frame,
            fg_color=COLORS.get("bg_card", "#FFFFFF"),
            corner_radius=12,
            border_width=1,
            border_color=COLORS.get("border", "#E2E8F0"),
        )
        card.pack(fill="x")
        card.columnconfigure(0, weight=1)
        next_row = [0]   # mutable counter for dynamic row placement

        # ── Identity row ─────────────────────────────────────────────────
        if r:
            id_frame = ctk.CTkFrame(
                card, fg_color=COLORS.get("bg_input", "#F7FAFC"),
                corner_radius=8)
            id_frame.grid(row=next_row[0], column=0, sticky="ew",
                         padx=14, pady=(12, 6))
            next_row[0] += 1
            id_frame.columnconfigure((0, 1, 2, 3), weight=1, uniform="id")

            nin_display = r.nin or (
                "Not printed on this statement type"
                if r.statement_type in ("equity", "mtn_momo", "airtel")
                else "Not found in PDF")

            fields = [
                ("👤  Client Name", r.client_name or "Not found in PDF",
                 bool(r.client_name)),
                ("🪪  NIN", nin_display, bool(r.nin)),
                ("🏦  Account Number", r.account_number or "Not found in PDF",
                 bool(r.account_number)),
                ("📅  Period",
                 (f"{r.period_from.strftime('%b %Y')} – {r.period_to.strftime('%b %Y')}"
                  if r.period_from and r.period_to else "Not found in PDF"),
                 bool(r.period_from and r.period_to)),
            ]
            for i, (label, value, found) in enumerate(fields):
                cell = ctk.CTkFrame(id_frame, fg_color="transparent")
                cell.grid(row=0, column=i, padx=(10 if i == 0 else 4, 4),
                         pady=8, sticky="w")
                ctk.CTkLabel(
                    cell, text=label, font=FONTS.get("caption", ("Helvetica", 10)),
                    text_color=COLORS.get("text_muted", "#718096"), anchor="w",
                ).pack(anchor="w")
                ctk.CTkLabel(
                    cell, text=value,
                    font=FONTS.get("body_small", ("Helvetica", 11, "bold")),
                    text_color=(COLORS.get("text_primary", "#1A202C") if found
                                else COLORS.get("text_muted", "#718096")),
                    anchor="w", wraplength=140, justify="left",
                ).pack(anchor="w")

        # ── KPI row ──────────────────────────────────────────────────────
        if c or r:
            income_display = float(c.income_used) if c else (
                r.avg_monthly_income if r else 0)
            income_label = "Income used (ceiling)" if c else "Avg monthly income"
            expense_display = r.avg_monthly_expense if r else 0
            net_display = income_display - expense_display
            recent = getattr(r, "recent_avg_income", 0.0) if r else 0.0
            balance = getattr(r, "latest_balance", 0.0) if r else 0.0

            kpi_frame = ctk.CTkFrame(card, fg_color="transparent")
            kpi_frame.grid(row=next_row[0], column=0, sticky="ew",
                          padx=14, pady=6)
            next_row[0] += 1
            for i in range(5):
                kpi_frame.columnconfigure(i, weight=1, uniform="kpi")

            kpis = [
                (income_label, _ugx(income_display), COLORS.get("accent_green", "#276749")),
                ("Recent 3-month avg", _ugx(recent), COLORS.get("accent_green", "#276749")),
                ("Avg monthly expense", _ugx(expense_display), COLORS.get("danger", "#E53E3E")),
                ("Net monthly flow", _ugx(net_display),
                 COLORS.get("accent_green") if net_display >= 0 else COLORS.get("danger", "#E53E3E")),
                ("Latest balance", _ugx(balance) if balance > 0 else "N/A",
                 COLORS.get("text_secondary", "#4A5568")),
            ]
            for i, (label, value, color) in enumerate(kpis):
                cell = ctk.CTkFrame(kpi_frame, fg_color=COLORS.get("bg_input", "#F7FAFC"),
                                    corner_radius=8)
                cell.grid(row=0, column=i, padx=(0 if i == 0 else 4, 0), sticky="ew")
                ctk.CTkLabel(cell, text=label, font=FONTS.get("caption", ("Helvetica", 9)),
                            text_color=COLORS.get("text_muted", "#718096"), anchor="w",
                            wraplength=100).pack(anchor="w", padx=8, pady=(6, 0))
                ctk.CTkLabel(cell, text=value, font=FONTS.get("body_small", ("Helvetica", 12, "bold")),
                            text_color=color, anchor="w").pack(anchor="w", padx=8, pady=(2, 6))

        # ── Monthly breakdown — 6 per row ────────────────────────────────
        if r and r.monthly_summaries:
            self._build_monthly_breakdown(card, r, next_row)

        # ── Risk consistency badge ───────────────────────────────────────
        if r:
            cons_pct = round(r.income_consistency * 100)
            cons_color = (COLORS.get("accent_green", "#276749") if r.income_consistency >= 0.6
                          else COLORS.get("warning", "#D69E2E"))
            ctk.CTkLabel(
                card, text=f"{cons_pct}% income consistency  ·  {len(r.transactions)} transactions  ·  {r.months_covered} months",
                font=FONTS.get("caption", ("Helvetica", 11)),
                text_color=cons_color,
            ).grid(row=next_row[0], column=0, sticky="w", padx=14, pady=(4, 12))
            next_row[0] += 1

    def _build_monthly_breakdown(self, card, r, next_row):
        """6 cards per row, showing real In/Out UGX amounts per month."""
        section = ctk.CTkFrame(card, fg_color="transparent")
        section.grid(row=next_row[0], column=0, sticky="ew", padx=14, pady=(6, 4))
        next_row[0] += 1

        PER_ROW = 6
        for i in range(PER_ROW):
            section.columnconfigure(i, weight=1, uniform="month")

        ctk.CTkLabel(
            section, text="Monthly breakdown",
            font=FONTS.get("caption", ("Helvetica", 11)),
            text_color=COLORS.get("text_muted", "#718096"), anchor="w",
        ).grid(row=0, column=0, columnspan=PER_ROW, sticky="w", pady=(0, 6))

        max_val = max(
            (max(m.total_in, m.total_out) for m in r.monthly_summaries),
            default=1)

        for i, ms in enumerate(r.monthly_summaries):
            row_idx = 1 + (i // PER_ROW)
            col_idx = i % PER_ROW

            col = ctk.CTkFrame(section, fg_color=COLORS.get("bg_input", "#F7FAFC"),
                               corner_radius=8)
            col.grid(row=row_idx, column=col_idx,
                     padx=(0 if col_idx == 0 else 4, 0), pady=(0, 4), sticky="nsew")

            ctk.CTkLabel(col, text=ms.month, font=FONTS.get("caption", ("Helvetica", 10, "bold")),
                        text_color=COLORS.get("text_primary", "#1A202C"),
                        anchor="center").pack(anchor="center", padx=4, pady=(6, 4))

            for label, val, color_key in [("In", ms.total_in, "accent_green"),
                                          ("Out", ms.total_out, "danger")]:
                row_f = ctk.CTkFrame(col, fg_color="transparent")
                row_f.pack(fill="x", padx=6, pady=1)
                ctk.CTkLabel(row_f, text=label, font=FONTS.get("caption", ("Helvetica", 9)),
                            text_color=COLORS.get("text_muted", "#718096"),
                            width=20, anchor="w").pack(side="left")
                ctk.CTkLabel(row_f, text=_ugx(val), font=FONTS.get("caption", ("Helvetica", 9, "bold")),
                            text_color=COLORS.get(color_key, "#48BB78"),
                            anchor="e").pack(side="right")

            net = ms.total_in - ms.total_out
            net_color = (COLORS.get("accent_green", "#276749") if net >= 0
                        else COLORS.get("danger", "#E53E3E"))
            sign = "+" if net >= 0 else ""
            ctk.CTkLabel(col, text=f"Net: {sign}{_ugx(net)}",
                        font=FONTS.get("caption", ("Helvetica", 9, "bold")),
                        text_color=net_color).pack(anchor="center", padx=4, pady=(2, 6))

    # ── Reset / clear ────────────────────────────────────────────────────────────

    def _reset_results(self):
        self.accept_btn.configure(state="disabled")
        self.result_card_frame.grid_forget()
        for w in self.result_card_frame.winfo_children():
            w.destroy()
        self.scenarios_frame.grid_forget()
        for w in self.scenarios_frame.winfo_children():
            w.destroy()
        self.flags_frame.grid_forget()
        for w in self.flags_frame.winfo_children():
            w.destroy()

    # ── Loan scenario cards (1/3/6 month) ────────────────────────────────────────

    def _show_scenario_cards(self):
        """
        Build 3 scenario cards keyed by duration: 1-month, 3-month, 6-month.
        Colour-coded by risk_label (Low/Moderate/High/Very High) — the
        new source of truth from the rewritten LoanCeilingEngine.
        """
        if not self._ceiling or not self._ceiling.scenarios:
            return

        for w in self.scenarios_frame.winfo_children():
            w.destroy()

        self.scenarios_frame.grid(row=7, column=0, sticky="ew", pady=(0, 8))
        self.scenarios_frame.columnconfigure(0, weight=1)
        self.scenarios_frame.columnconfigure(1, weight=1)
        self.scenarios_frame.columnconfigure(2, weight=1)

        ctk.CTkLabel(
            self.scenarios_frame,
            text="Choose a Loan Duration:",
            font=FONTS["subheading"],
            text_color=COLORS["accent_green_dark"],
            anchor="w",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        risk_color_map = {
            "Low":       COLORS.get("accent_green", "#276749"),
            "Moderate":  COLORS.get("warning", "#D69E2E"),
            "High":      COLORS.get("danger", "#E53E3E"),
            "Very High": "#9B2335",
        }

        for i, scenario in enumerate(self._ceiling.scenarios):
            months     = scenario.duration_months
            risk_label = getattr(scenario, "risk_label", "Moderate")
            is_viable  = getattr(scenario, "is_viable", True)
            sc_color   = risk_color_map.get(risk_label, COLORS["accent_green"])
            is_typical = (months == 3)

            card = ctk.CTkFrame(
                self.scenarios_frame,
                fg_color=COLORS["bg_card"],
                corner_radius=8,
                border_width=2,
                border_color=(COLORS["accent_green"] if is_typical else sc_color),
            )
            card.grid(row=1, column=i, padx=4, sticky="nsew")

            ctk.CTkFrame(card, fg_color=sc_color, height=4, corner_radius=0).pack(fill="x")

            if is_typical:
                ctk.CTkLabel(
                    card, text="✦ typical loan",
                    font=FONTS.get("caption", ("Helvetica", 10)),
                    text_color=COLORS["accent_green"],
                ).pack(pady=(6, 0))

            ctk.CTkLabel(
                card, text=f"{months}-Month Loan",
                font=FONTS["badge"], text_color=COLORS["text_primary"],
            ).pack(pady=(6 if not is_typical else 2, 2))

            ctk.CTkLabel(
                card, text=f"UGX {float(scenario.principal):,.0f}",
                font=FONTS["subheading"], text_color=COLORS["text_primary"],
            ).pack()

            ctk.CTkLabel(
                card, text=f"UGX {float(scenario.monthly_instalment):,.0f}/mo",
                font=FONTS["body_small"], text_color=COLORS["text_secondary"],
            ).pack(pady=(2, 4))

            aff_pct = float(getattr(scenario, "affordability_pct", 0))
            ctk.CTkLabel(
                card, text=f"{aff_pct:.0f}% of income  ·  {risk_label} Risk",
                font=FONTS["caption"], text_color=sc_color,
            ).pack(pady=(0, 2))

            if not is_viable:
                ctk.CTkLabel(
                    card, text="⚠ High repayment risk",
                    font=FONTS["caption"], text_color=COLORS["danger"],
                ).pack(pady=(0, 4))

            ctk.CTkButton(
                card, text="✔ Accept", height=28,
                font=FONTS["caption"],
                fg_color=(sc_color if is_viable else COLORS["bg_input"]),
                hover_color=COLORS["accent_green_dark"],
                text_color=("#FFFFFF" if is_viable else COLORS["text_primary"]),
                corner_radius=6,
                command=lambda s=scenario: self._accept_scenario(s),
            ).pack(fill="x", padx=8, pady=(4, 10))

    def _show_flags(self):
        """Show red flags and warnings below scenarios."""
        if not self._ceiling:
            return

        all_flags = (
            [(f, "danger") for f in self._ceiling.red_flags] +
            [(w, "muted")  for w in self._ceiling.warnings]
        )
        if not all_flags:
            return

        for w in self.flags_frame.winfo_children():
            w.destroy()

        self.flags_frame.grid(row=8, column=0, sticky="ew", pady=(0, 8))
        self.flags_frame.columnconfigure(0, weight=1)

        for text, kind in all_flags:
            color = COLORS["danger"] if kind == "danger" else COLORS["text_muted"]
            prefix = "⚠ " if kind == "danger" else "ℹ "
            ctk.CTkLabel(
                self.flags_frame,
                text=f"{prefix}{text}",
                font=FONTS["body_small"],
                text_color=color,
                anchor="w",
                wraplength=360,
                justify="left",
            ).grid(sticky="w", pady=1)

    # ── Accept handlers ────────────────────────────────────────────────────────

    def _accept_scenario(self, scenario):
        """Called when staff clicks Accept on a specific duration card."""
        months = scenario.duration_months
        if self.on_accept:
            self.on_accept(
                float(scenario.principal),
                months,
                self._ceiling,
            )
        self.accept_btn.configure(
            text=(f"✔  {months}-month loan accepted — "
                  f"UGX {float(scenario.principal):,.0f}"),
            state="disabled",
        )

    def _accept_standard(self):
        """Accept the typical Bingongold loan — the 3-month scenario."""
        if not self._ceiling or not self._ceiling.scenarios:
            return
        scenarios = self._ceiling.scenarios
        scenario  = next(
            (s for s in scenarios if getattr(s, "duration_months", None) == 3),
            scenarios[len(scenarios) // 2] if scenarios else None,
        )
        if scenario:
            self._accept_scenario(scenario)

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_statement_result(self):
        """Return parsed StatementResult or None."""
        return self._result

    def get_ceiling_result(self):
        """Return CeilingResult or None."""
        return self._ceiling