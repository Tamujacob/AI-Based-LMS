"""
app/core/services/audit_service.py
────────────────────────────────────
Central audit logging service for Bingongold LMS.
Every significant system action is recorded here for
accountability, security, and debugging purposes.

Usage:
    AuditService.log(
        action="CLIENT_CREATED",
        user_id=current_user.id,
        entity_type="Client",
        entity_id=client.id,
        description="New client created: John Doe (NIN: CM12345678)",
    )
"""

import json
from datetime import datetime
from app.database.connection import get_db
from app.core.models.audit_log import AuditLog


# ── Recognised action constants ────────────────────────────────────────────────
# Import these in other services to avoid typos in action strings.

class Actions:
    # Auth
    LOGIN               = "LOGIN"
    LOGOUT              = "LOGOUT"
    LOGIN_FAILED        = "LOGIN_FAILED"
    PASSWORD_CHANGED    = "PASSWORD_CHANGED"

    # Users
    USER_CREATED        = "USER_CREATED"
    USER_UPDATED        = "USER_UPDATED"
    USER_ACTIVATED      = "USER_ACTIVATED"
    USER_DEACTIVATED    = "USER_DEACTIVATED"

    # Clients
    CLIENT_CREATED      = "CLIENT_CREATED"
    CLIENT_UPDATED      = "CLIENT_UPDATED"
    CLIENT_DELETED      = "CLIENT_DELETED"

    # Loans
    LOAN_CREATED        = "LOAN_CREATED"
    LOAN_APPROVED       = "LOAN_APPROVED"
    LOAN_REJECTED       = "LOAN_REJECTED"
    LOAN_UPDATED        = "LOAN_UPDATED"
    LOAN_COMPLETED      = "LOAN_COMPLETED"
    LOAN_DEFAULTED      = "LOAN_DEFAULTED"

    # Repayments
    REPAYMENT_RECORDED  = "REPAYMENT_RECORDED"
    REPAYMENT_DELETED   = "REPAYMENT_DELETED"

    # Reports
    REPORT_GENERATED    = "REPORT_GENERATED"


class AuditService:

    @staticmethod
    def log(
        action: str,
        user_id: int        = None,
        entity_type: str    = None,
        entity_id: int      = None,
        description: str    = None,
        old_value: dict     = None,
        new_value: dict     = None,
        ip_address: str     = None,
    ) -> None:
        """
        Write a single audit log entry to the database.

        This method is intentionally fault-tolerant — a logging
        failure must never crash the main application flow.

        Args:
            action:       Action constant, e.g. Actions.CLIENT_CREATED
            user_id:      ID of the user performing the action (None = system)
            entity_type:  Model name affected, e.g. "Client", "Loan"
            entity_id:    Primary key of the affected record
            description:  Human-readable summary of what happened
            old_value:    Dict snapshot of the record before the change
            new_value:    Dict snapshot of the record after the change
            ip_address:   IP address of the user (optional)
        """
        try:
            with get_db() as db:
                entry = AuditLog(
                    action      = action,
                    user_id     = user_id,
                    entity_type = entity_type,
                    entity_id   = entity_id,
                    description = description,
                    old_value   = json.dumps(old_value) if old_value else None,
                    new_value   = json.dumps(new_value) if new_value else None,
                    ip_address  = ip_address,
                    timestamp   = datetime.utcnow(),
                )
                db.add(entry)
                db.commit()
        except Exception as e:
            # Never let logging crash the app
            print(f"[AuditService] ⚠ Failed to write log entry "
                  f"(action={action}, user={user_id}): {e}")

    @staticmethod
    def get_recent(limit: int = 100) -> list:
        """Return the most recent audit log entries."""
        from app.core.models.user import User
        from sqlalchemy import desc
        try:
            with get_db() as db:
                results = (
                    db.query(AuditLog, User)
                    .outerjoin(User, AuditLog.user_id == User.id)
                    .order_by(desc(AuditLog.timestamp))
                    .limit(limit)
                    .all()
                )
                rows = []
                for log, user in results:
                    rows.append({
                        "id":          log.id,
                        "timestamp":   log.timestamp.strftime("%Y-%m-%d %H:%M")
                                       if log.timestamp else "—",
                        "user_name":   user.full_name if user else "System",
                        "action":      log.action       or "—",
                        "entity_type": log.entity_type  or "—",
                        "entity_id":   str(log.entity_id) if log.entity_id else "—",
                        "description": log.description  or "—",
                    })
                return rows
        except Exception as e:
            print(f"[AuditService] Failed to fetch logs: {e}")
            return []

    @staticmethod
    def get_for_entity(entity_type: str, entity_id: int) -> list:
        """Return all log entries for a specific record, e.g. a single Loan."""
        from sqlalchemy import desc
        try:
            with get_db() as db:
                logs = (
                    db.query(AuditLog)
                    .filter_by(entity_type=entity_type, entity_id=entity_id)
                    .order_by(desc(AuditLog.timestamp))
                    .all()
                )
                for log in logs:
                    db.expunge(log)
                return logs
        except Exception as e:
            print(f"[AuditService] Failed to fetch entity logs: {e}")
            return []

    @staticmethod
    def get_for_user(user_id: int, limit: int = 50) -> list:
        """Return recent log entries for a specific user."""
        from sqlalchemy import desc
        try:
            with get_db() as db:
                logs = (
                    db.query(AuditLog)
                    .filter_by(user_id=user_id)
                    .order_by(desc(AuditLog.timestamp))
                    .limit(limit)
                    .all()
                )
                for log in logs:
                    db.expunge(log)
                return logs
        except Exception as e:
            print(f"[AuditService] Failed to fetch user logs: {e}")
            return []