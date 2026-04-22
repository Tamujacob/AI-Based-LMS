"""
app/core/services/repayment_service.py
────────────────────────────────────────
Recording payments, tracking balances, and repayment history.
Every write operation is fully audit-logged.
"""

import uuid
from datetime import date
from decimal import Decimal

from app.database.connection import get_db
from app.core.models.repayment import Repayment, PaymentMethod, RepaymentStatus
from app.core.models.loan import Loan, LoanStatus
from app.core.services.audit_service import AuditService, Actions


def _repayment_snapshot(repayment: Repayment) -> dict:
    """Return a JSON-serialisable dict snapshot of a repayment record."""
    return {
        "id":                    repayment.id,
        "receipt_number":        repayment.receipt_number,
        "loan_id":               repayment.loan_id,
        "amount":                str(repayment.amount),
        "payment_date":          str(repayment.payment_date),
        "payment_method":        repayment.payment_method.value if repayment.payment_method else None,
        "transaction_reference": repayment.transaction_reference,
        "status":                repayment.status.value if repayment.status else None,
    }


class RepaymentService:

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _generate_receipt_number() -> str:
        uid = str(uuid.uuid4().int)[:6]
        return f"RCP-{date.today().year}-{uid}"

    @staticmethod
    def _loan_number(loan_id: int) -> str:
        """Fetch loan number for audit descriptions."""
        try:
            from app.core.services.loan_service import LoanService
            loan = LoanService.get_loan_by_id(loan_id)
            return loan.loan_number if loan else f"Loan#{loan_id}"
        except Exception:
            return f"Loan#{loan_id}"

    @staticmethod
    def _client_name_for_loan(loan_id: int) -> str:
        """Fetch client name via the loan for audit descriptions."""
        try:
            from app.core.services.loan_service import LoanService
            from app.core.services.client_service import ClientService
            loan   = LoanService.get_loan_by_id(loan_id)
            client = ClientService.get_client_by_id(loan.client_id) if loan else None
            return client.full_name if client else "—"
        except Exception:
            return "—"

    # ── Record payment ─────────────────────────────────────────────────────────

    @staticmethod
    def record_payment(
        loan_id: int,
        amount: float,
        payment_method: str      = "Cash",
        payment_date: date       = None,
        transaction_reference: str = None,
        notes: str               = None,
        recorded_by_id: int      = None,
    ) -> Repayment:
        """
        Record a repayment against a loan.
        Automatically marks the loan as completed if fully paid.

        Args:
            loan_id:                Primary key of the loan being repaid.
            amount:                 Amount paid in UGX.
            payment_method:         Cash / Mobile Money / Bank Transfer / Cheque.
            payment_date:           Date of payment (defaults to today).
            transaction_reference:  Optional mobile money or bank ref.
            notes:                  Optional free-text notes.
            recorded_by_id:         ID of the user recording this payment (for audit log).
        """
        with get_db() as db:
            loan = db.query(Loan).filter_by(id=loan_id).first()
            if not loan:
                raise ValueError(f"Loan #{loan_id} not found.")
            if loan.status not in (LoanStatus.active, LoanStatus.approved):
                raise ValueError(
                    f"Cannot record payment — loan status is '{loan.status.value}'.")

            loan_number = loan.loan_number
            client_id   = loan.client_id

            repayment = Repayment(
                receipt_number        = RepaymentService._generate_receipt_number(),
                loan_id               = loan_id,
                amount                = Decimal(str(amount)),
                payment_date          = payment_date or date.today(),
                payment_method        = PaymentMethod(payment_method),
                transaction_reference = transaction_reference,
                notes                 = notes,
                recorded_by_id        = recorded_by_id,
                status                = RepaymentStatus.confirmed,
            )
            db.add(repayment)

            # Calculate total paid so far (including this payment)
            previously_paid = sum(
                r.amount for r in db.query(Repayment).filter_by(
                    loan_id=loan_id,
                    status=RepaymentStatus.confirmed,
                ).all()
            )
            total_paid = previously_paid + Decimal(str(amount))

            loan_auto_completed = False
            if loan.total_repayable and total_paid >= loan.total_repayable:
                loan.status         = LoanStatus.completed
                loan_auto_completed = True

            db.commit()
            db.refresh(repayment)
            snapshot = _repayment_snapshot(repayment)
            db.expunge(repayment)

        # Fetch client name outside the session
        try:
            from app.core.services.client_service import ClientService
            client      = ClientService.get_client_by_id(client_id)
            client_name = client.full_name if client else "—"
        except Exception:
            client_name = "—"

        AuditService.log(
            action      = Actions.REPAYMENT_RECORDED,
            user_id     = recorded_by_id,
            entity_type = "Repayment",
            entity_id   = repayment.id,
            description = (
                f"Payment recorded: {repayment.receipt_number} "
                f"| Loan: {loan_number} "
                f"| Client: {client_name} "
                f"| Amount: UGX {amount:,.0f} "
                f"| Method: {payment_method}"
                + (" | Loan fully paid — marked COMPLETED" if loan_auto_completed else "")
            ),
            new_value   = snapshot,
        )

        # If loan was auto-completed, log that separately for clarity
        if loan_auto_completed:
            AuditService.log(
                action      = Actions.LOAN_COMPLETED,
                user_id     = recorded_by_id,
                entity_type = "Loan",
                entity_id   = loan_id,
                description = (
                    f"Loan auto-completed after full repayment: {loan_number} "
                    f"| Client: {client_name} "
                    f"| Total paid: UGX {float(total_paid):,.0f}"
                ),
            )

        return repayment

    @staticmethod
    def delete_repayment(
        repayment_id: int,
        deleted_by_id: int = None,
    ) -> None:
        """
        Soft-delete (void) a repayment record.

        Args:
            repayment_id:   Primary key of the repayment to void.
            deleted_by_id:  ID of the user voiding the payment (for audit log).
        """
        receipt_number = "Unknown"
        loan_id        = None

        with get_db() as db:
            repayment = db.query(Repayment).filter_by(id=repayment_id).first()
            if repayment:
                receipt_number          = repayment.receipt_number
                loan_id                 = repayment.loan_id
                repayment.status        = RepaymentStatus.cancelled
                db.commit()

        loan_number = RepaymentService._loan_number(loan_id) if loan_id else "—"
        AuditService.log(
            action      = Actions.REPAYMENT_DELETED,
            user_id     = deleted_by_id,
            entity_type = "Repayment",
            entity_id   = repayment_id,
            description = (
                f"Repayment voided: {receipt_number} "
                f"| Loan: {loan_number}"
            ),
        )

    # ── Read ───────────────────────────────────────────────────────────────────

    @staticmethod
    def get_repayments_for_loan(loan_id: int) -> list:
        """All confirmed repayments for a loan, newest first."""
        with get_db() as db:
            repayments = (
                db.query(Repayment)
                .filter_by(loan_id=loan_id, status=RepaymentStatus.confirmed)
                .order_by(Repayment.payment_date.desc())
                .all()
            )
            for r in repayments:
                db.expunge(r)
            return repayments

    @staticmethod
    def get_outstanding_balance(loan_id: int) -> Decimal:
        """Calculate how much is still owed on a loan."""
        with get_db() as db:
            loan = db.query(Loan).filter_by(id=loan_id).first()
            if not loan or not loan.total_repayable:
                return Decimal("0")
            paid = db.query(Repayment).filter_by(
                loan_id=loan_id,
                status=RepaymentStatus.confirmed,
            ).all()
            total_paid = sum(r.amount for r in paid)
            balance    = Decimal(str(loan.total_repayable)) - Decimal(str(total_paid))
            return max(balance, Decimal("0"))

    @staticmethod
    def get_total_collected_today() -> Decimal:
        """Sum of all payments recorded today — for dashboard."""
        with get_db() as db:
            from sqlalchemy import func
            result = db.query(func.sum(Repayment.amount)).filter(
                Repayment.payment_date == date.today(),
                Repayment.status       == RepaymentStatus.confirmed,
            ).scalar()
            return result or Decimal("0")

    @staticmethod
    def get_all_recent_repayments(limit: int = 20) -> list:
        """Most recent repayments across all loans — for dashboard feed."""
        with get_db() as db:
            repayments = (
                db.query(Repayment)
                .filter_by(status=RepaymentStatus.confirmed)
                .order_by(Repayment.payment_date.desc())
                .limit(limit)
                .all()
            )
            for r in repayments:
                db.expunge(r)
            return repayments