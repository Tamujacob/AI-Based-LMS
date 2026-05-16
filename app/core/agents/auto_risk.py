"""
app/core/agents/auto_risk.py
─────────────────────────────────────────────────────────────
Auto Risk Scorer — runs automatically when a new loan is created.

Called from loans_screen._submit_loan() in a daemon thread.
Never blocks the UI. Never raises — all errors are logged silently.

What it does:
  1. Loads the loan + client from DB
  2. Runs LocalScorer.score() (offline, instant)
  3. Writes risk_score back to the loan record
  4. If Groq is available, also writes a short ai_notes summary

The human still approves or rejects — this only informs.
"""

import traceback
from datetime import date


def auto_score_loan(loan_id: int) -> None:
    """
    Entry point. Safe to call from any thread.
    Silently scores the loan and writes the result back to the DB.
    """
    try:
        _run(loan_id)
    except Exception:
        # Never crash the caller — just log
        print(f"[AutoRisk] Unexpected error scoring loan {loan_id}:")
        traceback.print_exc()


# ── Internal ───────────────────────────────────────────────────────────────────

def _run(loan_id: int) -> None:
    from app.database.connection import get_db
    from app.core.models.loan import Loan
    from app.core.agents.local_scorer import LocalScorer
    from app.core.services.repayment_service import RepaymentService

    # ── 1. Load loan + client ─────────────────────────────────────────────────
    with get_db() as db:
        loan = db.query(Loan).filter_by(id=loan_id).first()
        if loan is None:
            print(f"[AutoRisk] Loan {loan_id} not found — skipping.")
            return

        # Snapshot the fields we need before the session closes
        principal       = float(loan.principal_amount or 0)
        duration_months = int(loan.duration_months or 12)
        loan_type       = loan.loan_type.value if loan.loan_type else "Business Loan"
        client_id       = loan.client_id
        loan_number     = loan.loan_number

    # ── 2. Load client details (income, occupation) ───────────────────────────
    monthly_income = 0.0
    occupation     = ""
    try:
        from app.core.services.client_service import ClientService
        client = ClientService.get_client_by_id(client_id)
        if client:
            if client.monthly_income:
                monthly_income = float(
                    str(client.monthly_income).replace(",", ""))
            occupation = client.occupation or ""
    except Exception as e:
        print(f"[AutoRisk] Could not load client for loan {loan_number}: {e}")

    # ── 3. Load repayment history (payment consistency) ───────────────────────
    payment_consistency = 1.0   # default for brand-new borrowers
    previous_loans      = 0
    previous_defaults   = 0
    try:
        repayments = RepaymentService.get_repayments_for_loan(loan_id)
        if repayments:
            on_time = sum(
                1 for r in repayments
                if r.payment_date and r.payment_date <= date.today()
            )
            payment_consistency = on_time / len(repayments)
    except Exception as e:
        print(f"[AutoRisk] Could not load repayments for {loan_number}: {e}")

    # ── 4. Run the scorer ─────────────────────────────────────────────────────
    result = LocalScorer.score(
        principal           = principal,
        duration_months     = duration_months,
        loan_type           = loan_type,
        occupation          = occupation,
        monthly_income      = monthly_income,
        previous_loans      = previous_loans,
        previous_defaults   = previous_defaults,
        payment_consistency = payment_consistency,
    )

    print(
        f"[AutoRisk] {loan_number} → {result.rating} "
        f"({result.confidence}% confidence, {result.model_used})"
    )

    # ── 5. Write risk_score back to the loan record ───────────────────────────
    with get_db() as db:
        loan = db.query(Loan).filter_by(id=loan_id).first()
        if loan is None:
            return

        loan.risk_score = result.rating   # "LOW" | "MEDIUM" | "HIGH"

        # Optionally store the full reasoning as a note (if the column exists)
        if hasattr(loan, "ai_notes"):
            loan.ai_notes = result.as_text()

        db.commit()
        print(f"[AutoRisk] Risk score written for {loan_number}: {result.rating}")

    # ── 6. Optional — enrich with Groq explanation (best-effort) ─────────────
    # Only runs if GROQ_API_KEY is set. Never blocks or retries.
    _try_groq_notes(loan_id, loan_number, result)


def _try_groq_notes(loan_id: int, loan_number: str, local_result) -> None:
    """
    If Groq is available, replace the local reasoning with a richer
    AI-written summary and write it back to ai_notes.
    Completely optional — silently skipped if offline or column missing.
    """
    try:
        from app.core.agents.ai_core import AICore
        if AICore.check_groq_status() != "online":
            return

        # Run the full assess_single_loan (which calls Groq internally)
        ai_text = AICore.assess_single_loan(loan_id)
        if not ai_text:
            return

        from app.database.connection import get_db
        from app.core.models.loan import Loan

        with get_db() as db:
            loan = db.query(Loan).filter_by(id=loan_id).first()
            if loan and hasattr(loan, "ai_notes"):
                loan.ai_notes = ai_text
                db.commit()
                print(f"[AutoRisk] Groq notes written for {loan_number}")

    except Exception as e:
        # Groq is optional — never let it affect the main flow
        print(f"[AutoRisk] Groq enrichment skipped for {loan_number}: {e}")