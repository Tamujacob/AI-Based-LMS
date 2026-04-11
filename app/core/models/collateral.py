"""
app/core/models/collateral.py
─────────────────────────────────────────────
Collateral documents (images, scans) linked to a loan.
File content stored on disk; path stored in DB.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database.base import Base


class Collateral(Base):
    __tablename__ = "collaterals"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign Key
    loan_id = Column(Integer, ForeignKey("loans.id"), nullable=False, index=True)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Document Details
    description = Column(String(200), nullable=False)  # e.g. "Land Title", "Car Logbook"
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # Absolute or relative path on disk
    file_type = Column(String(50), nullable=True)     # image/png, application/pdf, etc.
    file_size_kb = Column(Integer, nullable=True)

    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    loan = relationship("Loan", back_populates="collaterals")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_id])

    def __repr__(self):
        return f"<Collateral {self.description} | Loan #{self.loan_id}>"