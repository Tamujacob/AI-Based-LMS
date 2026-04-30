"""
app/core/models/statement_analysis.py
──────────────────────────────────────────────────────────────
Database model for storing financial statement analysis results.
Linked to a loan record so management can review the analysis
that was done when the loan was applied for.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from app.database.base import Base


class StatementAnalysis(Base):
    __tablename__ = "statement_analyses"

    id                  = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    loan_id             = Column(Integer, ForeignKey("loans.id"),
                                 nullable=False, index=True)
    created_by_id       = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Source file info
    source_file         = Column(String(500), nullable=True)
    statement_type      = Column(String(30),  nullable=True)  # mtn / airtel / bank

    # Statement period
    statement_from      = Column(String(20),  nullable=True)
    statement_to        = Column(String(20),  nullable=True)
    months_covered      = Column(Integer,     nullable=True, default=1)

    # Income analysis
    total_credits       = Column(Float, nullable=True, default=0.0)
    total_debits        = Column(Float, nullable=True, default=0.0)
    avg_monthly_income  = Column(Float, nullable=True, default=0.0)
    avg_monthly_expense = Column(Float, nullable=True, default=0.0)
    net_monthly_flow    = Column(Float, nullable=True, default=0.0)
    income_consistency  = Column(String(10), nullable=True)  # HIGH / MEDIUM / LOW

    # Ceiling recommendation
    recommended_ceiling = Column(Float, nullable=True, default=0.0)
    affordability_score = Column(Integer, nullable=True, default=0)

    # Scenarios stored as text for display
    scenarios_text      = Column(Text, nullable=True)

    # Red flags
    red_flags           = Column(Text, nullable=True)

    # System
    created_at          = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    loan       = relationship("Loan",     foreign_keys=[loan_id])
    created_by = relationship("User",     foreign_keys=[created_by_id])

    def __repr__(self):
        return (f"<StatementAnalysis loan_id={self.loan_id} "
                f"type={self.statement_type} "
                f"ceiling={self.recommended_ceiling}>")

    def summary_text(self) -> str:
        return (
            f"Type: {self.statement_type or '—'}  |  "
            f"Months: {self.months_covered}  |  "
            f"Net Flow: UGX {self.net_monthly_flow:,.0f}  |  "
            f"Ceiling: UGX {self.recommended_ceiling:,.0f}  |  "
            f"Score: {self.affordability_score}/100"
        )