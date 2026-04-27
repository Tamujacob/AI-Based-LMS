"""
app/config/settings.py
─────────────────────────────────────────────
Central configuration for Bingongold LMS.
All settings are loaded from the .env file.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Database ──────────────────────────────────
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ailms_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)


GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


# ── Application ───────────────────────────────
APP_NAME = os.getenv("APP_NAME", "AI-Based Loans Management System")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# ── Security ──────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "change_me_in_production")

# ── Business Logic ────────────────────────────
DEFAULT_INTEREST_RATE = float(os.getenv("DEFAULT_INTEREST_RATE", "10.0"))

# Loan types offered by Bingongold Credit
LOAN_TYPES = [
    "Business Loan",
    "School Fees Loan",
    "Tax Clearance Loan",
    "Development Loan",
    "Asset Acquisition Loan",
]

# User roles
ROLES = ["admin", "manager", "loan_officer"]

# Loan status values
LOAN_STATUS = ["pending", "approved", "active", "completed", "defaulted", "rejected"]

# ── File Storage ──────────────────────────────
COLLATERAL_UPLOAD_DIR = os.getenv("COLLATERAL_UPLOAD_DIR", "./data/collaterals")
os.makedirs(COLLATERAL_UPLOAD_DIR, exist_ok=True)

# ── Window ────────────────────────────────────
WINDOW_WIDTH      = None   # determined at runtime
WINDOW_HEIGHT     = None   # determined at runtime
WINDOW_MIN_WIDTH  = 900
WINDOW_MIN_HEIGHT = 580