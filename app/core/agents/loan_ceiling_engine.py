"""
app/core/agents/loan_ceiling_engine.py
─────────────────────────────────────────────────────────
Phase 2 — Loan Ceiling Engine

Takes a StatementResult (from statement_parser.py) plus
optional client profile data and calculates:

  • Maximum safe loan amount (the "ceiling")
  • Maximum safe monthly instalment
  • Recommended loan duration
  • Three loan scenarios (conservative / standard / extended)
  • Affordability score (0–100)
  • Red flags from the statement

100% offline — no internet, no API, no ML model needed.
Pure financial calculation logic.

v2 fixes:
  - Uses recent_avg_income (3-month trailing) vs 12-month avg,
    whichever is higher — so a large recent credit is not diluted
  - latest_balance used as secondary capacity signal
  - Red flags no longer fire on income_consistency alone when recent
    income is strong
  - Negative net flow does not zero out income when recent income exists
  - Income source label is clearer in output

Usage:
    from app.core.agents.statement_parser import StatementParser
    from app.core.agents.loan_ceiling_engine import LoanCeilingEngine

    result  = StatementParser.parse("statement.pdf")
    ceiling = LoanCeilingEngine.calculate(result)
    print(ceiling.recommended_ceiling)
    print(ceiling.scenarios)
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, List


@dataclass
class LoanScenario:
    """One of three loan options presented to the borrower."""
    name:               str
    principal:          Decimal
    duration_months:    int
    monthly_instalment: Decimal
    total_repayable:    Decimal
    total_interest:     Decimal
    affordability_pct:  float        # % of net monthly flow used for repayment


@dataclass
class CeilingResult:
    """Full output from the Loan Ceiling Engine."""
    recommended_ceiling:      Decimal
    max_monthly_instalment:   Decimal
    recommended_duration:     int
    affordability_score:      int          # 0–100
    income_used:              Decimal
    income_source:            str

    scenarios:                List[LoanScenario] = field(default_factory=list)
    red_flags:                List[str]    = field(default_factory=list)
    warnings:                 List[str]    = field(default_factory=list)
    interest_rate:            Decimal      = Decimal("10")

    def as_text(self) -> str:
        lines = [
            "═" * 52,
            "  LOAN CEILING ANALYSIS",
            "═" * 52,
            f"  Income Source:      {self.income_source.upper()}",
            f"  Monthly Income:     UGX {float(self.income_used):,.0f}",
            f"  Affordability:      {self.affordability_score}/100",
            "",
            f"  RECOMMENDED CEILING: UGX {float(self.recommended_ceiling):,.0f}",
            f"  Max Monthly Payment: UGX {float(self.max_monthly_instalment):,.0f}",
            f"  Suggested Duration:  {self.recommended_duration} months",
            "",
            "─" * 52,
            "  THREE SCENARIOS",
            "─" * 52,
        ]
        for s in self.scenarios:
            lines += [
                f"  [{s.name.upper()}]",
                f"    Loan Amount:  UGX {float(s.principal):,.0f}",
                f"    Duration:     {s.duration_months} months",
                f"    Monthly Pay:  UGX {float(s.monthly_instalment):,.0f}",
                f"    Total Repay:  UGX {float(s.total_repayable):,.0f}",
                f"    Income Used:  {s.affordability_pct:.0f}%",
                "",
            ]
        if self.red_flags:
            lines += ["─" * 52, "  ⚠ RED FLAGS"]
            lines += [f"    • {f}" for f in self.red_flags]
        if self.warnings:
            lines += ["", "  ℹ NOTES"]
            lines += [f"    • {w}" for w in self.warnings]
        lines.append("═" * 52)
        return "\n".join(lines)


class LoanCeilingEngine:
    """
    Calculates the maximum safe loan amount from financial statement data.

    Interest method (Bingongold Credit): 10% per month on principal.
      Total Interest     = Principal × 10% × Duration (months)
      Total Repayable    = Principal + Total Interest
      Monthly Instalment = Total Repayable ÷ Duration

    Working backwards from a target instalment:
      Principal = Instalment × Duration ÷ (1 + 0.10 × Duration)
    """

    REPAYMENT_RATIO     = Decimal("0.30")
    INTEREST_RATE       = Decimal("0.10")
    MIN_LOAN            = Decimal("100000")
    MAX_LOAN            = Decimal("50000000")
    DEFAULT_DURATION    = 12
    CONSERVATIVE_RATIO  = Decimal("0.70")
    EXTENDED_RATIO      = Decimal("1.40")
    CONSERVATIVE_MONTHS = 6
    EXTENDED_MONTHS     = 24

    @classmethod
    def calculate(
        cls,
        statement_result=None,
        stated_income: float = 0,
        existing_loans_monthly: float = 0,
        preferred_duration: int = None,
    ) -> CeilingResult:
        red_flags = []
        warnings  = []

        # ── Step 1: Determine best income signal ──────────────────────────────
        #
        # Priority order:
        #   A) recent_avg_income  (3-month trailing — most current)
        #   B) avg_monthly_income (12-month average — broader context)
        #   C) stated income      (self-reported fallback)
        #   D) minimum assumption
        #
        # We use whichever of A or B is HIGHER as the income signal.
        # This protects against two failure modes:
        #   1. Large recent credit diluted by old zero months (use recent)
        #   2. Single lucky month masking a pattern of zero income (use 12-month)

        net_flow      = Decimal("0")
        income_source = "stated"
        latest_balance = Decimal("0")

        if statement_result and hasattr(statement_result, "net_monthly_flow"):
            avg_12m   = Decimal(str(max(0.0, statement_result.avg_monthly_income)))
            recent_3m = Decimal(str(max(0.0, getattr(statement_result,
                                                      "recent_avg_income", 0.0))))
            latest_balance = Decimal(str(getattr(statement_result,
                                                  "latest_balance", 0.0)))

            # Use higher of 12-month or 3-month average as income base
            best_income = max(avg_12m, recent_3m)

            avg_expense = Decimal(str(max(0.0, statement_result.avg_monthly_expense)))
            net_flow    = best_income - avg_expense

            # Label the income source clearly
            if recent_3m > avg_12m:
                income_source = "statement (recent 3-month avg)"
            else:
                income_source = "statement (12-month avg)"

            # ── Red flags — context-aware ──────────────────────────────────
            # Only flag irregular income if recent income is also weak.
            # A borrower with strong recent income after a gap is not high-risk.
            if statement_result.income_consistency < 0.5 and recent_3m < avg_12m:
                red_flags.append(
                    "Income is irregular and recent income is below average — "
                    "monitor repayment closely.")
            elif statement_result.income_consistency < 0.5:
                warnings.append(
                    "Income pattern is irregular over 12 months, but recent "
                    "3-month income is strong.")

            if net_flow < 0:
                if recent_3m > 0:
                    # Net flow is negative due to large recent spending,
                    # but there is real recent income — use recent income only
                    warnings.append(
                        "Overall net cash flow is negative (high spending month). "
                        "Ceiling based on recent income only.")
                    net_flow = recent_3m * cls.REPAYMENT_RATIO / cls.REPAYMENT_RATIO
                else:
                    red_flags.append(
                        "Statement shows negative net flow — "
                        "borrower spends more than they earn.")
                    net_flow = Decimal("0")

            if len(statement_result.transactions) < 5:
                warnings.append(
                    "Very few transactions found — statement may be incomplete.")

        elif stated_income > 0:
            net_flow      = Decimal(str(stated_income)) * Decimal("0.60")
            income_source = "stated"
            warnings.append(
                "No statement uploaded. "
                "Using 60% of stated income as estimated net flow.")
        else:
            net_flow      = Decimal("50000")
            income_source = "minimum"
            warnings.append(
                "No income data available. "
                "Using minimum assumption of UGX 50,000/month.")

        # Subtract existing loan commitments
        if existing_loans_monthly > 0:
            net_flow -= Decimal(str(existing_loans_monthly))
            if net_flow < 0:
                red_flags.append(
                    "Existing loan payments exceed estimated net income.")
                net_flow = Decimal("0")

        # ── Step 2: Max monthly instalment (30% of net flow) ─────────────────
        max_instalment = net_flow * cls.REPAYMENT_RATIO

        # ── Step 3: Standard ceiling from instalment ──────────────────────────
        duration = preferred_duration or cls.DEFAULT_DURATION
        standard_ceiling = (
            max_instalment * duration / (1 + cls.INTEREST_RATE * duration)
        )

        # ── Step 3b: Balance-informed ceiling boost ───────────────────────────
        # If the borrower has a meaningful account balance, use it as a
        # secondary signal to allow a modest ceiling boost (up to 50% of balance).
        # This handles cases like: 7M balance after sending 8M — clear capacity.
        if latest_balance > cls.MIN_LOAN:
            balance_ceiling = latest_balance * Decimal("0.50")
            if balance_ceiling > standard_ceiling:
                warnings.append(
                    f"Ceiling boosted from UGX {float(standard_ceiling):,.0f} "
                    f"to UGX {float(balance_ceiling):,.0f} based on account balance "
                    f"of UGX {float(latest_balance):,.0f}.")
                standard_ceiling = balance_ceiling

        standard_ceiling = cls._apply_caps(standard_ceiling)

        # ── Step 4: Affordability score ───────────────────────────────────────
        score = cls._affordability_score(
            net_flow, standard_ceiling, duration, red_flags)

        # ── Step 5: Three scenarios ───────────────────────────────────────────
        scenarios = [
            cls._build_scenario(
                "Conservative",
                standard_ceiling * cls.CONSERVATIVE_RATIO,
                cls.CONSERVATIVE_MONTHS,
                net_flow,
            ),
            cls._build_scenario(
                "Standard",
                standard_ceiling,
                duration,
                net_flow,
            ),
            cls._build_scenario(
                "Extended",
                cls._apply_caps(standard_ceiling * cls.EXTENDED_RATIO),
                cls.EXTENDED_MONTHS,
                net_flow,
            ),
        ]

        # income_used = the net flow that drove the ceiling
        return CeilingResult(
            recommended_ceiling    = standard_ceiling,
            max_monthly_instalment = max_instalment,
            recommended_duration   = duration,
            affordability_score    = score,
            income_used            = net_flow,
            income_source          = income_source,
            scenarios              = scenarios,
            red_flags              = red_flags,
            warnings               = warnings,
            interest_rate          = cls.INTEREST_RATE * 100,
        )

    @classmethod
    def _build_scenario(
        cls,
        name: str,
        principal: Decimal,
        duration: int,
        net_flow: Decimal,
    ) -> LoanScenario:
        principal = cls._apply_caps(principal)
        interest  = principal * cls.INTEREST_RATE * Decimal(str(duration))
        total     = principal + interest
        monthly   = total / duration if duration > 0 else total
        aff_pct   = (float(monthly) / float(net_flow) * 100) if net_flow > 0 else 0
        return LoanScenario(
            name               = name,
            principal          = principal,
            duration_months    = duration,
            monthly_instalment = monthly,
            total_repayable    = total,
            total_interest     = interest,
            affordability_pct  = round(aff_pct, 1),
        )

    @classmethod
    def _apply_caps(cls, amount: Decimal) -> Decimal:
        amount = max(cls.MIN_LOAN, amount)
        amount = min(cls.MAX_LOAN, amount)
        return Decimal(str(round(float(amount) / 10000) * 10000))

    @classmethod
    def _affordability_score(
        cls,
        net_flow: Decimal,
        ceiling: Decimal,
        duration: int,
        red_flags: list,
    ) -> int:
        if net_flow <= 0:
            return 10
        total   = ceiling * (1 + cls.INTEREST_RATE * duration)
        monthly = total / duration
        ratio   = float(monthly) / float(net_flow)

        if ratio < 0.20:
            score = 90
        elif ratio < 0.30:
            score = 75
        elif ratio < 0.40:
            score = 60
        elif ratio < 0.50:
            score = 45
        else:
            score = 25

        score -= len(red_flags) * 10
        return max(0, min(100, score))