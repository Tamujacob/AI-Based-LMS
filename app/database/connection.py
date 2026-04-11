"""
app/database/connection.py
─────────────────────────────────────────────
SQLAlchemy engine, session factory, and
get_db() context manager used throughout the app.
"""

from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.config.settings import DATABASE_URL, DEBUG

# Create engine — pool_pre_ping ensures dead connections are recycled
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=DEBUG,  # Logs SQL in debug mode
)

# Session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


@contextmanager
def get_db() -> Session:
    """
    Context manager for database sessions.

    Usage:
        with get_db() as db:
            clients = db.query(Client).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def test_connection() -> bool:
    """Test that the database connection is working. Returns True/False."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"[DB] Connection failed: {e}")
        return False


def create_all_tables():
    """Create all tables from SQLAlchemy models. Called on first run."""
    from app.database.base import Base
    # Import all models so they register with Base.metadata
    from app.core.models import user, client, loan, repayment, collateral, audit_log  # noqa
    Base.metadata.create_all(bind=engine)
    print("[DB] All tables created successfully.")