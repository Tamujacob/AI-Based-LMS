"""
app/core/services/loan_service.py
────────────────────────────────────
Loan processing, interest calculation, approval workflow,
and all loan-related database operations.
Every write operation is fully audit-logged.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from app.database.connection import get_db
from app.core.models.loan import Loan, LoanStatus, LoanType
from app.core.services.audit_service import AuditService, Actions
from app.config.settings import DEFAULT_INTEREST_RATE


def _safe_decimal(value) -> Decimal:
    """
    Convert any value to Decimal safely.
    Strips commas, spaces, and UGX prefix that cause ConversionSyntax.
    """
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    cleaned = (
        str(value)
        .replace(",", "")
        .replace(" ", "")
        .replace("UGX", "")
        .strip()
    )
    if not cleaned:
        raise ValueError("Amount field is empty.")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(
            f'"{value}" is not a valid number. '
            f'Please enter digits only (e.g. 500000 or 500,000).'
        )


def _loan_snapshot(loan: Loan) -> dict:
    """Return a JSON-serialisable dict snapshot of a loan record."""
    return {
        "id":               loan.id,
        "loan_number":      loan.loan_number,
        "client_id":        loan.client_id,
        "loan_type":        loan.loan_type.value if loan.loan_type else None,
        "principal_amount": str(loan.principal_amount),
        "duration_months":  loan.duration_months,
        "status":           loan.status.value if loan.status else None,
        "due_date":         str(loan.due_date)      if loan.due_date      else None,
        "approval_date":    str(loan.approval_date) if loan.approval_date else None,
    }


class LoanService:

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _generate_loan_number() -> str:
        """Generate a unique loan number e.g. BG-2025-00042."""
        year = date.today().year
        uid  = str(uuid.uuid4().int)[:5]
        return f"BG-{year}-{uid}"

    @staticmethod
    def _client_name(client_id: int) -> str:
        """Fetch client full name for audit descriptions."""
        try:
            from app.core.services.client_service import ClientService
            client = ClientService.get_client_by_id(client_id)
            return client.full_name if client else f"Client#{client_id}"
        except Exception:
            return f"Client#{client_id}"

    # ── Create ─────────────────────────────────────────────────────────────────

    @staticmethod
    def create_loan(
        client_id: int,
        loan_type: str,
        principal_amount,            # accepts float, int, str (with/without commas), or Decimal
        duration_months: int,
        purpose: str       = None,
        created_by_id: int = None,
    ) -> Loan:
        """
        Create a new loan application (status = pending).
        Automatically calculates interest and repayment schedule.

        Args:
            client_id:        ID of the borrowing client.
            loan_type:        LoanType enum value string.
            principal_amount: Amount in UGX — any format accepted (500000, 500,000, etc.)
            duration_months:  Loan term in months.
            purpose:          Optional free-text loan purpose.
            created_by_id:    ID of the user creating this loan (for audit log).
        """
        # ── Sanitise and validate inputs before touching the DB ────────────
        clean_principal = _safe_decimal(principal_amount)
        if clean_principal <= 0:
            raise ValueError("Principal amount must be greater than zero.")

        try:
            clean_months = int(str(duration_months).replace(",", "").strip())
        except (ValueError, TypeError):
            raise ValueError("Duration must be a whole number of months (e.g. 12).")
        if clean_months <= 0:
            raise ValueError("Duration must be at least 1 month.")

        with get_db() as db:
            loan = Loan(
                loan_number      = LoanService._generate_loan_number(),
                client_id        = client_id,
                loan_type        = LoanType(loan_type),
                principal_amount = clean_principal,
                interest_rate    = Decimal(str(DEFAULT_INTEREST_RATE)),
                duration_months  = clean_months,
                purpose          = purpose,
                created_by_id    = created_by_id,
                application_date = date.today(),
                status           = LoanStatus.pending,
            )
            loan.calculate_financials()
            db.add(loan)
            db.commit()
            db.refresh(loan)
            db.expunge(loan)

        client_name = LoanService._client_name(client_id)
        AuditService.log(
            action      = Actions.LOAN_CREATED,
            user_id     = created_by_id,
            entity_type = "Loan",
            entity_id   = loan.id,
            description = (
                f"Loan application created: {loan.loan_number} "
                f"| Client: {client_name} "
                f"| Type: {loan_type} "
                f"| Principal: UGX {float(clean_principal):,.0f} "
                f"| Term: {clean_months} months"
            ),
            new_value   = _loan_snapshot(loan),
        )
        return loan

    # ── Approval workflow ──────────────────────────────────────────────────────

    @staticmethod
    def approve_loan(loan_id: int, approved_by_id: int = None) -> Loan:
        """Approve a pending loan and set disbursement + due dates."""
        with get_db() as db:
            loan = db.query(Loan).filter_by(id=loan_id).first()
            if not loan:
                raise ValueError(f"Loan #{loan_id} not found.")
            if loan.status != LoanStatus.pending:
                raise ValueError(f"Loan is already {loan.status.value}.")

            old_snapshot = _loan_snapshot(loan)
            today = date.today()

            loan.status            = LoanStatus.active
            loan.approval_date     = today
            loan.disbursement_date = today
            loan.due_date          = today + timedelta(days=30 * loan.duration_months)
            loan.approved_by_id    = approved_by_id

            db.commit()
            db.refresh(loan)
            new_snapshot = _loan_snapshot(loan)
            client_id    = loan.client_id
            loan_number  = loan.loan_number
            db.expunge(loan)

        client_name = LoanService._client_name(client_id)
        AuditService.log(
            action      = Actions.LOAN_APPROVED,
            user_id     = approved_by_id,
            entity_type = "Loan",
            entity_id   = loan_id,
            description = (
                f"Loan approved: {loan_number} "
                f"| Client: {client_name} "
                f"| Disbursed: {today} "
                f"| Due: {new_snapshot['due_date']}"
            ),
            old_value   = old_snapshot,
            new_value   = new_snapshot,
        )
        return loan

    @staticmethod
    def reject_loan(
        loan_id: int,
        reason: str         = None,
        rejected_by_id: int = None,
    ) -> Loan:
        """Reject a pending loan."""
        with get_db() as db:
            loan = db.query(Loan).filter_by(id=loan_id).first()
            if not loan:
                raise ValueError(f"Loan #{loan_id} not found.")

            old_snapshot          = _loan_snapshot(loan)
            loan.status           = LoanStatus.rejected
            loan.rejection_reason = reason

            db.commit()
            db.refresh(loan)
            new_snapshot = _loan_snapshot(loan)
            client_id    = loan.client_id
            loan_number  = loan.loan_number
            db.expunge(loan)

        client_name = LoanService._client_name(client_id)
        AuditService.log(
            action      = Actions.LOAN_REJECTED,
            user_id     = rejected_by_id,
            entity_type = "Loan",
            entity_id   = loan_id,
            description = (
                f"Loan rejected: {loan_number} "
                f"| Client: {client_name} "
                f"| Reason: {reason or 'Not specified'}"
            ),
            old_value   = old_snapshot,
            new_value   = new_snapshot,
        )
        return loan

    @staticmethod
    def mark_completed(loan_id: int, completed_by_id: int = None) -> None:
        """Mark a fully paid loan as completed."""
        loan_number = "Unknown"
        client_id   = None

        with get_db() as db:
            loan = db.query(Loan).filter_by(id=loan_id).first()
            if loan:
                loan_number = loan.loan_number
                client_id   = loan.client_id
                loan.status = LoanStatus.completed
                db.commit()

        client_name = LoanService._client_name(client_id) if client_id else "—"
        AuditService.log(
            action      = Actions.LOAN_COMPLETED,
            user_id     = completed_by_id,
            entity_type = "Loan",
            entity_id   = loan_id,
            description = (
                f"Loan marked as completed: {loan_number} "
                f"| Client: {client_name}"
            ),
        )

    @staticmethod
    def mark_defaulted(loan_id: int, marked_by_id: int = None) -> None:
        """Mark an overdue loan as defaulted."""
        loan_number = "Unknown"
        client_id   = None

        with get_db() as db:
            loan = db.query(Loan).filter_by(id=loan_id).first()
            if loan:
                loan_number = loan.loan_number
                client_id   = loan.client_id
                loan.status = LoanStatus.defaulted
                db.commit()

        client_name = LoanService._client_name(client_id) if client_id else "—"
        AuditService.log(
            action      = Actions.LOAN_DEFAULTED,
            user_id     = marked_by_id,
            entity_type = "Loan",
            entity_id   = loan_id,
            description = (
                f"Loan marked as defaulted: {loan_number} "
                f"| Client: {client_name}"
            ),
        )

    # ── Read ───────────────────────────────────────────────────────────────────

    @staticmethod
    def get_all_loans(status: str = None, search: str = None) -> list:
        with get_db() as db:
            from app.core.models.client import Client
            query = db.query(Loan).join(Client, Loan.client_id == Client.id)
            if status:
                query = query.filter(Loan.status == LoanStatus(status))
            if search:
                term  = f"%{search}%"
                query = query.filter(Client.full_name.ilike(term))
            loans = query.order_by(Loan.created_at.desc()).all()
            for l in loans:
                db.expunge(l)
            return loans

    @staticmethod
    def get_loan_by_id(loan_id: int) -> Loan | None:
        with get_db() as db:
            loan = db.query(Loan).filter_by(id=loan_id).first()
            if loan:
                db.expunge(loan)
            return loan

    @staticmethod
    def get_loans_by_client(client_id: int) -> list:
        with get_db() as db:
            loans = (
                db.query(Loan)
                .filter_by(client_id=client_id)
                .order_by(Loan.created_at.desc())
                .all()
            )
            for l in loans:
                db.expunge(l)
            return loans

    @staticmethod
    def get_overdue_loans() -> list:
        """Return all active loans past their due date."""
        with get_db() as db:
            loans = db.query(Loan).filter(
                Loan.status   == LoanStatus.active,
                Loan.due_date <  date.today(),
            ).all()
            for l in loans:
                db.expunge(l)
            return loans

    # ── Dashboard stats ────────────────────────────────────────────────────────

    @staticmethod
    def count_by_status() -> dict:
        with get_db() as db:
            return {
                status.value: db.query(Loan).filter_by(status=status).count()
                for status in LoanStatus
            }

    @staticmethod
    def total_portfolio_value() -> Decimal:
        with get_db() as db:
            from sqlalchemy import func
            result = db.query(func.sum(Loan.principal_amount)).filter(
                Loan.status.in_([LoanStatus.active, LoanStatus.approved])
            ).scalar()
            return result or Decimal("0")

    @staticmethod
    def total_interest_earned() -> Decimal:
        with get_db() as db:
            from sqlalchemy import func
            result = db.query(func.sum(Loan.total_interest)).filter(
                Loan.status == LoanStatus.completed
            ).scalar()
            return result or Decimal("0")