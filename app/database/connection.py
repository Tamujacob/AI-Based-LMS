"""
app/database/connection.py
─────────────────────────────────────────────
SQLAlchemy engine, session factory, and
get_db() context manager used throughout the app.

Performance fixes:
  - pool_size increased from 5 → 20
  - max_overflow increased from 10 → 30
  - pool_timeout reduced from 30s → 5s (fail fast, don't hang)
  - pool_recycle added — recycles connections every 5 minutes
    to prevent stale/dead connections building up
  - pool_pre_ping=True — tests connection before using it
  - DB_SEMAPHORE — limits concurrent DB threads to 8
    so screens don't pile up waiting for connections
  - get_db() now always closes session in finally block
    even if commit or rollback raises an exception
"""

import threading
from contextlib import contextmanager
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from app.config.settings import DATABASE_URL, DEBUG
from typing import Generator

# ── Connection pool ────────────────────────────────────────────────────────────
engine = create_engine(
    DATABASE_URL,

    # Pool sizing — enough for all screens + background threads simultaneously
    pool_size        = 20,        # was 5  — base connections kept open
    max_overflow     = 30,        # was 10 — extra connections allowed under load
    pool_timeout     = 5,         # was 30 — fail fast instead of hanging 30s
    pool_recycle     = 300,       # recycle connections every 5 minutes
    pool_pre_ping    = True,      # test connection before using — drops dead ones

    poolclass        = QueuePool,
    echo             = DEBUG,
)

# ── Session factory ────────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind        = engine,
    autocommit  = False,
    autoflush   = False,
    expire_on_commit = False,     # IMPORTANT: prevents "detached instance" errors
                                  # when accessing attributes after session closes
)

# ── Thread semaphore ───────────────────────────────────────────────────────────
# Limits how many background threads can query the DB simultaneously.
# Without this, navigating quickly launches 5+ threads all grabbing
# connections at once, exhausting the pool and causing 3-5 minute hangs.
DB_SEMAPHORE = threading.Semaphore(8)


# ── Context manager ────────────────────────────────────────────────────────────

@contextmanager

def get_db() -> Generator:
    """
    Context manager for database sessions.

    Acquires the DB semaphore to prevent connection pool exhaustion
    when multiple background threads query simultaneously.

    Usage:
        with get_db() as db:
            clients = db.query(Client).all()
    """
    acquired = DB_SEMAPHORE.acquire(timeout=10)   # wait max 10s for a slot
    if not acquired:
        raise RuntimeError(
            "Database is busy — too many concurrent queries. "
            "Please try again in a moment."
        )

    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            db.close()
        except Exception:
            pass
        DB_SEMAPHORE.release()


# ── Utility functions ──────────────────────────────────────────────────────────

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
    from app.core.models import user, client, loan, repayment, collateral, audit_log  # noqa
    try:
        from app.core.models import statement_analysis  # noqa
    except ImportError:
        pass
    Base.metadata.create_all(bind=engine)
    print("[DB] All tables created successfully.")


def get_pool_status() -> dict:
    """
    Returns current connection pool statistics.
    Useful for debugging — call from settings screen or console.
    """
    pool = engine.pool
    return {
        "pool_size":      pool.size(),
        "checked_in":     pool.checkedin(),
        "checked_out":    pool.checkedout(),
        "overflow":       pool.overflow(),
        "semaphore_value": DB_SEMAPHORE._value,
    }