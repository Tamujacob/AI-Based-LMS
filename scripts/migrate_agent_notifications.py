"""
scripts/migrate_agent_notifications.py
──────────────────────────────────────
One-time migration: adds the unique_ref column to the
agent_notifications table that was created by an older version
of background_agent.py.

Run once:
    cd ~/Desktop/AI-Based-LMS
    source venv/bin/activate
    python scripts/migrate_agent_notifications.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import get_db
from sqlalchemy import text

def migrate():
    print("Running migration: agent_notifications → add unique_ref column")

    with get_db() as db:

        # 1. Check if column already exists
        result = db.execute(text("""
            SELECT column_name
            FROM   information_schema.columns
            WHERE  table_name  = 'agent_notifications'
              AND  column_name = 'unique_ref'
        """)).fetchone()

        if result:
            print("✅ unique_ref column already exists — nothing to do.")
            return

        # 2. Add the column with a default of empty string
        print("   Adding unique_ref column...")
        db.execute(text("""
            ALTER TABLE agent_notifications
            ADD COLUMN unique_ref VARCHAR(80) NOT NULL DEFAULT ''
        """))

        # 3. Back-fill existing rows so the column is consistent
        # Existing rows had no unique_ref so we set it to notif_type
        # (safe fallback — they won't duplicate against new rows)
        print("   Back-filling existing rows...")
        db.execute(text("""
            UPDATE agent_notifications
            SET    unique_ref = notif_type
            WHERE  unique_ref = ''
        """))

        db.commit()
        print("✅ Migration complete — unique_ref column added and back-filled.")

if __name__ == "__main__":
    migrate()