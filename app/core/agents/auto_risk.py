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
        print(f"[AutoRisk] Unexpected error scoring loan {loan_id}:")
        traceback.print_exc()


# ── Internal ───────────────────────────────────────────────────────────────────

def _run(loan_id: int) -> None:
    from app.database.connection import get_db
    from app.core.models.loan import Loan
    from app.core.agents.local_scorer import LocalScorer
    from app.core.services.repayment_service import RepaymentService
    import inspect

    # ── 1. Load loan ──────────────────────────────────────────────────────────
    with get_db() as db:
        loan = db.query(Loan).filter_by(id=loan_id).first()
        if loan is None:
            print(f"[AutoRisk] Loan {loan_id} not found — skipping.")
            return
        principal       = float(loan.principal_amount or 0)
        duration_months = int(loan.duration_months or 12)
        loan_type       = loan.loan_type.value if loan.loan_type else "Business Loan"
        client_id       = loan.client_id
        loan_number     = loan.loan_number

    # ── 2. Load client ────────────────────────────────────────────────────────
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
        print(f"[AutoRisk] Could not load client for {loan_number}: {e}")

    # ── 3. Payment consistency ────────────────────────────────────────────────
    payment_consistency = 1.0   # default for brand-new loans
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

    # ── 4. Run scorer — only pass params it actually accepts ──────────────────
    # Inspect LocalScorer.score() signature at runtime so we never crash
    # if the model was trained with a different feature set.
    try:
        sig        = inspect.signature(LocalScorer.score)
        valid_keys = set(sig.parameters.keys())

        all_kwargs = {
            "principal":           principal,
            "duration_months":     duration_months,
            "loan_type":           loan_type,
            "occupation":          occupation,
            "monthly_income":      monthly_income,
            "payment_consistency": payment_consistency,
            "previous_loans":      0,
            "previous_defaults":   0,
        }
        # Only pass kwargs the scorer actually accepts
        kwargs = {k: v for k, v in all_kwargs.items() if k in valid_keys}
        result = LocalScorer.score(**kwargs)

    except Exception as e:
        print(f"[AutoRisk] LocalScorer failed for {loan_number}: {e}")
        return

    # ── 5. Extract risk level — handle different attribute names ──────────────
    # Different versions of ScoreResult use different attribute names.
    # Try them all in priority order.
    risk_level = (
        getattr(result, "risk_level",  None) or
        getattr(result, "rating",      None) or
        getattr(result, "risk_score",  None) or
        getattr(result, "score",       None) or
        "MEDIUM"   # safe fallback
    )
    # Normalise to uppercase string
    risk_level = str(risk_level).upper()
    # Map numeric scores to labels if scorer returns a number
    if risk_level.lstrip("-").isdigit() or _is_float(risk_level):
        score_val = float(risk_level)
        risk_level = ("LOW" if score_val >= 70
                      else "HIGH" if score_val < 40
                      else "MEDIUM")

    # Log using whichever attributes exist
    confidence  = getattr(result, "confidence",  None)
    model_used  = getattr(result, "model_used",  None)
    conf_str    = f" ({confidence}% confidence)" if confidence else ""
    model_str   = f" via {model_used}"           if model_used else ""
    print(f"[AutoRisk] {loan_number} → {risk_level}{conf_str}{model_str}")

    # ── 6. Write risk_score back ──────────────────────────────────────────────
    with get_db() as db:
        loan = db.query(Loan).filter_by(id=loan_id).first()
        if loan is None:
            return
        loan.risk_score = risk_level
        if hasattr(loan, "risk_reasoning"):
            try:
                loan.risk_reasoning = (
                    f"[AUTO-ASSESSED by AutoRisk on {date.today()}]\n"
                    f"Risk Level: {risk_level}\n\n"
                    + (result.as_text() if hasattr(result, "as_text")
                       else str(result))
                )
            except Exception:
                pass
        if hasattr(loan, "ai_notes"):
            try:
                loan.ai_notes = result.as_text() if hasattr(
                    result, "as_text") else str(result)
            except Exception:
                pass
        db.commit()
        print(f"[AutoRisk] Risk score written for {loan_number}: {risk_level}")

    # ── 7. Optional Groq enrichment ───────────────────────────────────────────
    _try_groq_notes(loan_id, loan_number, risk_level)


def _try_groq_notes(loan_id: int, loan_number: str, risk_level: str) -> None:
    """
    If Groq is online, get a richer AI explanation and write it to
    risk_reasoning / ai_notes. Completely optional — silently skipped
    if offline, key missing, or column doesn't exist.
    """
    try:
        from app.core.agents.ai_core import AICore
        if AICore.check_groq_status() != "online":
            return

        ai_text = AICore.assess_single_loan(loan_id)
        if not ai_text:
            return

        from app.database.connection import get_db
        from app.core.models.loan import Loan

        with get_db() as db:
            loan = db.query(Loan).filter_by(id=loan_id).first()
            if loan:
                if hasattr(loan, "risk_reasoning"):
                    loan.risk_reasoning = ai_text
                if hasattr(loan, "ai_notes"):
                    loan.ai_notes = ai_text
                db.commit()
                print(f"[AutoRisk] Groq notes written for {loan_number}")

    except Exception as e:
        print(f"[AutoRisk] Groq enrichment skipped for {loan_number}: {e}")


def _is_float(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False