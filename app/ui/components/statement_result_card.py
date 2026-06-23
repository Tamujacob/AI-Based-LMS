"""
app/ui/components/statement_result_card.py
────────────────────────────────────────────────────────────
Renders a parsed StatementResult as a structured card inside
the chatbot messages area.

v2 fixes:
  - KPI row now shows ceiling engine values (income_used, net_flow)
    not raw parser avg_monthly_income which could be zero
  - recent_avg_income shown alongside 12-month avg
  - latest_balance shown in header
  - NIN / account number / client name displayed prominently
  - consistency score uses active-months value from ceiling result
  - Suggested questions moved to popup (handled in chatbot_screen.py)
"""

import customtkinter as ctk
from app.ui.styles.theme import COLORS, FONTS


def _ugx(value: float) -> str:
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


class StatementResultCard(ctk.CTkFrame):

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

        # Dynamic row counter — the monthly breakdown section can span a
        # variable number of grid rows depending on how many months are
        # present (wraps at 6 per row), so every section after it must use
        # this counter instead of a hardcoded row number.
        self._next_row = 0

        self._build_header()
        self._build_identity_row()   # NEW — name / NIN / account / period
        self._build_kpi_row()
        self._build_monthly_breakdown()
        self._build_loan_scenarios()
        self._build_risk_note()

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self):
        r = self.result
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=self._next_row, column=0, sticky="ew", padx=16, pady=(14, 4))
        self._next_row += 1
        hdr.columnconfigure(1, weight=1)

        icon = ctk.CTkLabel(
            hdr, text="📄",
            width=40, height=40,
            fg_color=COLORS.get("bg_input", "#F7FAFC"),
            corner_radius=20,
            font=("Helvetica", 18),
        )
        icon.grid(row=0, column=0, rowspan=2, padx=(0, 12))

        # Institution + transaction count
        ctk.CTkLabel(
            hdr,
            text=_institution_label(r.statement_type),
            font=FONTS.get("subheading", ("Helvetica", 14, "bold")),
            text_color=COLORS.get("text_primary", "#1A202C"),
            anchor="w",
        ).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            hdr,
            text=f"{len(r.transactions)} transactions  ·  {r.months_covered} months",
            font=FONTS.get("caption", ("Helvetica", 11)),
            text_color=COLORS.get("text_muted", "#718096"),
            anchor="w",
        ).grid(row=1, column=1, sticky="w")

        # Consistency badge — use ceiling income_consistency if available
        cons = r.income_consistency
        cons_pct   = round(cons * 100)
        cons_color = (COLORS.get("accent_green", "#276749")
                      if cons >= 0.6
                      else COLORS.get("warning", "#D69E2E"))

        ctk.CTkLabel(
            hdr,
            text=f"{cons_pct}% consistent",
            font=FONTS.get("caption", ("Helvetica", 11)),
            text_color="#FFFFFF",
            fg_color=cons_color,
            corner_radius=8,
            padx=10, pady=3,
        ).grid(row=0, column=2, rowspan=2, sticky="e", padx=(8, 0))

        ctk.CTkFrame(
            self, fg_color=COLORS.get("border", "#E2E8F0"), height=1,
        ).grid(row=self._next_row, column=0, sticky="ew", padx=16)
        self._next_row += 1

    # ── Identity row — name / NIN / account / period ─────────────────────────

    def _build_identity_row(self):
        """
        Prominent display of client identity fields extracted from the PDF.
        Shows all fields we have; greys out / labels missing ones clearly
        so the loan officer knows what to fill manually.
        """
        r = self.result

        id_frame = ctk.CTkFrame(
            self,
            fg_color=COLORS.get("bg_input", "#F7FAFC"),
            corner_radius=8,
        )
        id_frame.grid(row=self._next_row, column=0, sticky="ew", padx=16, pady=(10, 4))
        self._next_row += 1
        id_frame.columnconfigure((0, 1, 2, 3), weight=1, uniform="id")

        # Equity Bank statements never print NIN — show a clearer message
        # than "Not found" so the loan officer knows it's not a parsing
        # failure, just not available on this statement type.
        if r.statement_type in ("equity", "mtn_momo", "airtel") and not r.nin:
            nin_display = "Not printed on this statement type"
        else:
            nin_display = r.nin or "Not found in PDF"

        fields = [
            ("👤  Client Name",
             r.client_name or "Not found in PDF",
             bool(r.client_name)),
            ("🪪  NIN",
             nin_display,
             bool(r.nin)),
            ("🏦  Account Number",
             r.account_number or "Not found in PDF",
             bool(r.account_number)),
            ("📅  Period",
             (f"{r.period_from.strftime('%b %Y')} – {r.period_to.strftime('%b %Y')}"
              if r.period_from and r.period_to else "Not found in PDF"),
             bool(r.period_from and r.period_to)),
        ]

        for i, (label, value, found) in enumerate(fields):
            cell = ctk.CTkFrame(id_frame, fg_color="transparent")
            cell.grid(row=0, column=i,
                      padx=(12 if i == 0 else 4, 4),
                      pady=10, sticky="w")

            ctk.CTkLabel(
                cell,
                text=label,
                font=FONTS.get("caption", ("Helvetica", 10)),
                text_color=COLORS.get("text_muted", "#718096"),
                anchor="w",
            ).pack(anchor="w")

            ctk.CTkLabel(
                cell,
                text=value,
                font=FONTS.get("body_small", ("Helvetica", 12, "bold")),
                text_color=(COLORS.get("text_primary", "#1A202C")
                            if found
                            else COLORS.get("text_muted", "#718096")),
                anchor="w",
                wraplength=180,
                justify="left",
            ).pack(anchor="w")

        ctk.CTkFrame(
            self, fg_color=COLORS.get("border", "#E2E8F0"), height=1,
        ).grid(row=self._next_row, column=0, sticky="ew", padx=16, pady=(4, 0))
        self._next_row += 1

    # ── KPI row ───────────────────────────────────────────────────────────────

    def _build_kpi_row(self):
        """
        Shows the income values that the ceiling engine ACTUALLY used —
        not the raw parser avg_monthly_income which can be zero when
        the IQR outlier logic stripped large credits.
        """
        r = self.result
        c = self.ceiling

        # Use ceiling engine values when available — they are more accurate
        if c:
            income_display  = float(c.income_used)
            income_label    = "Income used (ceiling)"
            expense_display = r.avg_monthly_expense
            net_display     = income_display - expense_display
        else:
            income_display  = r.avg_monthly_income
            income_label    = "Avg monthly income"
            expense_display = r.avg_monthly_expense
            net_display     = r.net_monthly_flow

        recent = getattr(r, "recent_avg_income", 0.0)
        balance = getattr(r, "latest_balance", 0.0)

        kpi_frame = ctk.CTkFrame(self, fg_color="transparent")
        kpi_frame.grid(row=self._next_row, column=0, sticky="ew", padx=16, pady=10)
        self._next_row += 1
        for i in range(5):
            kpi_frame.columnconfigure(i, weight=1, uniform="kpi")

        kpis = [
            (income_label,
             _ugx(income_display),
             COLORS.get("accent_green", "#276749")),
            ("Recent 3-month avg",
             _ugx(recent),
             COLORS.get("accent_green", "#276749")),
            ("Avg monthly expense",
             _ugx(expense_display),
             COLORS.get("danger", "#E53E3E")),
            ("Net monthly flow",
             _ugx(net_display),
             COLORS.get("accent_green") if net_display >= 0
             else COLORS.get("danger", "#E53E3E")),
            ("Latest balance",
             _ugx(balance) if balance > 0 else "N/A",
             COLORS.get("text_secondary", "#4A5568")),
        ]

        for i, (label, value, color) in enumerate(kpis):
            cell = ctk.CTkFrame(
                kpi_frame,
                fg_color=COLORS.get("bg_input", "#F7FAFC"),
                corner_radius=8,
            )
            cell.grid(row=0, column=i,
                      padx=(0 if i == 0 else 4, 0),
                      sticky="ew")
            ctk.CTkLabel(
                cell, text=label,
                font=FONTS.get("caption", ("Helvetica", 10)),
                text_color=COLORS.get("text_muted", "#718096"),
                anchor="w",
                wraplength=120,
            ).pack(anchor="w", padx=10, pady=(8, 0))
            ctk.CTkLabel(
                cell, text=value,
                font=FONTS.get("subheading", ("Helvetica", 13, "bold")),
                text_color=color,
                anchor="w",
            ).pack(anchor="w", padx=10, pady=(2, 8))

        ctk.CTkFrame(
            self, fg_color=COLORS.get("border", "#E2E8F0"), height=1,
        ).grid(row=self._next_row, column=0, sticky="ew", padx=16)
        self._next_row += 1

    # ── Monthly breakdown ─────────────────────────────────────────────────────

    def _build_monthly_breakdown(self):
        """
        Renders monthly cards in a grid wrapping at 6 columns per row.
        Each card is bigger than before and shows the actual UGX amounts
        for income (In) and expense (Out) as separate labeled lines,
        not just a thin proportional bar.
        """
        r = self.result
        if not r.monthly_summaries:
            return

        section = ctk.CTkFrame(self, fg_color="transparent")
        section.grid(row=self._next_row, column=0, sticky="ew", padx=16, pady=(10, 4))
        self._next_row += 1

        PER_ROW = 6
        for i in range(PER_ROW):
            section.columnconfigure(i, weight=1, uniform="month")

        ctk.CTkLabel(
            section, text="Monthly breakdown",
            font=FONTS.get("caption", ("Helvetica", 11)),
            text_color=COLORS.get("text_muted", "#718096"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=PER_ROW,
               sticky="w", pady=(0, 8))

        max_val = max(
            (max(m.total_in, m.total_out) for m in r.monthly_summaries),
            default=1,
        )

        for i, ms in enumerate(r.monthly_summaries):
            row_idx = 1 + (i // PER_ROW)
            col_idx = i % PER_ROW

            col = ctk.CTkFrame(
                section,
                fg_color=COLORS.get("bg_input", "#F7FAFC"),
                corner_radius=10,
            )
            col.grid(row=row_idx, column=col_idx,
                     padx=(0 if col_idx == 0 else 6, 0),
                     pady=(0, 6),
                     sticky="nsew")

            # Month + year label — e.g. "Jun 2025"
            ctk.CTkLabel(
                col,
                text=ms.month,
                font=FONTS.get("body_small", ("Helvetica", 12, "bold")),
                text_color=COLORS.get("text_primary", "#1A202C"),
                anchor="center",
            ).pack(anchor="center", padx=8, pady=(10, 6))

            # In row — green, shows actual UGX amount
            in_row = ctk.CTkFrame(col, fg_color="transparent")
            in_row.pack(fill="x", padx=10, pady=1)
            ctk.CTkLabel(
                in_row, text="In",
                font=FONTS.get("caption", ("Helvetica", 10)),
                text_color=COLORS.get("text_muted", "#718096"),
                width=28, anchor="w",
            ).pack(side="left")
            ctk.CTkLabel(
                in_row, text=_ugx(ms.total_in),
                font=FONTS.get("caption", ("Helvetica", 11, "bold")),
                text_color=COLORS.get("accent_green", "#276749"),
                anchor="e",
            ).pack(side="right")

            # Bar for In
            bar_bg_in = ctk.CTkFrame(
                col, fg_color=COLORS.get("border", "#E2E8F0"),
                height=6, corner_radius=3,
            )
            bar_bg_in.pack(fill="x", padx=10, pady=(0, 4))
            pct_in = max(0.04, ms.total_in / max_val) if max_val > 0 else 0.04
            ctk.CTkFrame(
                bar_bg_in,
                fg_color=COLORS.get("accent_green", "#48BB78"),
                height=6, corner_radius=3,
            ).place(x=0, y=0, relheight=1, relwidth=min(pct_in, 1.0))

            # Out row — red, shows actual UGX amount
            out_row = ctk.CTkFrame(col, fg_color="transparent")
            out_row.pack(fill="x", padx=10, pady=1)
            ctk.CTkLabel(
                out_row, text="Out",
                font=FONTS.get("caption", ("Helvetica", 10)),
                text_color=COLORS.get("text_muted", "#718096"),
                width=28, anchor="w",
            ).pack(side="left")
            ctk.CTkLabel(
                out_row, text=_ugx(ms.total_out),
                font=FONTS.get("caption", ("Helvetica", 11, "bold")),
                text_color=COLORS.get("danger", "#E53E3E"),
                anchor="e",
            ).pack(side="right")

            # Bar for Out
            bar_bg_out = ctk.CTkFrame(
                col, fg_color=COLORS.get("border", "#E2E8F0"),
                height=6, corner_radius=3,
            )
            bar_bg_out.pack(fill="x", padx=10, pady=(0, 6))
            pct_out = max(0.04, ms.total_out / max_val) if max_val > 0 else 0.04
            ctk.CTkFrame(
                bar_bg_out,
                fg_color=COLORS.get("danger", "#E53E3E"),
                height=6, corner_radius=3,
            ).place(x=0, y=0, relheight=1, relwidth=min(pct_out, 1.0))

            # Net — divider + bold net figure
            ctk.CTkFrame(
                col, fg_color=COLORS.get("border", "#E2E8F0"), height=1,
            ).pack(fill="x", padx=10, pady=(2, 4))

            net = ms.total_in - ms.total_out
            net_color = (COLORS.get("accent_green", "#276749")
                         if net >= 0 else COLORS.get("danger", "#E53E3E"))
            sign = "+" if net >= 0 else ""
            ctk.CTkLabel(
                col,
                text=f"Net: {sign}{_ugx(net)}",
                font=FONTS.get("caption", ("Helvetica", 11, "bold")),
                text_color=net_color,
                anchor="center",
            ).pack(anchor="center", padx=8, pady=(0, 10))

        # Advance the parent card's row counter by exactly how many rows
        # the breakdown grid used (wraps at PER_ROW months per row).
        import math
        rows_used = max(1, math.ceil(len(r.monthly_summaries) / PER_ROW))
        self._next_row += rows_used

        ctk.CTkFrame(
            self, fg_color=COLORS.get("border", "#E2E8F0"), height=1,
        ).grid(row=self._next_row, column=0, sticky="ew", padx=16, pady=(4, 0))
        self._next_row += 1

    # ── Loan scenarios ────────────────────────────────────────────────────────

    def _build_loan_scenarios(self):
        """
        Renders exactly 3 scenario cards: 1-month, 3-month, 6-month.
        3-month is highlighted as the typical Bingongold loan.
        Each card shows risk label and viability from the ceiling engine.
        """
        c = self.ceiling
        r = self.result

        # ── Normalise scenarios from CeilingResult ────────────────────────────
        scenarios = []
        if c and hasattr(c, "scenarios") and c.scenarios:
            for s in c.scenarios:
                def _g(obj, *keys, default=None):
                    for k in keys:
                        v = (obj.get(k) if isinstance(obj, dict)
                             else getattr(obj, k, None))
                        if v is not None:
                            return v
                    return default

                months    = int(_g(s, "duration_months", "months",
                                   "duration", "term") or 3)
                principal = float(_g(s, "principal", "loan_amount",
                                     "amount") or 0)
                instalment = float(_g(s, "monthly_instalment", "instalment",
                                      "monthly_payment", "payment") or 0)
                aff_raw   = _g(s, "affordability_pct", "pct_income",
                                "percentage") or 0
                aff_pct   = float(aff_raw) / 100 if float(aff_raw) > 1 else float(aff_raw)
                is_viable = bool(_g(s, "is_viable") if _g(s, "is_viable") is not None
                                 else aff_pct <= 0.60)
                risk_label = str(_g(s, "risk_label") or (
                    "Low" if aff_pct <= 0.30 else
                    "Moderate" if aff_pct <= 0.50 else
                    "High" if aff_pct <= 0.60 else "Very High"))

                scenarios.append({
                    "months":     months,
                    "principal":  principal,
                    "instalment": instalment,
                    "aff_pct":    aff_pct,
                    "is_viable":  is_viable,
                    "risk_label": risk_label,
                })
        else:
            # Fallback: calculate directly — durations 1, 3, 6 months
            income = float(c.income_used) if c else (r.avg_monthly_income or 0)
            for mos in [1, 3, 6]:
                inst      = income * 0.30
                principal = (inst * mos) / (1 + 0.10 * mos) if mos else 0
                aff_pct   = (inst / income) if income > 0 else 0
                scenarios.append({
                    "months": mos, "principal": round(principal),
                    "instalment": round(inst), "aff_pct": aff_pct,
                    "is_viable": aff_pct <= 0.60, "risk_label": "Moderate",
                })

        if not scenarios:
            return

        # ── Risk colour helper ────────────────────────────────────────────────
        def _risk_color(label: str) -> str:
            return {
                "Low":       COLORS.get("accent_green", "#276749"),
                "Moderate":  COLORS.get("warning", "#D69E2E"),
                "High":      "#E53E3E",
                "Very High": "#9B2335",
            }.get(label, COLORS.get("text_muted", "#718096"))

        # ── Layout ────────────────────────────────────────────────────────────
        section = ctk.CTkFrame(self, fg_color="transparent")
        section.grid(row=self._next_row, column=0, sticky="ew", padx=16, pady=10)
        self._next_row += 1
        for i in range(len(scenarios)):
            section.columnconfigure(i, weight=1, uniform="scenario")

        ctk.CTkLabel(
            section,
            text="Loan scenarios  ·  10% per month on principal  ·  Max 6 months",
            font=FONTS.get("caption", ("Helvetica", 11)),
            text_color=COLORS.get("text_muted", "#718096"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=len(scenarios),
               sticky="w", pady=(0, 8))

        for i, sc in enumerate(scenarios):
            months     = sc["months"]
            principal  = sc["principal"]
            instalment = sc["instalment"]
            aff_pct    = sc["aff_pct"]
            is_viable  = sc["is_viable"]
            risk_label = sc["risk_label"]
            is_typical = (months == 3)   # 3-month = typical Bingongold loan

            card = ctk.CTkFrame(
                section,
                fg_color=COLORS.get("bg_card", "#FFFFFF"),
                corner_radius=8,
                border_width=2 if is_typical else 1,
                border_color=(COLORS.get("accent_green", "#276749")
                              if is_typical
                              else COLORS.get("border", "#E2E8F0")),
            )
            card.grid(row=1, column=i,
                      padx=(0 if i == 0 else 6, 0),
                      sticky="nsew")

            # "typical" banner on 3-month card
            if is_typical:
                ctk.CTkLabel(
                    card, text="✦ typical loan",
                    font=FONTS.get("caption", ("Helvetica", 10)),
                    text_color=COLORS.get("accent_green", "#276749"),
                    fg_color=COLORS.get("bg_input", "#F7FAFC"),
                    corner_radius=0,
                ).pack(fill="x")

            # Duration heading
            ctk.CTkLabel(
                card,
                text=f"{months}-Month Loan",
                font=FONTS.get("body_small", ("Helvetica", 12, "bold")),
                text_color=COLORS.get("text_primary", "#1A202C"),
                anchor="w",
            ).pack(anchor="w", padx=12,
                   pady=(10 if not is_typical else 6, 0))

            # Principal amount — large
            ctk.CTkLabel(
                card, text=_ugx(principal),
                font=FONTS.get("subheading", ("Helvetica", 15, "bold")),
                text_color=COLORS.get("text_primary", "#1A202C"),
                anchor="w",
            ).pack(anchor="w", padx=12, pady=(2, 0))

            # Monthly instalment
            ctk.CTkLabel(
                card,
                text=f"Instalment: {_ugx(instalment)} / mo",
                font=FONTS.get("caption", ("Helvetica", 11)),
                text_color=COLORS.get("text_secondary", "#4A5568"),
                anchor="w",
            ).pack(anchor="w", padx=12, pady=(2, 0))

            # Income usage %
            ctk.CTkLabel(
                card,
                text=f"{int(aff_pct * 100)}% of net income",
                font=FONTS.get("caption", ("Helvetica", 11)),
                text_color=COLORS.get("text_muted", "#718096"),
                anchor="w",
            ).pack(anchor="w", padx=12, pady=(1, 0))

            # Risk badge row
            risk_row = ctk.CTkFrame(card, fg_color="transparent")
            risk_row.pack(anchor="w", padx=12, pady=(4, 0))

            ctk.CTkLabel(
                risk_row,
                text=f"● {risk_label} Risk",
                font=FONTS.get("caption", ("Helvetica", 11, "bold")),
                text_color=_risk_color(risk_label),
                anchor="w",
            ).pack(side="left")

            if not is_viable:
                ctk.CTkLabel(
                    risk_row,
                    text="  ⚠ High repayment risk",
                    font=FONTS.get("caption", ("Helvetica", 10)),
                    text_color=COLORS.get("danger", "#E53E3E"),
                    anchor="w",
                ).pack(side="left")

            # Accept button
            ctk.CTkButton(
                card, text="Accept →",
                height=32,
                font=FONTS.get("body_small", ("Helvetica", 12)),
                fg_color=(COLORS.get("accent_green", "#276749")
                          if is_typical and is_viable
                          else COLORS.get("bg_input", "#F7FAFC")),
                hover_color=COLORS.get("accent_green_dark", "#1C4532"),
                text_color=("#FFFFFF"
                            if is_typical and is_viable
                            else COLORS.get("text_primary", "#1A202C")),
                corner_radius=6,
                command=lambda m=months, p=principal: (
                    self.on_accept(f"{m}-month", p, m)
                    if self.on_accept else None),
            ).pack(fill="x", padx=12, pady=(8, 10))

        ctk.CTkFrame(
            self, fg_color=COLORS.get("border", "#E2E8F0"), height=1,
        ).grid(row=self._next_row, column=0, sticky="ew", padx=16, pady=(4, 0))
        self._next_row += 1

    # ── Risk note ─────────────────────────────────────────────────────────────

    def _build_risk_note(self):
        r  = self.result
        c  = self.ceiling
        warnings = []

        # Use ceiling red flags first — they are more context-aware
        if c and c.red_flags:
            warnings.extend(c.red_flags)
        if c and c.warnings:
            warnings.extend(c.warnings)

        # Add parser warnings that aren't already covered
        for w in r.parse_warnings:
            if w not in warnings:
                warnings.append(w)

        if r.months_covered < 3:
            warnings.append(
                f"Only {r.months_covered} month(s) of history — "
                "request a longer statement if possible.")

        if not warnings:
            return

        note = ctk.CTkFrame(
            self,
            fg_color=COLORS.get("bg_warning", "#FFFBEB"),
            corner_radius=8,
        )
        note.grid(row=self._next_row, column=0, sticky="ew", padx=16, pady=(8, 14))
        self._next_row += 1

        for w in warnings:
            ctk.CTkLabel(
                note,
                text=f"⚠  {w}",
                font=FONTS.get("caption", ("Helvetica", 11)),
                text_color=COLORS.get("warning", "#D69E2E"),
                anchor="w",
                justify="left",
                wraplength=700,
            ).pack(anchor="w", padx=12, pady=(6, 0))

        ctk.CTkFrame(note, fg_color="transparent", height=6).pack()