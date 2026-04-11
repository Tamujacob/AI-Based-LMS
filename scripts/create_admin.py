"""
scripts/create_admin.py
─────────────────────────────────────────────
Run this ONCE to create the first admin account.
Usage: python scripts/create_admin.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import create_all_tables, test_connection
from app.core.services.auth_service import AuthService


def main():
    print("\n=== Bingongold Credit LMS — Admin Setup ===\n")

    if not test_connection():
        print("ERROR: Cannot connect to PostgreSQL.")
        print("Make sure PostgreSQL is running and your .env file is correct.")
        sys.exit(1)

    print("Database connected. Creating tables...")
    create_all_tables()

    print("\nEnter details for the admin account:\n")
    full_name = input("Full Name: ").strip()
    username  = input("Username: ").strip()
    password  = input("Password: ").strip()

    if not full_name or not username or not password:
        print("ERROR: All fields are required.")
        sys.exit(1)

    try:
        user = AuthService.create_user(
            full_name=full_name,
            username=username,
            password=password,
            role="admin",
        )
        print(f"\n✔ Admin account created successfully!")
        print(f"  Name    : {user.full_name}")
        print(f"  Username: {user.username}")
        print(f"  Role    : {user.role.value}")
        print(f"\nYou can now run: python main.py\n")
    except ValueError as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()