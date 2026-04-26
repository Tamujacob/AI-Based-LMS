"""
app/core/services/auth_service.py
─────────────────────────────────────────────
Handles login, password hashing, and user management.
"""

import bcrypt
from datetime import datetime
from app.database.connection import get_db
from app.core.models.user import User, UserRole


class AuthService:

    @staticmethod
    def authenticate(username: str, password: str):
        """
        Verify username and password.
        Returns:
            User object if valid and active
            "inactive" string if user exists but is deactivated
            None if username or password is wrong
        """
        with get_db() as db:
            # Check without the is_active filter first
            user = db.query(User).filter_by(username=username).first()
            if not user:
                return None
            if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
                return None
            if not user.is_active:
                return "inactive"

            # Valid and active — update last login
            user.last_login = datetime.utcnow()
            db.commit()
            db.refresh(user)
            db.expunge(user)
            return user

    @staticmethod
    def create_user(full_name: str, username: str, password: str,
                    role: str = "loan_officer", email: str = None):
        """Create a new system user. Returns the created User or raises on duplicate."""
        with get_db() as db:
            existing = db.query(User).filter_by(username=username).first()
            if existing:
                raise ValueError(f"Username '{username}' already exists.")

            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            user = User(
                full_name=full_name,
                username=username,
                email=email,
                password_hash=hashed,
                role=UserRole(role),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            db.expunge(user)
            return user

    @staticmethod
    def get_all_users():
        """Return all active users."""
        with get_db() as db:
            users = db.query(User).filter_by(is_active=True).order_by(User.full_name).all()
            for u in users:
                db.expunge(u)
            return users

    @staticmethod
    def deactivate_user(user_id: int):
        """Soft-delete a user by deactivating them."""
        with get_db() as db:
            user = db.query(User).filter_by(id=user_id).first()
            if user:
                user.is_active = False
                db.commit()

    @staticmethod
    def change_password(user_id: int, new_password: str):
        """Update a user's password."""
        with get_db() as db:
            user = db.query(User).filter_by(id=user_id).first()
            if user:
                hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                user.password_hash = hashed
                db.commit()