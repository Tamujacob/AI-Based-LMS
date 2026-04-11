"""
app/core/models/user.py
─────────────────────────────────────────────
System user (staff accounts) with role-based access.
Roles: admin | manager | loan_officer
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.orm import relationship
from app.database.base import Base
import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    loan_officer = "loan_officer"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(150), nullable=False)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(150), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.loan_officer)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    audit_logs = relationship("AuditLog", back_populates="user", lazy="dynamic")

    def __repr__(self):
        return f"<User {self.username} [{self.role}]>"

    @property
    def is_admin(self):
        return self.role == UserRole.admin

    @property
    def is_manager(self):
        return self.role in (UserRole.admin, UserRole.manager)