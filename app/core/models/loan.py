"""
app/core/models/loan.py
─────────────────────────────────────────────
Loan record. Linked to one client.
Contains all financial fields for interest calc.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from sqlalchemy import (
    Column, Integer, String, Numeric, Date, DateTime,
    ForeignKey, Text, Enum,
)
from sqlalchemy.orm import relationship
from app.database.base import Base
from app.config.settings import DEFAULT_INTEREST_RATE
import enum


class LoanStatus(str, enum.Enum):
    pending   = "pending"
    approved  = "approved"
    active    = "active"
    completed = "completed"
    defaulted = "defaulted"
    rejected  = "rejected"


class LoanType(str, enum.Enum):
    business         = "Business Loan"
    school_fees      = "School Fees Loan"
    tax_clearance    = "Tax Clearance Loan"
    development      = "Development Loan"
    asset_acquisition = "Asset Acquisition Loan"


def _safe_decimal(value) -> Decimal:
    """
    Safely convert any value to Decimal.
    Strips commas, spaces, and currency prefixes that would
    cause decimal.ConversionSyntax errors.
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
        return Decimal("0")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(
            f'Cannot convert "{value}" to a number. '
            f'Please enter digits only (e.g. 500000).'
        )


class Loan(Base):
    __tablename__ = "loans"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    loan_number    = Column(String(30), unique=True, nullable=False, index=True)

    # Foreign Keys
    client_id      = Column(Integer, ForeignKey("clients.id"),  nullable=False, index=True)
    created_by_id  = Column(Integer, ForeignKey("users.id"),    nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id"),    nullable=True)

    # Loan Details
    loan_type         = Column(Enum(LoanType),    nullable=False)
    principal_amount  = Column(Numeric(14, 2),    nullable=False)
    interest_rate     = Column(Numeric(5, 2),     nullable=False, default=DEFAULT_INTEREST_RATE)
    duration_months   = Column(Integer,           nullable=False)

    # Computed fields (populated by calculate_financials)
    total_interest      = Column(Numeric(14, 2), nullable=True)
    total_repayable     = Column(Numeric(14, 2), nullable=True)
    monthly_installment = Column(Numeric(14, 2), nullable=True)

    # Dates
    application_date  = Column(Date,     default=datetime.utcnow, nullable=False)
    approval_date     = Column(Date,     nullable=True)
    disbursement_date = Column(Date,     nullable=True)
    due_date          = Column(Date,     nullable=True)

    # Status
    status = Column(Enum(LoanStatus), nullable=False, default=LoanStatus.pending)

    # AI Risk Assessment
    risk_score     = Column(String(10), nullable=True)   # LOW / MEDIUM / HIGH
    risk_reasoning = Column(Text,       nullable=True)

    # Admin notes
    purpose          = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    notes            = Column(Text, nullable=True)

    # System timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    client      = relationship("Client", back_populates="loans")
    repayments  = relationship("Repayment",   back_populates="loan", lazy="dynamic")
    collaterals = relationship("Collateral",  back_populates="loan", lazy="dynamic")
    created_by  = relationship("User", foreign_keys=[created_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])

    def __repr__(self):
        return f"<Loan {self.loan_number} | {self.loan_type} | {self.status}>"

    def calculate_financials(self):
        """
        Compute and store interest, total repayable, and monthly installment.
        Uses _safe_decimal() so commas or other formatting never cause crashes.
        """
        principal = _safe_decimal(self.principal_amount)
        rate      = _safe_decimal(self.interest_rate) / Decimal("100")
        months    = int(self.duration_months)

        if months <= 0:
            raise ValueError("Duration must be at least 1 month.")
        if principal <= 0:
            raise ValueError("Principal amount must be greater than zero.")

        self.total_interest      = principal * rate * months
        self.total_repayable     = principal + self.total_interest
        self.monthly_installment = self.total_repayable / months

            # ── Computed properties ────────────────────────────────────────────────────

    @property
    def amount_paid(self) -> Decimal:
        return sum(
            r.amount for r in self.repayments.filter_by(status="confirmed")
        ) or Decimal("0")

    @property
    def outstanding_balance(self):
        if self.total_repayable is None:
            return None
        return _safe_decimal(self.total_repayable) - _safe_decimal(self.amount_paid)

    @property
    def is_overdue(self) -> bool:
        from datetime import date
        return (
            self.due_date is not None
            and self.status == LoanStatus.active
            and date.today() > self.due_date
        )