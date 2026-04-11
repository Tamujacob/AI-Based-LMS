"""
app/core/models/audit_log.py
─────────────────────────────────────────────
System audit trail. Every significant action is logged.
Used for security, accountability, and debugging.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Who
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # What
    action = Column(String(100), nullable=False)       # e.g. "LOAN_APPROVED", "CLIENT_CREATED"
    entity_type = Column(String(50), nullable=True)    # e.g. "Loan", "Client"
    entity_id = Column(Integer, nullable=True)         # ID of the affected record
    description = Column(Text, nullable=True)          # Human-readable summary
    old_value = Column(Text, nullable=True)            # JSON snapshot before change
    new_value = Column(Text, nullable=True)            # JSON snapshot after change

    # When / Where
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    ip_address = Column(String(50), nullable=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog [{self.action}] by User#{self.user_id} at {self.timestamp}>"
    