"""
app/ui/components/statement_result_card.py
────────────────────────────────────────────────────────────
Renders a parsed StatementResult as a structured card inside
the chatbot messages area.

Replaces the monospace _add_system_note() text dump with:
  - Header  : client name, institution, account number, period
  - KPI row : avg income / expense / net flow / consistency
  - Monthly : mini bar chart per month (in vs out)
  - Scenarios: Conservative / Standard / Extended loan cards
  - Risk note: warning banner if cashflow is negative

Usage (in chatbot_screen.py):
    from app.ui.components.statement_result_card import StatementResultCard

    card = StatementResultCard(
        parent          = self.messages_frame,
        result          = result,          # StatementResult
        ceiling         = ceiling,         # CeilingResult from LoanCeilingEngine
        on_accept       = self._on_accept_scenario,   # callback(scenario_name, principal, months)
    )
    card.pack(fill="x", padx=12, pady=6)
    self._scroll_to_bottom()
"""

import customtkinter as ctk
from app.ui.styles.theme import COLORS, FONTS


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ugx(value: float) -> str:
    """Format a number as UGX with thousands separator."""
    return f"UGX {int(value):,}"


def _institution_label(stmt_type: str) -> str:
    return {
        "mtn_momo":  "MTN MoMo",
        "airtel":    "Airtel Money",
        "stanbic":   "Stanbic Bank",
        "equity":    "Equity Bank",
        "centenary": "Centenary Bank",
        "dfcu":      "DFCU Bank",
        "bank":      "Bank Statement",
    }.get(stmt_type, stmt_type.replace("_", " ").title())


# ── Main card ─────────────────────────────────────────────────────────────────

class StatementResultCard(ctk.CTkFrame):
    """
    Full-width card that displays a StatementResult + CeilingResult
    inside the chatbot messages scrollable frame.
    """

    def __init__(self, parent, result, ceiling=None, on_accept=None, **kwargs):
        super().__init__(
            parent,
            fg_color=COLORS.get("bg_card", "#FFFFFF"),
            corner_radius=12,
            border_width=1,
            border_color=COLORS.get("border", "#E2E8F0"),
            **kwargs,
        )
        self.result    = result
        self.ceiling   = ceiling
        self.on_accept = on_accept
        self.columnconfigure(0, weight=1)

        self._build_header()
        self._build_kpi_row()
        self._build_monthly_breakdown()
        self._build_loan_scenarios()   # always renders — falls back to calc from income
        self._build_risk_note()

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self):
        r = self.result
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        hdr.columnconfigure(1, weight=1)

        # Institution icon circle
        icon = ctk.CTkLabel(
            hdr, text="📄",
            width=36, height=36,
            fg_color=COLORS.get("bg_input", "#F7FAFC"),
            corner_radius=18,
            font=("Helvetica", 16),
        )
        icon.grid(row=0, column=0, rowspan=2, padx=(0, 10))

        # Client name
        name = r.client_name or r.account_holder or "Unknown Client"
        ctk.CTkLabel(
            hdr, text=name,
            font=FONTS.get("subheading", ("Helvetica", 14, "bold")),
            text_color=COLORS.get("text_primary", "#1A202C"),
            anchor="w",
        ).grid(row=0, column=1, sticky="w")

        # Subtitle: institution · account · NIN · period
        parts = [_institution_label(r.statement_type)]
        if r.account_number:
            parts.append(r.account_number)
        if r.nin:
            parts.append(f"NIN: {r.nin}")
        if r.period_from and r.period_to:
            parts.append(
                f"{r.period_from.strftime('%d %b %Y')} – "
                f"{r.period_to.strftime('%d %b %Y')}"
            )
        ctk.CTkLabel(
            hdr, text="  ·  ".join(parts),
            font=FONTS.get("caption", ("Helvetica", 11)),
            text_color=COLORS.get("text_muted", "#718096"),
            anchor="w",
        ).grid(row=1, column=1, sticky="w")

        # Transaction count + consistency badge (no risk label — no loan yet)
        tx_count   = len(r.transactions)
        cons_pct   = round(r.income_consistency * 100)
        cons_color = (COLORS.get("accent_green", "#276749")
                      if r.income_consistency >= 0.6
                      else COLORS.get("warning", "#D69E2E"))

        badge_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        badge_frame.grid(row=0, column=2, rowspan=2, sticky="e", padx=(8, 0))

        ctk.CTkLabel(
            badge_frame,
            text=f"{cons_pct}% consistent",
            font=FONTS.get("caption", ("Helvetica", 11)),
            text_color="#FFFFFF",
            fg_color=cons_color,
            corner_radius=8,
            padx=10, pady=3,
        ).pack(anchor="e")

        ctk.CTkLabel(
            badge_frame,
            text=f"{tx_count} transactions",
            font=FONTS.get("caption", ("Helvetica", 11)),
            text_color=COLORS.get("text_muted", "#718096"),
        ).pack(anchor="e", pady=(4, 0))

        # Divider
        ctk.CTkFrame(
            self, fg_color=COLORS.get("border", "#E2E8F0"), height=1,
        ).grid(row=1, column=0, sticky="ew", padx=16)

    # ── KPI row ───────────────────────────────────────────────────────────────

    def _build_kpi_row(self):
        r   = self.result
        net = r.avg_monthly_income - r.avg_monthly_expense

        kpi_frame = ctk.CTkFrame(self, fg_color="transparent")
        kpi_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=10)
        for i in range(4):
            kpi_frame.columnconfigure(i, weight=1, uniform="kpi")

        kpis = [
            ("Avg monthly income",  f"{_ugx(r.avg_monthly_income)}",
             COLORS.get("accent_green", "#276749")),
            ("Avg monthly expense", f"{_ugx(r.avg_monthly_expense)}",
             COLORS.get("danger", "#E53E3E")),
            ("Net monthly flow",    f"{_ugx(net)}",
             COLORS.get("accent_green") if net >= 0 else COLORS.get("danger")),
            ("Income consistency",  f"{r.income_consistency:.0%}",
             COLORS.get("accent_green") if r.income_consistency >= 0.6
             else COLORS.get("warning", "#D69E2E")),
        ]

        for i, (label, value, color) in enumerate(kpis):
            cell = ctk.CTkFrame(
                kpi_frame,
                fg_color=COLORS.get("bg_input", "#F7FAFC"),
                corner_radius=8,
            )
            cell.grid(row=0, column=i, padx=(0 if i == 0 else 4, 0), sticky="ew")
            ctk.CTkLabel(
                cell, text=label,
                font=FONTS.get("caption", ("Helvetica", 11)),
                text_color=COLORS.get("text_muted", "#718096"),
                anchor="w",
            ).pack(anchor="w", padx=10, pady=(8, 0))
            ctk.CTkLabel(
                cell, text=value,
                font=FONTS.get("subheading", ("Helvetica", 14, "bold")),
                text_color=color,
                anchor="w",
            ).pack(anchor="w", padx=10, pady=(2, 8))

        # Divider
        ctk.CTkFrame(
            self, fg_color=COLORS.get("border", "#E2E8F0"), height=1,
        ).grid(row=3, column=0, sticky="ew", padx=16)

    # ── Monthly breakdown ─────────────────────────────────────────────────────

    def _build_monthly_breakdown(self):
        r = self.result
        if not r.monthly_summaries:
            return

        section = ctk.CTkFrame(self, fg_color="transparent")
        section.grid(row=4, column=0, sticky="ew", padx=16, pady=(10, 4))
        section.columnconfigure(tuple(range(len(r.monthly_summaries))),
                                weight=1)

        ctk.CTkLabel(
            section, text="Monthly breakdown",
            font=FONTS.get("caption", ("Helvetica", 11)),
            text_color=COLORS.get("text_muted", "#718096"),
            anchor="w",
        ).grid(row=0, column=0,
               columnspan=max(len(r.monthly_summaries), 1),
               sticky="w", pady=(0, 6))

        max_val = max(
            (max(m.total_in, m.total_out) for m in r.monthly_summaries),
            default=1
        )
        BAR_H = 60   # canvas height for bars

        for i, ms in enumerate(r.monthly_summaries):
            col = ctk.CTkFrame(
                section,
                fg_color=COLORS.get("bg_input", "#F7FAFC"),
                corner_radius=8,
            )
            col.grid(row=1, column=i,
                     padx=(0 if i == 0 else 6, 0),
                     sticky="ew")

            # Month label
            ctk.CTkLabel(
                col, text=ms.month,
                font=FONTS.get("caption", ("Helvetica", 11)),
                text_color=COLORS.get("text_primary", "#1A202C"),
                anchor="w",
            ).pack(anchor="w", padx=10, pady=(8, 4))

            # Mini bar rows (In / Out)
            for label, val, color_key in [
                ("In",  ms.total_in,  "accent_green"),
                ("Out", ms.total_out, "danger"),
            ]:
                row_f = ctk.CTkFrame(col, fg_color="transparent")
                row_f.pack(fill="x", padx=10, pady=1)
                row_f.columnconfigure(1, weight=1)

                ctk.CTkLabel(
                    row_f, text=label, width=22,
                    font=FONTS.get("caption", ("Helvetica", 10)),
                    text_color=COLORS.get("text_muted", "#718096"),
                    anchor="w",
                ).grid(row=0, column=0)

                bar_bg = ctk.CTkFrame(
                    row_f, fg_color=COLORS.get("border", "#E2E8F0"),
                    height=6, corner_radius=3,
                )
                bar_bg.grid(row=0, column=1, sticky="ew", padx=(4, 6))
                bar_bg.update_idletasks()

                pct = int(val / max_val * 100) if max_val > 0 else 0
                bar_fill = ctk.CTkFrame(
                    bar_bg,
                    fg_color=COLORS.get(color_key, "#48BB78"),
                    height=6,
                    corner_radius=3,
                    width=max(4, int(bar_bg.winfo_reqwidth() * pct / 100)),
                )
                bar_fill.place(x=0, y=0, relheight=1,
                               relwidth=max(0.04, pct / 100))

                ctk.CTkLabel(
                    row_f,
                    text=f"{int(val/1000)}k",
                    width=32,
                    font=FONTS.get("caption", ("Helvetica", 10)),
                    text_color=COLORS.get("text_muted", "#718096"),
                    anchor="e",
                ).grid(row=0, column=2)

            # Net label
            net = ms.total_in - ms.total_out
            net_color = (COLORS.get("accent_green", "#276749")
                         if net >= 0 else COLORS.get("danger", "#E53E3E"))
            ctk.CTkLabel(
                col,
                text=f"Net: {'+' if net >= 0 else ''}{int(net/1000)}k",
                font=FONTS.get("caption", ("Helvetica", 11)),
                text_color=net_color,
            ).pack(anchor="w", padx=10, pady=(4, 8))

        # Divider
        ctk.CTkFrame(
            self, fg_color=COLORS.get("border", "#E2E8F0"), height=1,
        ).grid(row=5, column=0, sticky="ew", padx=16, pady=(6, 0))

    # ── Loan scenarios ────────────────────────────────────────────────────────

    def _build_loan_scenarios(self):
        c = self.ceiling
        r = self.result

        # ── Build scenarios list ─────────────────────────────────────────────
        # Priority 1: use CeilingResult.scenarios if available
        # Priority 2: build directly from StatementResult avg_monthly_income
        # This ensures scenarios always render even if LoanCeilingEngine fails.

        scenarios = []

        if c and hasattr(c, "scenarios") and c.scenarios:
            raw = c.scenarios
            def _sget(obj, *keys, default=0):
                for k in keys:
                    if isinstance(obj, dict):
                        if k in obj: return obj[k]
                    else:
                        if hasattr(obj, k): return getattr(obj, k)
                return default

            for i, s in enumerate(raw):
                scenarios.append({
                    "name":      str(_sget(s, "name", "label", "scenario_name",
                                          default=f"Option {i+1}")),
                    "principal": float(_sget(s, "principal", "loan_amount",
                                            "amount", default=0)),
                    "months":    int(_sget(s, "months", "duration",
                                          "duration_months", "term", default=0)),
                    "instalment":float(_sget(s, "monthly_instalment", "instalment",
                                            "monthly_payment", "payment", default=0)),
                    "pct_income":float(_sget(s, "pct_income", "income_percentage",
                                            "income_pct", "percentage", default=0)),
                })
        else:
            # Fallback: calculate scenarios from avg_monthly_income
            # Uses same formula as loan_ceiling_engine:
            #   principal = (pct * income * months) / 1.10
            income = r.avg_monthly_income or 0
            RATE   = 1.10  # 10% flat

            for name, pct, mos in [
                ("Conservative", 0.20, 6),
                ("Standard",     0.30, 9),
                ("Extended",     0.40, 12),
            ]:
                instalment = income * pct
                principal  = (instalment * mos) / RATE
                scenarios.append({
                    "name":       name,
                    "principal":  round(principal),
                    "months":     mos,
                    "instalment": round(instalment),
                    "pct_income": pct,
                })

        if not scenarios:
            return

        # ── Render ───────────────────────────────────────────────────────────
        section = ctk.CTkFrame(self, fg_color="transparent")
        section.grid(row=6, column=0, sticky="ew", padx=16, pady=10)
        for i in range(len(scenarios)):
            section.columnconfigure(i, weight=1, uniform="scenario")

        ctk.CTkLabel(
            section,
            text="Loan scenarios  (10% flat interest)",
            font=FONTS.get("caption", ("Helvetica", 11)),
            text_color=COLORS.get("text_muted", "#718096"),
            anchor="w",
        ).grid(row=0, column=0,
               columnspan=len(scenarios),
               sticky="w", pady=(0, 8))

        for i, sc in enumerate(scenarios):
            name       = sc["name"]
            principal  = sc["principal"]
            months     = sc["months"]
            instalment = sc["instalment"]
            pct_income = sc["pct_income"]
            is_std     = name.lower() == "standard"

            card = ctk.CTkFrame(
                section,
                fg_color=COLORS.get("bg_card", "#FFFFFF"),
                corner_radius=8,
                border_width=2 if is_std else 1,
                border_color=(COLORS.get("accent_green", "#276749")
                              if is_std
                              else COLORS.get("border", "#E2E8F0")),
            )
            card.grid(row=1, column=i,
                      padx=(0 if i == 0 else 6, 0),
                      sticky="nsew")

            if is_std:
                ctk.CTkLabel(
                    card, text="recommended",
                    font=FONTS.get("caption", ("Helvetica", 10)),
                    text_color=COLORS.get("accent_green", "#276749"),
                    fg_color=COLORS.get("bg_input", "#F7FAFC"),
                    corner_radius=0,
                ).pack(fill="x")

            ctk.CTkLabel(
                card, text=name,
                font=FONTS.get("caption", ("Helvetica", 11)),
                text_color=COLORS.get("text_muted", "#718096"),
                anchor="w",
            ).pack(anchor="w", padx=12, pady=(10 if not is_std else 6, 0))

            ctk.CTkLabel(
                card, text=_ugx(principal),
                font=FONTS.get("subheading", ("Helvetica", 15, "bold")),
                text_color=COLORS.get("text_primary", "#1A202C"),
                anchor="w",
            ).pack(anchor="w", padx=12, pady=(2, 0))

            ctk.CTkLabel(
                card,
                text=f"{months} months  ·  {int(pct_income * 100)}% of income",
                font=FONTS.get("caption", ("Helvetica", 11)),
                text_color=COLORS.get("text_muted", "#718096"),
                anchor="w",
            ).pack(anchor="w", padx=12, pady=(2, 0))

            ctk.CTkLabel(
                card,
                text=f"Instalment: {_ugx(instalment)} / mo",
                font=FONTS.get("body_small", ("Helvetica", 12)),
                text_color=COLORS.get("text_secondary", "#4A5568"),
                anchor="w",
            ).pack(anchor="w", padx=12, pady=(2, 8))

            ctk.CTkButton(
                card, text="Accept",
                height=32,
                font=FONTS.get("body_small", ("Helvetica", 12)),
                fg_color=(COLORS.get("accent_green", "#276749")
                          if is_std else COLORS.get("bg_input", "#F7FAFC")),
                hover_color=COLORS.get("accent_green_dark", "#1C4532"),
                text_color=("#FFFFFF" if is_std
                            else COLORS.get("text_primary", "#1A202C")),
                corner_radius=6,
                command=lambda n=name, p=principal, m=months: (
                    self.on_accept(n, p, m) if self.on_accept else None),
            ).pack(fill="x", padx=12, pady=(0, 10))

        # Divider
        ctk.CTkFrame(
            self, fg_color=COLORS.get("border", "#E2E8F0"), height=1,
        ).grid(row=7, column=0, sticky="ew", padx=16, pady=(4, 0))

    # ── Risk note ─────────────────────────────────────────────────────────────

    def _build_risk_note(self):
        r   = self.result
        net = r.avg_monthly_income - r.avg_monthly_expense

        warnings = list(r.parse_warnings)

        if net < 0:
            warnings.insert(
                0,
                "Expenses exceed income on average — high repayment risk."
            )
        if r.income_consistency < 0.5:
            warnings.append(
                "Income is irregular across months — "
                "consider requiring collateral or a guarantor."
            )
        if r.months_covered < 3:
            warnings.append(
                f"Only {r.months_covered} month(s) of history — "
                "request a longer statement if possible."
            )

        if not warnings:
            return

        note = ctk.CTkFrame(
            self,
            fg_color=COLORS.get("bg_warning", "#FFFBEB"),
            corner_radius=8,
        )
        note.grid(row=8, column=0, sticky="ew", padx=16, pady=(8, 14))

        ctk.CTkLabel(
            note,
            text="⚠  " + "  ·  ".join(warnings),
            font=FONTS.get("caption", ("Helvetica", 11)),
            text_color=COLORS.get("warning", "#D69E2E"),
            anchor="w",
            justify="left",
            wraplength=520,
        ).pack(anchor="w", padx=12, pady=8)