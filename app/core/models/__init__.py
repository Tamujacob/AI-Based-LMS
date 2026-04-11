"""app/core/models/__init__.py — expose all models for clean imports."""

from app.core.models.user import User, UserRole
from app.core.models.client import Client
from app.core.models.loan import Loan, LoanStatus, LoanType
from app.core.models.repayment import Repayment, PaymentMethod, RepaymentStatus
from app.core.models.collateral import Collateral
from app.core.models.audit_log import AuditLog

__all__ = [
    "User", "UserRole",
    "Client",
    "Loan", "LoanStatus", "LoanType",
    "Repayment", "PaymentMethod", "RepaymentStatus",
    "Collateral",
    "AuditLog",
]