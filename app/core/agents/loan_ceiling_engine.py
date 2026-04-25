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

Usage:
    from app.core.agents.statement_parser import StatementParser
    from app.core.agents.loan_ceiling_engine import LoanCeilingEngine

    result  = StatementParser.parse("statement.pdf")
    ceiling = LoanCeilingEngine.calculate(
        result,
        stated_income=800000,
        existing_loans_monthly=0,
    )
    print(ceiling.recommended_ceiling)
    print(ceiling.scenarios)
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, List


@dataclass
class LoanScenario:
    """One of three loan options presented to the borrower."""
    name:               str          # "Conservative", "Standard", "Extended"
    principal:          Decimal
    duration_months:    int
    monthly_instalment: Decimal
    total_repayable:    Decimal
    total_interest:     Decimal
    affordability_pct:  float        # % of net monthly flow used for repayment


@dataclass
class CeilingResult:
    """Full output from the Loan Ceiling Engine."""
    # Core recommendation
    recommended_ceiling:      Decimal
    max_monthly_instalment:   Decimal
    recommended_duration:     int
    affordability_score:      int          # 0–100
    income_used:              Decimal      # which income figure was used
    income_source:            str          # "statement" or "stated"

    # Three scenarios
    scenarios:                List[LoanScenario] = field(default_factory=list)

    # Red flags
    red_flags:                List[str]    = field(default_factory=list)
    warnings:                 List[str]    = field(default_factory=list)

    # Interest rate used
    interest_rate:            Decimal      = Decimal("10")

    def as_text(self) -> str:
        """Human-readable summary for display in the UI."""
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

    Calculation method:
      1. Determine net monthly cash flow (from statement or stated income).
      2. Calculate max monthly instalment = net flow × REPAYMENT_RATIO.
      3. Calculate loan ceiling = max instalment × duration / (1 + INTEREST_RATE).
      4. Apply caps and safety checks.
      5. Build three scenarios.
    """

    # ── Configuration ─────────────────────────────────────────────────────────
    REPAYMENT_RATIO     = Decimal("0.30")   # max 30% of net income for repayment
    INTEREST_RATE       = Decimal("0.10")   # Bingongold flat rate 10%
    MIN_LOAN            = Decimal("100000") # UGX 100,000 minimum
    MAX_LOAN            = Decimal("50000000")  # UGX 50 million absolute maximum
    DEFAULT_DURATION    = 12                # months if not specified
    CONSERVATIVE_RATIO  = Decimal("0.70")   # conservative = 70% of standard
    EXTENDED_RATIO      = Decimal("1.40")   # extended = 140% of standard
    CONSERVATIVE_MONTHS = 6
    EXTENDED_MONTHS     = 24

    @classmethod
    def calculate(
        cls,
        statement_result=None,          # StatementResult from parser (can be None)
        stated_income: float = 0,       # borrower's self-reported income
        existing_loans_monthly: float = 0,  # other loan payments per month
        preferred_duration: int = None,
    ) -> CeilingResult:
        """
        Calculate loan ceiling from available financial data.

        Priority: statement data > stated income > minimum fallback
        """
        red_flags = []
        warnings  = []

        # ── Step 1: Determine income to use ───────────────────────────────────
        net_flow      = Decimal("0")
        income_source = "stated"

        if statement_result and hasattr(statement_result, "net_monthly_flow"):
            net_flow = Decimal(str(statement_result.net_monthly_flow))
            income_source = "statement"

            # Check for red flags in statement
            if statement_result.income_consistency == "LOW":
                red_flags.append(
                    "Income is highly irregular — high risk of repayment gaps.")
            if float(net_flow) < 0:
                red_flags.append(
                    "Statement shows negative net flow — borrower spends more than they earn.")
                net_flow = Decimal("0")
            if len(statement_result.transactions) < 5:
                warnings.append(
                    "Very few transactions found — statement may be incomplete.")

        elif stated_income > 0:
            net_flow      = Decimal(str(stated_income)) * Decimal("0.60")
            income_source = "stated"
            warnings.append(
                "No statement uploaded. Using 60% of stated income as estimated net flow.")
        else:
            net_flow = Decimal("50000")   # absolute minimum assumption
            income_source = "minimum"
            warnings.append(
                "No income data available. Using minimum assumption of UGX 50,000/month.")

        # Subtract existing loan commitments
        if existing_loans_monthly > 0:
            net_flow -= Decimal(str(existing_loans_monthly))
            if net_flow < 0:
                red_flags.append(
                    "Existing loan payments exceed estimated net income.")
                net_flow = Decimal("0")

        # ── Step 2: Calculate max monthly instalment ──────────────────────────
        max_instalment = net_flow * cls.REPAYMENT_RATIO

        # ── Step 3: Calculate standard ceiling ────────────────────────────────
        duration = preferred_duration or cls.DEFAULT_DURATION
        # ceiling = instalment × duration ÷ (1 + interest_rate)
        standard_ceiling = max_instalment * duration / (1 + cls.INTEREST_RATE)
        standard_ceiling = cls._apply_caps(standard_ceiling)

        # ── Step 4: Affordability score ───────────────────────────────────────
        score = cls._affordability_score(
            net_flow, standard_ceiling, duration, red_flags)

        # ── Step 5: Build three scenarios ─────────────────────────────────────
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
        interest  = principal * cls.INTEREST_RATE
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
        # Round to nearest 10,000 UGX for cleanliness
        return Decimal(str(round(float(amount) / 10000) * 10000))

    @classmethod
    def _affordability_score(
        cls,
        net_flow: Decimal,
        ceiling: Decimal,
        duration: int,
        red_flags: list,
    ) -> int:
        """Score 0–100. Higher = better ability to repay."""
        if net_flow <= 0:
            return 10
        total    = ceiling * (1 + cls.INTEREST_RATE)
        monthly  = total / duration
        ratio    = float(monthly) / float(net_flow)

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