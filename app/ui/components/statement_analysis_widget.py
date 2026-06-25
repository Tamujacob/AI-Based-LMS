"""
app/ui/components/statement_analysis_widget.py
──────────────────────────────────────────────────────────────
Reusable widget for uploading and analysing financial statements.

Embedded inside the new loan form in loans_screen.py.

v2 fix — updated for the rewritten LoanCeilingEngine which now returns
exactly 3 scenarios keyed by DURATION (1/3/6 months), not by NAME
(Conservative/Standard/Extended). The old LoanScenario dataclass had
`.name` and `.affordability_pct` as a plain float; the new one has
`.duration_months`, `.risk_label`, `.is_viable`, and `.affordability_pct`
already expressed as a 0-100 number (not 0-1). This widget was crashing
with "'LoanScenario' object has no attribute 'name'" because it was
never updated when the engine was rewritten for Bingongold Credit's
real 1/3/6-month lending rule.

Changes from original:
  - Scenario cards now keyed by duration_months (1/3/6), not name
  - 3-month card highlighted as "typical loan" (Bingongold's most common)
  - Risk label + viability badge shown per card (Low/Moderate/High/Very High)
  - Added Remove file button
  - Added red flags and warnings display below results
  - Kept stated income fallback field (important for manual entry)
  - Kept separate Analyse button (staff controls when it runs)
  - on_accept callback signature unchanged:
      callback(principal: float, duration: int, ceiling_result)
"""

import os
import threading
import customtkinter as ctk
from app.ui.styles.theme import COLORS, FONTS, input_style


class StatementAnalysisWidget(ctk.CTkFrame):
    """
    Statement upload and analysis panel.
    Shows upload button, runs analysis, displays results,
    and provides Accept buttons for the 1/3/6-month loan scenarios.
    """

    def __init__(self, master, on_accept=None, current_user=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_accept    = on_accept
        self.current_user = current_user
        self._result      = None
        self._ceiling     = None
        self._file_path   = None
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
        pwd_row = ctk.CTkFrame(self, fg_color="transparent")
        pwd_row.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        pwd_row.columnconfigure(1, weight=1)

        ctk.CTkLabel(
            pwd_row,
            text="PDF Password (if encrypted):",
            font=FONTS["body_small"],
            text_color=COLORS["text_secondary"],
        ).grid(row=0, column=0, padx=(0, 8))

        self.pdf_password_var = ctk.StringVar()
        ctk.CTkEntry(
            pwd_row,
            textvariable=self.pdf_password_var,
            placeholder_text="e.g. 1234 (last 4 account digits)",
            show="•",  # Mask password
            **input_style(),
        ).grid(row=0, column=1, sticky="ew")

        # ── Stated income fallback ──────────────────────────────────────────
        stated_row = ctk.CTkFrame(self, fg_color="transparent")
        stated_row.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        stated_row.columnconfigure(1, weight=1)

        ctk.CTkLabel(
            stated_row,
            text="OR  Stated Monthly Income (UGX):",
            font=FONTS["body_small"],
            text_color=COLORS["text_secondary"],
        ).grid(row=0, column=0, padx=(0, 8))

        self.stated_income_var = ctk.StringVar()
        ctk.CTkEntry(
            stated_row,
            textvariable=self.stated_income_var,
            placeholder_text="e.g.  800,000  (for borrowers without a statement)",
            **input_style(),
        ).grid(row=0, column=1, sticky="ew")

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

        # ── Results text box — income summary ──────────────────────────────
        self.results_box = ctk.CTkTextbox(
            self,
            height=160,
            fg_color=COLORS["bg_input"],
            text_color=COLORS["text_primary"],
            font=("Courier", 10),
            wrap="word",
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"],
        )
        self.results_box.grid(row=6, column=0, sticky="ew", pady=(0, 8))
        self.results_box.insert("end", "Analysis results will appear here.")
        self.results_box.configure(state="disabled")

        # ── Scenario cards frame — hidden until analysis runs ──────────────
        self.scenarios_frame = ctk.CTkFrame(self, fg_color="transparent")
        # Not gridded yet

        # ── Red flags frame — hidden until analysis runs ───────────────────
        self.flags_frame = ctk.CTkFrame(self, fg_color="transparent")
        # Not gridded yet

        # ── Single Accept button (original behaviour) ──────────────────────
        # Still available if on_accept callback is set
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
        self._set_results("⏳  Analysing... please wait.")
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

            # Get password if provided
            password = self.pdf_password_var.get().strip() if hasattr(self, "pdf_password_var") else ""

            # Parse statement if uploaded
            parsed = None
            if self._file_path:
                parsed = StatementParser.parse(self._file_path, password=password if password else None)
                self._result = parsed

            # Run ceiling engine
            ceiling = LoanCeilingEngine.calculate(
                statement_result=parsed,
                stated_income=stated,
            )
            self._ceiling = ceiling

            # Build summary text
            # NOTE: StatementResult's field is `statement_type`, not
            # `source_type` — using the wrong field name here was a second
            # latent bug that would have crashed once analysis succeeded.
            lines = []
            if parsed and parsed.statement_type not in ("error", "unknown"):
                lines.append(parsed.as_text())
                lines.append("")
            lines.append(ceiling.as_text())
            summary = "\n".join(lines)

            self.after(0, lambda: self._set_results(summary))
            self.after(0, self._show_scenario_cards)
            self.after(0, self._show_flags)
            self.after(0, lambda: self.accept_btn.configure(state="normal"))

        except Exception as e:
            self.after(0, lambda: self._set_results(f"⚠  Analysis error: {e}"))

    # ── Results display ────────────────────────────────────────────────────────

    def _set_results(self, text: str):
        self.results_box.configure(state="normal")
        self.results_box.delete("1.0", "end")
        self.results_box.insert("end", text)
        self.results_box.configure(state="disabled")

    def _reset_results(self):
        self._set_results("Analysis results will appear here.")
        self.accept_btn.configure(state="disabled")
        # Hide scenario and flag frames
        self.scenarios_frame.grid_forget()
        for w in self.scenarios_frame.winfo_children():
            w.destroy()
        self.flags_frame.grid_forget()
        for w in self.flags_frame.winfo_children():
            w.destroy()

    def _show_scenario_cards(self):
        """
        Build 3 scenario cards keyed by duration: 1-month, 3-month, 6-month.

        FIXED: the old version looked up `scenario.name` (Conservative/
        Standard/Extended) which no longer exists on LoanScenario — the
        engine was rewritten for Bingongold Credit's real lending rule
        (max 6 months, typically 3 months) and now exposes
        `duration_months`, `risk_label`, and `is_viable` instead.
        """
        if not self._ceiling or not self._ceiling.scenarios:
            return

        for w in self.scenarios_frame.winfo_children():
            w.destroy()

        self.scenarios_frame.grid(row=6, column=0, sticky="ew", pady=(0, 8))
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

        # Risk-based colour, not name-based — risk_label is the new source
        # of truth (Low / Moderate / High / Very High) from the engine.
        risk_color_map = {
            "Low":       COLORS.get("accent_green", "#276749"),
            "Moderate":  COLORS.get("warning", "#D69E2E"),
            "High":      COLORS.get("danger", "#E53E3E"),
            "Very High": "#9B2335",
        }

        # Scenarios always come back sorted by duration: [1, 3, 6]
        for i, scenario in enumerate(self._ceiling.scenarios):
            months     = scenario.duration_months
            risk_label = getattr(scenario, "risk_label", "Moderate")
            is_viable  = getattr(scenario, "is_viable", True)
            sc_color   = risk_color_map.get(risk_label, COLORS["accent_green"])
            is_typical = (months == 3)   # Bingongold's typical loan term

            card = ctk.CTkFrame(
                self.scenarios_frame,
                fg_color=COLORS["bg_card"],
                corner_radius=8,
                border_width=2,
                border_color=(COLORS["accent_green"] if is_typical else sc_color),
            )
            card.grid(row=1, column=i, padx=4, sticky="nsew")

            # Colour bar
            ctk.CTkFrame(
                card, fg_color=sc_color,
                height=4, corner_radius=0,
            ).pack(fill="x")

            if is_typical:
                ctk.CTkLabel(
                    card, text="✦ typical loan",
                    font=FONTS.get("caption", ("Helvetica", 10)),
                    text_color=COLORS["accent_green"],
                ).pack(pady=(6, 0))

            ctk.CTkLabel(
                card, text=f"{months}-Month Loan",
                font=FONTS["badge"],
                text_color=COLORS["text_primary"],
            ).pack(pady=(6 if not is_typical else 2, 2))

            ctk.CTkLabel(
                card,
                text=f"UGX {float(scenario.principal):,.0f}",
                font=FONTS["subheading"],
                text_color=COLORS["text_primary"],
            ).pack()

            ctk.CTkLabel(
                card,
                text=f"UGX {float(scenario.monthly_instalment):,.0f}/mo",
                font=FONTS["body_small"],
                text_color=COLORS["text_secondary"],
            ).pack(pady=(2, 4))

            # affordability_pct is already a 0-100 number on the new
            # LoanScenario, not a 0-1 fraction — display directly.
            aff_pct = float(getattr(scenario, "affordability_pct", 0))
            ctk.CTkLabel(
                card,
                text=f"{aff_pct:.0f}% of income  ·  {risk_label} Risk",
                font=FONTS["caption"],
                text_color=sc_color,
            ).pack(pady=(0, 2))

            if not is_viable:
                ctk.CTkLabel(
                    card,
                    text="⚠ High repayment risk",
                    font=FONTS["caption"],
                    text_color=COLORS["danger"],
                ).pack(pady=(0, 4))

            ctk.CTkButton(
                card,
                text="✔ Accept",
                height=28,
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

        self.flags_frame.grid(row=7, column=0, sticky="ew", pady=(0, 8))
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
        """
        Accept the typical Bingongold loan — the 3-month scenario.
        Falls back to the middle scenario by index if duration_months
        is somehow not present (defensive, shouldn't normally happen).
        """
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