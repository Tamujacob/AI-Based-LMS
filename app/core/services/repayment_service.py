"""
app/core/services/repayment_service.py
─────────────────────────────────────────────
Recording payments, tracking balances, and repayment history.
"""

import uuid
from datetime import date
from decimal import Decimal
from app.database.connection import get_db
from app.core.models.repayment import Repayment, PaymentMethod, RepaymentStatus
from app.core.models.loan import Loan, LoanStatus


class RepaymentService:

    @staticmethod
    def _generate_receipt_number() -> str:
        uid = str(uuid.uuid4().int)[:6]
        return f"RCP-{date.today().year}-{uid}"

    @staticmethod
    def record_payment(loan_id: int, amount: float, payment_method: str = "Cash",
                       payment_date: date = None, transaction_reference: str = None,
                       notes: str = None, recorded_by_id: int = None) -> Repayment:
        """Record a repayment against a loan."""
        with get_db() as db:
            loan = db.query(Loan).filter_by(id=loan_id).first()
            if not loan:
                raise ValueError(f"Loan #{loan_id} not found.")
            if loan.status not in (LoanStatus.active, LoanStatus.approved):
                raise ValueError(f"Cannot record payment — loan status is '{loan.status}'.")

            repayment = Repayment(
                receipt_number=RepaymentService._generate_receipt_number(),
                loan_id=loan_id,
                amount=Decimal(str(amount)),
                payment_date=payment_date or date.today(),
                payment_method=PaymentMethod(payment_method),
                transaction_reference=transaction_reference,
                notes=notes,
                recorded_by_id=recorded_by_id,
                status=RepaymentStatus.confirmed,
            )
            db.add(repayment)

            # Auto-complete loan if fully paid
            total_paid = sum(
                r.amount for r in db.query(Repayment).filter_by(
                    loan_id=loan_id, status=RepaymentStatus.confirmed
                ).all()
            ) + Decimal(str(amount))

            if loan.total_repayable and total_paid >= loan.total_repayable:
                loan.status = LoanStatus.completed

            db.commit()
            db.refresh(repayment)
            db.expunge(repayment)
            return repayment

    @staticmethod
    def get_repayments_for_loan(loan_id: int) -> list:
        """All confirmed repayments for a loan, newest first."""
        with get_db() as db:
            repayments = db.query(Repayment).filter_by(
                loan_id=loan_id, status=RepaymentStatus.confirmed
            ).order_by(Repayment.payment_date.desc()).all()
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
                loan_id=loan_id, status=RepaymentStatus.confirmed
            ).all()
            total_paid = sum(r.amount for r in paid)
            balance = Decimal(str(loan.total_repayable)) - Decimal(str(total_paid))
            return max(balance, Decimal("0"))

    @staticmethod
    def get_total_collected_today() -> Decimal:
        """Sum of all payments recorded today — for dashboard."""
        with get_db() as db:
            from sqlalchemy import func
            result = db.query(func.sum(Repayment.amount)).filter(
                Repayment.payment_date == date.today(),
                Repayment.status == RepaymentStatus.confirmed,
            ).scalar()
            return result or Decimal("0")

    @staticmethod
    def get_all_recent_repayments(limit: int = 20) -> list:
        """Most recent repayments across all loans — for dashboard feed."""
        with get_db() as db:
            repayments = db.query(Repayment).filter_by(
                status=RepaymentStatus.confirmed
            ).order_by(Repayment.payment_date.desc()).limit(limit).all()
            for r in repayments:
                db.expunge(r)
            return repayments