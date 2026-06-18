"""
app/core/agents/loan_ceiling_engine.py
─────────────────────────────────────────────────────────
Loan Ceiling Engine — Bingongold Credit

Business rules (confirmed):
  - Loan durations: 1 month, 3 months, 6 months ONLY
  - Typical loan: 3 months
  - Interest: 10% per month flat on principal
  - Min loan: UGX 100,000
  - Max loan: UGX 50,000,000
  - Repayment capacity: max 30% of net monthly flow per instalment
  - Risk threshold: only recommend if repayment probability >= 50%

Interest formula:
  Total Interest     = Principal × 10% × Duration
  Total Repayable    = Principal + Total Interest
  Monthly Instalment = Total Repayable ÷ Duration

Working backwards from instalment:
  Principal = Instalment × Duration ÷ (1 + 0.10 × Duration)

  1-month:  Principal = Instalment × 1  ÷ 1.10  = Instalment × 0.909
  3-month:  Principal = Instalment × 3  ÷ 1.30  = Instalment × 2.308
  6-month:  Principal = Instalment × 6  ÷ 1.60  = Instalment × 3.750
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional


# ── Duration constants ────────────────────────────────────────────────────────
DURATIONS = [1, 3, 6]          # the only valid loan durations
TYPICAL_DURATION = 3           # used for headline recommended_ceiling

# ── Risk thresholds ───────────────────────────────────────────────────────────
# A scenario is "viable" only if the borrower can cover the instalment
# with at least 50% repayment probability — defined here as the instalment
# consuming no more than 60% of net flow (conservative safety margin).
# Below 50% net flow coverage the loan is flagged as high risk.
RISK_THRESHOLD_PCT   = Decimal("0.60")   # instalment / net_flow must be <= 60%
REPAYMENT_RATIO      = Decimal("0.30")   # target: instalment = 30% of net flow
INTEREST_RATE        = Decimal("0.10")   # 10% per month on principal
MIN_LOAN             = Decimal("100000")
MAX_LOAN             = Decimal("50000000")


@dataclass
class LoanScenario:
    duration_months:    int
    principal:          Decimal
    monthly_instalment: Decimal
    total_repayable:    Decimal
    total_interest:     Decimal
    affordability_pct:  float    # instalment as % of net flow
    is_viable:          bool     # True if repayment probability >= 50%
    risk_label:         str      # "Low", "Moderate", "High"


@dataclass
class CeilingResult:
    recommended_ceiling:      Decimal      # 3-month principal
    max_monthly_instalment:   Decimal
    affordability_score:      int          # 0–100
    income_used:              Decimal
    income_source:            str

    scenarios:    List[LoanScenario] = field(default_factory=list)
    red_flags:    List[str]          = field(default_factory=list)
    warnings:     List[str]          = field(default_factory=list)
    interest_rate: Decimal           = Decimal("10")

    def as_text(self) -> str:
        lines = [
            "═" * 54,
            "  LOAN CEILING — BINGONGOLD CREDIT",
            "═" * 54,
            f"  Income Source:       {self.income_source}",
            f"  Monthly Income Used: UGX {float(self.income_used):,.0f}",
            f"  Max Instalment(30%): UGX {float(self.max_monthly_instalment):,.0f}",
            f"  Affordability Score: {self.affordability_score}/100",
            f"  Recommended Ceiling: UGX {float(self.recommended_ceiling):,.0f}  (3-month loan)",
            "",
            "─" * 54,
            "  SCENARIOS",
            "─" * 54,
        ]
        for s in self.scenarios:
            viable_tag = "✅ Viable" if s.is_viable else "⚠ High Risk"
            lines += [
                f"  {s.duration_months}-MONTH LOAN  [{s.risk_label}]  {viable_tag}",
                f"    Principal:   UGX {float(s.principal):,.0f}",
                f"    Monthly Pay: UGX {float(s.monthly_instalment):,.0f}",
                f"    Total Repay: UGX {float(s.total_repayable):,.0f}",
                f"    Income Used: {s.affordability_pct:.0f}%",
                "",
            ]
        if self.red_flags:
            lines += ["─" * 54, "  ⚠ RED FLAGS"]
            lines += [f"    • {f}" for f in self.red_flags]
        if self.warnings:
            lines += ["", "  ℹ NOTES"]
            lines += [f"    • {w}" for w in self.warnings]
        lines.append("═" * 54)
        return "\n".join(lines)


class LoanCeilingEngine:

    @classmethod
    def calculate(
        cls,
        statement_result=None,
        stated_income: float = 0,
        existing_loans_monthly: float = 0,
        preferred_duration: int = None,   # ignored — all 3 durations always shown
    ) -> CeilingResult:

        red_flags = []
        warnings  = []

        # ── Step 1: Best income signal ────────────────────────────────────────
        net_flow      = Decimal("0")
        income_source = "stated"
        latest_balance = Decimal("0")

        if statement_result and hasattr(statement_result, "avg_monthly_income"):
            avg_12m    = Decimal(str(max(0.0, statement_result.avg_monthly_income)))
            recent_3m  = Decimal(str(max(0.0, getattr(statement_result,
                                                       "recent_avg_income", 0.0))))
            avg_expense = Decimal(str(max(0.0, statement_result.avg_monthly_expense)))
            latest_balance = Decimal(str(max(0.0, getattr(statement_result,
                                                           "latest_balance", 0.0))))

            # Use whichever income signal is stronger
            best_income = max(avg_12m, recent_3m)
            net_flow    = best_income - avg_expense

            if recent_3m >= avg_12m:
                income_source = f"Statement — recent 3-month avg (UGX {float(recent_3m):,.0f})"
            else:
                income_source = f"Statement — 12-month avg (UGX {float(avg_12m):,.0f})"

            # Red flags
            if statement_result.income_consistency < 0.5 and recent_3m < avg_12m:
                red_flags.append(
                    "Irregular income with weak recent earnings — high repayment risk.")
            elif statement_result.income_consistency < 0.5:
                warnings.append(
                    "Income irregular over 12 months but recent 3-month trend is strong.")

            if net_flow < 0:
                if recent_3m > 0:
                    warnings.append(
                        "Net flow negative due to high recent spending. "
                        "Using recent income as base.")
                    net_flow = recent_3m
                else:
                    red_flags.append(
                        "Negative net cash flow — borrower spends more than earned.")
                    net_flow = Decimal("0")

            if len(statement_result.transactions) < 5:
                warnings.append("Very few transactions — statement may be incomplete.")

        elif stated_income > 0:
            net_flow      = Decimal(str(stated_income)) * Decimal("0.60")
            income_source = f"Stated income × 60% (UGX {float(net_flow):,.0f})"
            warnings.append("No statement provided. Using 60% of stated income.")
        else:
            net_flow      = Decimal("50000")
            income_source = "Minimum assumption (UGX 50,000)"
            warnings.append("No income data. Using minimum UGX 50,000/month.")

        # Deduct existing commitments
        if existing_loans_monthly > 0:
            net_flow -= Decimal(str(existing_loans_monthly))
            if net_flow < 0:
                red_flags.append("Existing loan payments exceed net income.")
                net_flow = Decimal("0")

        # ── Step 2: Max monthly instalment (30% of net flow) ─────────────────
        max_instalment = net_flow * REPAYMENT_RATIO

        # ── Step 3: Build one scenario per duration ───────────────────────────
        scenarios = []
        for months in DURATIONS:
            scenario = cls._build_scenario(months, max_instalment,
                                           net_flow, latest_balance)
            scenarios.append(scenario)

        # ── Step 4: Recommended ceiling = 3-month principal ──────────────────
        three_month = next((s for s in scenarios if s.duration_months == 3), None)
        recommended = three_month.principal if three_month else MIN_LOAN

        # ── Step 5: Affordability score (based on 3-month scenario) ──────────
        score = cls._affordability_score(net_flow, recommended, 3, red_flags)

        return CeilingResult(
            recommended_ceiling    = recommended,
            max_monthly_instalment = max_instalment,
            affordability_score    = score,
            income_used            = net_flow,
            income_source          = income_source,
            scenarios              = scenarios,
            red_flags              = red_flags,
            warnings               = warnings,
            interest_rate          = INTEREST_RATE * 100,
        )

    @classmethod
    def _build_scenario(
        cls,
        months: int,
        max_instalment: Decimal,
        net_flow: Decimal,
        latest_balance: Decimal,
    ) -> LoanScenario:
        """
        Build a single scenario for *months* duration.

        Principal = max_instalment × months ÷ (1 + 0.10 × months)

        Balance boost: if the borrower's account balance supports a higher
        loan than the income calculation gives, use 40% of balance as an
        alternative ceiling — only when it improves the recommendation.
        The boost is capped at 2× the income-based ceiling so we don't
        over-lend based on a single large deposit.
        """
        # Income-based principal
        denom     = 1 + INTEREST_RATE * months
        principal = (max_instalment * months / denom
                     if max_instalment > 0 else Decimal("0"))

        # Balance boost (conservative: 40% of balance, capped at 2× income ceiling)
        if latest_balance > MIN_LOAN:
            balance_principal = latest_balance * Decimal("0.40")
            balance_principal = min(balance_principal, principal * 2)
            if balance_principal > principal:
                principal = balance_principal

        principal = cls._round(principal)

        # Recalculate instalment from final principal
        interest   = principal * INTEREST_RATE * months
        total      = principal + interest
        instalment = total / months

        aff_pct = (float(instalment) / float(net_flow) * 100
                   if net_flow > 0 else 999.0)

        # Risk label
        if aff_pct <= 30:
            risk_label = "Low"
        elif aff_pct <= 50:
            risk_label = "Moderate"
        elif aff_pct <= 60:
            risk_label = "High"
        else:
            risk_label = "Very High"

        # Viable = instalment consumes <= 60% of net flow (>= 50% repay probability)
        is_viable = aff_pct <= float(RISK_THRESHOLD_PCT * 100)

        return LoanScenario(
            duration_months    = months,
            principal          = principal,
            monthly_instalment = instalment,
            total_repayable    = total,
            total_interest     = interest,
            affordability_pct  = round(aff_pct, 1),
            is_viable          = is_viable,
            risk_label         = risk_label,
        )

    @classmethod
    def _round(cls, amount: Decimal) -> Decimal:
        """Round to nearest UGX 10,000 and apply min/max caps."""
        amount = max(MIN_LOAN, min(MAX_LOAN, amount))
        return Decimal(str(round(float(amount) / 10000) * 10000))

    @classmethod
    def _affordability_score(
        cls,
        net_flow: Decimal,
        principal: Decimal,
        months: int,
        red_flags: list,
    ) -> int:
        if net_flow <= 0:
            return 10
        total    = principal * (1 + INTEREST_RATE * months)
        monthly  = total / months
        ratio    = float(monthly) / float(net_flow)

        if ratio <= 0.20:   score = 95
        elif ratio <= 0.30: score = 80
        elif ratio <= 0.40: score = 65
        elif ratio <= 0.50: score = 50
        elif ratio <= 0.60: score = 35
        else:               score = 15

        score -= len(red_flags) * 8
        return max(0, min(100, score))