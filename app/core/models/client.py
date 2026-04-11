"""
app/core/models/client.py
─────────────────────────────────────────────
Borrower / Client profile.
One client can have many loans over time.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Date, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from app.database.base import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Personal Information
    full_name = Column(String(150), nullable=False, index=True)
    nin = Column(String(20), unique=True, nullable=True, index=True)  # National ID Number
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(10), nullable=True)  # Male / Female / Other
    phone_number = Column(String(20), nullable=False)
    alt_phone_number = Column(String(20), nullable=True)
    email = Column(String(150), nullable=True)

    # Address
    district = Column(String(100), nullable=True)
    sub_county = Column(String(100), nullable=True)
    village = Column(String(100), nullable=True)
    physical_address = Column(Text, nullable=True)

    # Employment / Business
    occupation = Column(String(150), nullable=True)
    employer_name = Column(String(150), nullable=True)
    monthly_income = Column(String(50), nullable=True)  # Stored as string for flexibility

    # Next of Kin
    next_of_kin_name = Column(String(150), nullable=True)
    next_of_kin_phone = Column(String(20), nullable=True)
    next_of_kin_relationship = Column(String(50), nullable=True)

    # System fields
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    loans = relationship("Loan", back_populates="client", lazy="dynamic")

    def __repr__(self):
        return f"<Client {self.full_name} | NIN: {self.nin}>"

    @property
    def total_loans(self):
        return self.loans.count()

    @property
    def active_loans(self):
        from app.core.models.loan import LoanStatus
        return self.loans.filter_by(status=LoanStatus.active).count()