"""
scripts/add_indexes.py
──────────────────────────────────────────────────────────────
Adds database indexes to speed up the most common queries.

Without indexes, PostgreSQL does a full table scan for every
query — reading all 200 (or 10,000) rows every time.
With indexes, queries run in microseconds regardless of table size.

Run once:
    python scripts/add_indexes.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    print("\n" + "="*55)
    print("  Bingongold Credit — Add Database Indexes")
    print("="*55)

    from app.database.connection import engine
    from sqlalchemy import text

    indexes = [
        # clients — searched by name, NIN, phone constantly
        ("idx_clients_full_name",
         "CREATE INDEX IF NOT EXISTS idx_clients_full_name "
         "ON clients (full_name)"),

        ("idx_clients_nin",
         "CREATE INDEX IF NOT EXISTS idx_clients_nin "
         "ON clients (nin)"),

        ("idx_clients_phone",
         "CREATE INDEX IF NOT EXISTS idx_clients_phone "
         "ON clients (phone_number)"),

        ("idx_clients_active",
         "CREATE INDEX IF NOT EXISTS idx_clients_active "
         "ON clients (is_active)"),

        # loans — filtered by status, joined to clients constantly
        ("idx_loans_status",
         "CREATE INDEX IF NOT EXISTS idx_loans_status "
         "ON loans (status)"),

        ("idx_loans_client_id",
         "CREATE INDEX IF NOT EXISTS idx_loans_client_id "
         "ON loans (client_id)"),

        ("idx_loans_due_date",
         "CREATE INDEX IF NOT EXISTS idx_loans_due_date "
         "ON loans (due_date)"),

        ("idx_loans_loan_number",
         "CREATE INDEX IF NOT EXISTS idx_loans_loan_number "
         "ON loans (loan_number)"),

        # repayments — joined to loans, sorted by date
        ("idx_repayments_loan_id",
         "CREATE INDEX IF NOT EXISTS idx_repayments_loan_id "
         "ON repayments (loan_id)"),

        ("idx_repayments_payment_date",
         "CREATE INDEX IF NOT EXISTS idx_repayments_payment_date "
         "ON repayments (payment_date DESC)"),

        # audit_logs — sorted by timestamp
        ("idx_audit_logs_created_at",
         "CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at "
         "ON audit_logs (created_at DESC)"),

        ("idx_audit_logs_user_id",
         "CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id "
         "ON audit_logs (user_id)"),
    ]

    with engine.connect() as conn:
        for name, sql in indexes:
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"  ✓  {name}")
            except Exception as e:
                print(f"  ✗  {name}: {e}")

    print("\n  " + "="*53)
    print("  ✓  Indexes created. Queries will now be instant.")
    print("  " + "="*53 + "\n")


if __name__ == "__main__":
    main()