"""
app/core/agents/credit_scorer.py
──────────────────────────────────────────────────────────────
Additional Feature — Client Credit Score (0–100)

Calculates an internal credit score for every client based
entirely on their repayment history at Bingongold Credit.

Score bands:
  80–100   EXCELLENT  (green)   — fast-track approval
  60–79    GOOD       (green)   — standard processing
  40–59    FAIR       (yellow)  — extra verification needed
  20–39    POOR       (red)     — collateral required
  0–19     BAD        (red)     — decline or refer to manager

100% offline — no API, no internet.

Usage:
    result = CreditScorer.score_client(client_id=5)
    print(result.score)        # 74
    print(result.band)         # "GOOD"
    print(result.colour)       # "green"
    print(result.summary)      # plain English explanation
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class CreditScoreResult:
    client_id:   int
    client_name: str
    score:       int          # 0–100
    band:        str          # EXCELLENT / GOOD / FAIR / POOR / BAD
    colour:      str          # green / yellow / red
    factors:     List[str]    = field(default_factory=list)
    summary:     str          = ""

    @property
    def badge_text(self) -> str:
        return f"{self.score}/100 — {self.band}"


class CreditScorer:
    """
    Calculates Bingongold Credit's internal client credit score.

    Scoring dimensions (total 100 points):
      30 pts  — Repayment consistency (on-time payments vs late)
      25 pts  — Loan completion rate (completed vs defaulted)
      20 pts  — Payment frequency (how regularly they pay)
      15 pts  — Loan history length (longer = more trust)
      10 pts  — Outstanding balance ratio (less owed = better)
    """

    @staticmethod
    def score_client(client_id: int) -> CreditScoreResult:
        """Calculate credit score for a specific client."""
        try:
            from app.database.connection import get_db
            from app.core.models.loan import Loan, LoanStatus
            from app.core.models.repayment import Repayment
            from app.core.models.client import Client
            from datetime import date

            with get_db() as db:
                client = db.query(Client).filter_by(id=client_id).first()
                if not client:
                    return CreditScoreResult(
                        client_id=client_id, client_name="Unknown",
                        score=0, band="BAD", colour="red",
                        summary="Client not found.")

                client_name = client.full_name

                all_loans = db.query(Loan).filter_by(client_id=client_id).all()
                if not all_loans:
                    return CreditScoreResult(
                        client_id=client_id, client_name=client_name,
                        score=50, band="FAIR", colour="yellow",
                        factors=["No loan history — neutral score assigned."],
                        summary="This client has no loan history at Bingongold Credit. "
                                "A neutral score of 50 has been assigned.")

                all_repayments = []
                for loan in all_loans:
                    reps = db.query(Repayment).filter_by(loan_id=loan.id).all()
                    all_repayments.extend(reps)

                # Expunge for use outside session
                for l in all_loans:
                    db.expunge(l)
                for r in all_repayments:
                    db.expunge(r)

            factors = []
            score   = 0

            # ── 1. Repayment consistency (30 pts) ─────────────────────────────
            total_reps  = len(all_repayments)
            if total_reps == 0:
                consistency_pts = 15
                factors.append("No repayment records yet — neutral consistency score.")
            else:
                on_time = 0
                for rep in all_repayments:
                    loan = next((l for l in all_loans if l.id == rep.loan_id), None)
                    if loan and rep.payment_date and loan.due_date:
                        if rep.payment_date <= loan.due_date:
                            on_time += 1
                ratio = on_time / total_reps
                consistency_pts = int(ratio * 30)
                if ratio >= 0.9:
                    factors.append(f"Excellent payment consistency — {ratio:.0%} of payments on time.")
                elif ratio >= 0.7:
                    factors.append(f"Good payment consistency — {ratio:.0%} on time.")
                elif ratio >= 0.5:
                    factors.append(f"Fair consistency — {ratio:.0%} on time. Some late payments noted.")
                else:
                    factors.append(f"Poor consistency — only {ratio:.0%} of payments on time.")
            score += consistency_pts

            # ── 2. Loan completion rate (25 pts) ──────────────────────────────
            completed = sum(1 for l in all_loans if l.status == LoanStatus.completed)
            defaulted = sum(1 for l in all_loans if l.status == LoanStatus.defaulted)
            total     = len(all_loans)

            if total > 0:
                if defaulted == 0:
                    completion_pts = min(25, int((completed / total) * 25) + 10)
                    if completed > 0:
                        factors.append(f"Clean record — {completed} loan(s) completed, no defaults.")
                else:
                    completion_pts = max(0, 15 - (defaulted * 8))
                    factors.append(f"Warning — {defaulted} default(s) found. Significant risk indicator.")
            else:
                completion_pts = 12
            score += completion_pts

            # ── 3. Payment frequency (20 pts) ─────────────────────────────────
            active_loans = [l for l in all_loans if l.status == LoanStatus.active]
            if active_loans and all_repayments:
                from datetime import timedelta
                recent_cutoff = date.today() - timedelta(days=60)
                recent_payments = [
                    r for r in all_repayments
                    if r.payment_date and r.payment_date >= recent_cutoff
                ]
                if len(recent_payments) >= 2:
                    frequency_pts = 20
                    factors.append("Active payment pattern — regular payments in last 60 days.")
                elif len(recent_payments) == 1:
                    frequency_pts = 12
                    factors.append("One payment in last 60 days — monitor for regularity.")
                else:
                    frequency_pts = 4
                    factors.append("No payments recorded in last 60 days — follow up needed.")
            else:
                frequency_pts = 10
            score += frequency_pts

            # ── 4. Loan history length (15 pts) ───────────────────────────────
            if total >= 5:
                history_pts = 15
                factors.append(f"Strong loan history — {total} loans processed at Bingongold Credit.")
            elif total >= 3:
                history_pts = 10
                factors.append(f"Moderate history — {total} loans.")
            elif total >= 1:
                history_pts = 5
                factors.append(f"Limited history — {total} loan(s). More time needed to build trust.")
            else:
                history_pts = 0
            score += history_pts

            # ── 5. Outstanding balance ratio (10 pts) ─────────────────────────
            try:
                from app.core.services.repayment_service import RepaymentService
                total_outstanding = sum(
                    float(RepaymentService.get_outstanding_balance(l.id))
                    for l in active_loans
                )
                total_principal = sum(
                    float(l.principal_amount or 0) for l in active_loans)
                if total_principal > 0:
                    paid_ratio = 1 - (total_outstanding / total_principal)
                    balance_pts = int(paid_ratio * 10)
                    if paid_ratio > 0.5:
                        factors.append(f"Has repaid {paid_ratio:.0%} of active loan principal — positive.")
                    else:
                        factors.append(f"Only {paid_ratio:.0%} of active principal repaid so far.")
                else:
                    balance_pts = 10
            except Exception:
                balance_pts = 5
            score += balance_pts

            # ── Final band ────────────────────────────────────────────────────
            score = max(0, min(100, score))

            if score >= 80:
                band, colour = "EXCELLENT", "green"
                summary = (f"{client_name} has an excellent credit score of {score}/100. "
                           "Fast-track approval recommended.")
            elif score >= 60:
                band, colour = "GOOD", "green"
                summary = (f"{client_name} has a good credit score of {score}/100. "
                           "Standard processing recommended.")
            elif score >= 40:
                band, colour = "FAIR", "yellow"
                summary = (f"{client_name} has a fair credit score of {score}/100. "
                           "Additional verification or collateral recommended.")
            elif score >= 20:
                band, colour = "POOR", "red"
                summary = (f"{client_name} has a poor credit score of {score}/100. "
                           "Strong collateral required. Refer to manager.")
            else:
                band, colour = "BAD", "red"
                summary = (f"{client_name} has a very low credit score of {score}/100. "
                           "Decline or escalate to senior management.")

            return CreditScoreResult(
                client_id=client_id, client_name=client_name,
                score=score, band=band, colour=colour,
                factors=factors, summary=summary)

        except Exception as e:
            return CreditScoreResult(
                client_id=client_id, client_name="Error",
                score=0, band="BAD", colour="red",
                summary=f"Could not calculate score: {e}")

    @staticmethod
    def score_all_clients() -> list:
        """Score every client and return sorted list (highest score first)."""
        try:
            from app.database.connection import get_db
            from app.core.models.client import Client

            with get_db() as db:
                clients = db.query(Client).filter_by(is_active=True).all()
                client_ids = [c.id for c in clients]

            results = [CreditScorer.score_client(cid) for cid in client_ids]
            results.sort(key=lambda r: r.score, reverse=True)
            return results
        except Exception as e:
            return []