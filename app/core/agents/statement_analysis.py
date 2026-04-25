"""
app/core/models/statement_analysis.py
──────────────────────────────────────────────────────────────
Database model for storing financial statement analysis results.

Linked to a loan record. Stores parsed results from
StatementParser and LoanCeilingEngine so managers can
review the analysis that was used when approving a loan.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Numeric, DateTime,
    ForeignKey, Text, Boolean
)
from sqlalchemy.orm import relationship
from app.database.base import Base


class StatementAnalysis(Base):
    __tablename__ = "statement_analyses"

    id              = Column(Integer, primary_key=True, autoincrement=True)

    # Link to loan and uploading user
    loan_id         = Column(Integer, ForeignKey("loans.id"), nullable=True)
    client_id       = Column(Integer, ForeignKey("clients.id"), nullable=True)
    uploaded_by_id  = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Statement metadata
    statement_type        = Column(String(50), nullable=True)   # mtn, airtel, bank
    statement_file_path   = Column(String(500), nullable=True)
    statement_from        = Column(String(20), nullable=True)   # stored as string
    statement_to          = Column(String(20), nullable=True)
    months_covered        = Column(Integer, nullable=True)
    transactions_found    = Column(Integer, default=0)

    # Extracted financial figures (UGX)
    total_credits         = Column(Numeric(14, 2), nullable=True)
    total_debits          = Column(Numeric(14, 2), nullable=True)
    avg_monthly_income    = Column(Numeric(14, 2), nullable=True)
    avg_monthly_expense   = Column(Numeric(14, 2), nullable=True)
    net_monthly_flow      = Column(Numeric(14, 2), nullable=True)
    income_consistency    = Column(String(20), nullable=True)   # HIGH/MEDIUM/LOW

    # Ceiling engine results
    recommended_ceiling       = Column(Numeric(14, 2), nullable=True)
    max_monthly_instalment    = Column(Numeric(14, 2), nullable=True)
    recommended_duration      = Column(Integer, nullable=True)
    affordability_score       = Column(Integer, nullable=True)   # 0-100
    red_flags                 = Column(Text, nullable=True)      # JSON or newline-separated

    # Whether officer accepted the recommendation
    recommendation_accepted   = Column(Boolean, default=False)

    # Raw notes
    parse_warnings            = Column(Text, nullable=True)
    analyst_notes             = Column(Text, nullable=True)

    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    loan          = relationship("Loan",   foreign_keys=[loan_id])
    client        = relationship("Client", foreign_keys=[client_id])
    uploaded_by   = relationship("User",   foreign_keys=[uploaded_by_id])

    def __repr__(self):
        return (f"<StatementAnalysis loan={self.loan_id} "
                f"type={self.statement_type} "
                f"ceiling={self.recommended_ceiling}>")