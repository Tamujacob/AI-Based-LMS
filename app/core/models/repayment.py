"""
app/core/models/repayment.py
─────────────────────────────────────────────
Individual payment made against a loan.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, Numeric, Date, DateTime, ForeignKey, String, Text, Enum
from sqlalchemy.orm import relationship
from app.database.base import Base
import enum


class PaymentMethod(str, enum.Enum):
    cash = "Cash"
    mobile_money = "Mobile Money"
    bank_transfer = "Bank Transfer"
    cheque = "Cheque"


class RepaymentStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    reversed = "reversed"


class Repayment(Base):
    __tablename__ = "repayments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_number = Column(String(30), unique=True, nullable=False, index=True)

    # Foreign Keys
    loan_id = Column(Integer, ForeignKey("loans.id"), nullable=False, index=True)
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Payment Details
    amount = Column(Numeric(14, 2), nullable=False)
    payment_date = Column(Date, nullable=False)
    payment_method = Column(Enum(PaymentMethod), nullable=False, default=PaymentMethod.cash)
    transaction_reference = Column(String(100), nullable=True)  # Mobile money or bank ref

    # Status
    status = Column(Enum(RepaymentStatus), nullable=False, default=RepaymentStatus.confirmed)

    # Notes
    notes = Column(Text, nullable=True)

    # System
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    loan = relationship("Loan", back_populates="repayments")
    recorded_by = relationship("User", foreign_keys=[recorded_by_id])

    def __repr__(self):
        return f"<Repayment {self.receipt_number} | UGX {self.amount} | {self.payment_date}>"