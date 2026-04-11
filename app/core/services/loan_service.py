"""
app/core/services/loan_service.py
─────────────────────────────────────────────
Loan processing, interest calculation, approval workflow,
and all loan-related database operations.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from app.database.connection import get_db
from app.core.models.loan import Loan, LoanStatus, LoanType


class LoanService:

    @staticmethod
    def _generate_loan_number() -> str:
        """Generate a unique loan number e.g. BG-2025-00042."""
        year = date.today().year
        uid = str(uuid.uuid4().int)[:5]
        return f"BG-{year}-{uid}"

    @staticmethod
    def create_loan(client_id: int, loan_type: str, principal_amount: float,
                    duration_months: int, purpose: str = None,
                    created_by_id: int = None) -> Loan:
        """
        Create a new loan application (status = pending).
        Automatically calculates interest and repayment schedule.
        """
        with get_db() as db:
            loan = Loan(
                loan_number=LoanService._generate_loan_number(),
                client_id=client_id,
                loan_type=LoanType(loan_type),
                principal_amount=Decimal(str(principal_amount)),
                duration_months=duration_months,
                purpose=purpose,
                created_by_id=created_by_id,
                application_date=date.today(),
                status=LoanStatus.pending,
            )
            loan.calculate_financials()
            db.add(loan)
            db.commit()
            db.refresh(loan)
            db.expunge(loan)
            return loan

    @staticmethod
    def approve_loan(loan_id: int, approved_by_id: int = None) -> Loan:
        """Approve a pending loan and set disbursement + due dates."""
        with get_db() as db:
            loan = db.query(Loan).filter_by(id=loan_id).first()
            if not loan:
                raise ValueError(f"Loan #{loan_id} not found.")
            if loan.status != LoanStatus.pending:
                raise ValueError(f"Loan is already {loan.status}.")

            today = date.today()
            loan.status = LoanStatus.active
            loan.approval_date = today
            loan.disbursement_date = today
            loan.due_date = today + timedelta(days=30 * loan.duration_months)
            loan.approved_by_id = approved_by_id
            db.commit()
            db.refresh(loan)
            db.expunge(loan)
            return loan

    @staticmethod
    def reject_loan(loan_id: int, reason: str = None) -> Loan:
        """Reject a pending loan."""
        with get_db() as db:
            loan = db.query(Loan).filter_by(id=loan_id).first()
            if not loan:
                raise ValueError(f"Loan #{loan_id} not found.")
            loan.status = LoanStatus.rejected
            loan.rejection_reason = reason
            db.commit()
            db.refresh(loan)
            db.expunge(loan)
            return loan

    @staticmethod
    def get_all_loans(status: str = None, search: str = None) -> list:
        """
        Return all loans, optionally filtered by status or client name search.
        Joins with client for name display.
        """
        with get_db() as db:
            from app.core.models.client import Client
            query = db.query(Loan).join(Client, Loan.client_id == Client.id)
            if status:
                query = query.filter(Loan.status == LoanStatus(status))
            if search:
                term = f"%{search}%"
                query = query.filter(Client.full_name.ilike(term))
            loans = query.order_by(Loan.created_at.desc()).all()
            for l in loans:
                db.expunge(l)
            return loans

    @staticmethod
    def get_loan_by_id(loan_id: int) -> Loan:
        with get_db() as db:
            loan = db.query(Loan).filter_by(id=loan_id).first()
            if loan:
                db.expunge(loan)
            return loan

    @staticmethod
    def get_loans_by_client(client_id: int) -> list:
        with get_db() as db:
            loans = db.query(Loan).filter_by(client_id=client_id)\
                       .order_by(Loan.created_at.desc()).all()
            for l in loans:
                db.expunge(l)
            return loans

    @staticmethod
    def get_overdue_loans() -> list:
        """Return all active loans past their due date."""
        with get_db() as db:
            loans = db.query(Loan).filter(
                Loan.status == LoanStatus.active,
                Loan.due_date < date.today()
            ).all()
            for l in loans:
                db.expunge(l)
            return loans

    @staticmethod
    def mark_completed(loan_id: int):
        """Mark a fully paid loan as completed."""
        with get_db() as db:
            loan = db.query(Loan).filter_by(id=loan_id).first()
            if loan:
                loan.status = LoanStatus.completed
                db.commit()

    # ── Dashboard stats ────────────────────────────────────────────────────

    @staticmethod
    def count_by_status() -> dict:
        """Return count of loans grouped by status."""
        with get_db() as db:
            results = {}
            for status in LoanStatus:
                results[status.value] = db.query(Loan).filter_by(status=status).count()
            return results

    @staticmethod
    def total_portfolio_value() -> Decimal:
        """Sum of all active loan principal amounts."""
        with get_db() as db:
            from sqlalchemy import func
            result = db.query(func.sum(Loan.principal_amount)).filter(
                Loan.status.in_([LoanStatus.active, LoanStatus.approved])
            ).scalar()
            return result or Decimal("0")

    @staticmethod
    def total_interest_earned() -> Decimal:
        """Sum of interest on all completed loans."""
        with get_db() as db:
            from sqlalchemy import func
            result = db.query(func.sum(Loan.total_interest)).filter(
                Loan.status == LoanStatus.completed
            ).scalar()
            return result or Decimal("0")