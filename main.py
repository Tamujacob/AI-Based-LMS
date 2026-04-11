"""
main.py
─────────────────────────────────────────────
Entry point for the AI-Based Loans Management System.
Run this file to start the application:

    python main.py
"""

import sys
import os

# Make sure the project root is on the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.connection import create_all_tables, test_connection
from app.ui.app_root import AppRoot


def main():
    print("\n=== AI-Based Loans Management System ===")
    print("Bingongold Credit, Kampala, Uganda\n")

    # 1. Test database connection
    print("Connecting to database...")
    if not test_connection():
        print("\nERROR: Cannot connect to PostgreSQL.")
        print("Please check:")
        print("  1. PostgreSQL is running on your machine")
        print("  2. Your .env file has the correct DB_PASSWORD")
        print("  3. The database 'ailms_db' exists in DBeaver")
        print("\nCreate the database in DBeaver by running:")
        print("  CREATE DATABASE ailms_db;")
        sys.exit(1)

    print("Database connected ✔")

    # 2. Create tables if they don't exist yet
    print("Initialising tables...")
    create_all_tables()
    print("Tables ready ✔\n")

    # 3. Launch the GUI
    print("Starting application...\n")
    app = AppRoot()
    app.mainloop()


if __name__ == "__main__":
    main()