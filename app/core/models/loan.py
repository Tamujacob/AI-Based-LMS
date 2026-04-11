"""
app/core/models/loan.py
─────────────────────────────────────────────
Loan record. Linked to one client.
Contains all financial fields for interest calc.
"""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, Numeric, Date, DateTime,
    ForeignKey, Text, Enum
)
from sqlalchemy.orm import relationship
from app.database.base import Base
from app.config.settings import DEFAULT_INTEREST_RATE
import enum


class LoanStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    active = "active"
    completed = "completed"
    defaulted = "defaulted"
    rejected = "rejected"


class LoanType(str, enum.Enum):
    business = "Business Loan"
    school_fees = "School Fees Loan"
    tax_clearance = "Tax Clearance Loan"
    development = "Development Loan"
    asset_acquisition = "Asset Acquisition Loan"


class Loan(Base):
    __tablename__ = "loans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    loan_number = Column(String(30), unique=True, nullable=False, index=True)

    # Foreign Keys
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Loan Details
    loan_type = Column(Enum(LoanType), nullable=False)
    principal_amount = Column(Numeric(14, 2), nullable=False)
    interest_rate = Column(Numeric(5, 2), nullable=False, default=DEFAULT_INTEREST_RATE)
    duration_months = Column(Integer, nullable=False)

    # Computed fields (populated on approval)
    total_interest = Column(Numeric(14, 2), nullable=True)
    total_repayable = Column(Numeric(14, 2), nullable=True)
    monthly_installment = Column(Numeric(14, 2), nullable=True)

    # Dates
    application_date = Column(Date, default=datetime.utcnow, nullable=False)
    approval_date = Column(Date, nullable=True)
    disbursement_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)

    # Status
    status = Column(Enum(LoanStatus), nullable=False, default=LoanStatus.pending)

    # AI Risk Assessment
    risk_score = Column(String(10), nullable=True)       # LOW / MEDIUM / HIGH
    risk_reasoning = Column(Text, nullable=True)

    # Admin notes
    purpose = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # System
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    client = relationship("Client", back_populates="loans")
    repayments = relationship("Repayment", back_populates="loan", lazy="dynamic")
    collaterals = relationship("Collateral", back_populates="loan", lazy="dynamic")
    created_by = relationship("User", foreign_keys=[created_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])

    def __repr__(self):
        return f"<Loan {self.loan_number} | {self.loan_type} | {self.status}>"

    def calculate_financials(self):
        """Compute and set interest and repayment fields."""
        principal = Decimal(str(self.principal_amount))
        rate = Decimal(str(self.interest_rate)) / Decimal("100")
        months = int(self.duration_months)

        self.total_interest = principal * rate
        self.total_repayable = principal + self.total_interest
        self.monthly_installment = self.total_repayable / months

    @property
    def amount_paid(self):
        return sum(r.amount for r in self.repayments.filter_by(status="confirmed"))

    @property
    def outstanding_balance(self):
        if self.total_repayable is None:
            return None
        return Decimal(str(self.total_repayable)) - Decimal(str(self.amount_paid or 0))

    @property
    def is_overdue(self):
        from datetime import date
        return (
            self.due_date is not None
            and self.status == LoanStatus.active
            and date.today() > self.due_date
        )