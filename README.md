# AI-Based Loans Management System

> A production-grade, agentic AI-powered desktop loan management system built with Python.
> Developed as a Final Year Project at **Bugema University** and deployed at **Bingongold Credit**, Ham Tower, Wandegeya, Kampala, Uganda.

---

## Overview

The AI-Based LMS replaces manual, paper-based loan management with a fully automated, intelligent desktop application. It supports the complete loan lifecycle — from client registration and loan application through to repayment tracking, AI-powered risk assessment, financial statement analysis, and natural language interaction via a built-in chatbot.

The system was designed and case-studied at **Bingongold Credit**, a growing microfinance institution in Kampala that offers Business Loans, School Fees Loans, Tax Clearance Loans, Development Loans, and Asset Acquisition Loans at a fixed 10% interest rate.

---

## Key Features

- **Role-Based Access Control** — Admin, Manager, and Loan Officer roles with separate permissions
- **Client Management** — Full borrower profiles with NIN, contact details, next of kin, and employment info
- **Loan Processing** — Application, approval workflow, and automated 10% interest calculation
- **Repayment Tracking** — Real-time payment recording, outstanding balance, and overdue detection
- **Financial Statement Analysis** — Upload MTN MoMo, Airtel Money, or bank PDF statements for AI-powered loan sizing with three scenario cards (Conservative / Standard / Extended)
- **AI Risk Agent** — Powered by Groq API (llama-3.3-70b, free): risk scoring (LOW / MEDIUM / HIGH), portfolio alerts, and loan health summaries
- **AI Chatbot** — Ask questions in plain English with live database context. Upload statements directly in chat for instant loan recommendations
- **Reports & Exports** — Generate PDF and Word documents for loan agreements and financial summaries
- **Collateral Management** — Attach and manage document scans and photos per loan
- **Audit Trail** — Every action is logged for accountability and transparency
- **Screen Caching** — Navigation is instant after first visit; data refreshes every 30 seconds
- **Background Loading** — All data loads in background threads so the UI never freezes

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| UI Framework | CustomTkinter 5.2.2 |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.x |
| AI / LLM | Groq API — llama-3.3-70b-versatile (free tier) |
| ML Risk Model | Scikit-learn — RandomForestClassifier |
| Statement Parser | pdfplumber + pytesseract (OCR) |
| Reports | ReportLab (PDF), python-docx (Word) |
| Config | python-dotenv |

---

## Project Structure

```
AI-Based_LMS/
│
├── main.py                          # Entry point — run this to start
├── .env                             # Environment variables (never commit)
├── .env.example                     # Safe template for environment setup
├── requirements.txt                 # All Python dependencies
├── README.md
│
├── app/
│   ├── config/
│   │   └── settings.py              # Central settings — DB URL, API keys, constants
│   │
│   ├── database/
│   │   ├── base.py                  # SQLAlchemy declarative base
│   │   └── connection.py            # Engine, session factory, get_db() context manager
│   │                                # Pool: size=20, overflow=30, timeout=5s, semaphore=8
│   │
│   ├── core/
│   │   ├── models/
│   │   │   ├── user.py              # Staff accounts (admin / manager / loan_officer)
│   │   │   ├── client.py            # Borrower profiles
│   │   │   ├── loan.py              # Loan records and financial fields
│   │   │   ├── repayment.py         # Payment transactions
│   │   │   ├── collateral.py        # Document attachments per loan
│   │   │   ├── audit_log.py         # Full system audit trail
│   │   │   └── statement_analysis.py # Stores statement analysis results per loan
│   │   │
│   │   ├── services/
│   │   │   ├── auth_service.py      # Login, bcrypt password hashing
│   │   │   ├── client_service.py    # Client CRUD operations
│   │   │   ├── loan_service.py      # Loan lifecycle and interest calculation
│   │   │   ├── repayment_service.py # Payment recording and balance tracking
│   │   │   └── report_service.py    # PDF and Word report generation
│   │   │
│   │   └── agents/
│   │       ├── ai_core.py           # Groq API router — online/offline fallback
│   │       ├── ai_agent.py          # Risk assessment and portfolio scanning
│   │       ├── chatbot.py           # Natural language chatbot with DB context
│   │       ├── statement_parser.py  # Parses MTN/Airtel/bank PDF statements
│   │       ├── loan_ceiling_engine.py # Calculates max safe loan from statement
│   │       ├── credit_scorer.py     # Credit scoring logic
│   │       ├── local_scorer.py      # Offline ML risk scoring
│   │       ├── model_trainer.py     # Trains RandomForestClassifier
│   │       ├── payment_planner.py   # Repayment schedule generator
│   │       └── reminder_service.py  # Overdue loan alert service
│   │
│   └── ui/
│       ├── app_root.py              # Root window — screen caching, 30s refresh throttle
│       ├── styles/
│       │   └── theme.py             # Colors, fonts, widget style presets
│       │
│       ├── components/
│       │   ├── sidebar.py           # Navigation sidebar (logo cached at class level)
│       │   ├── data_table.py        # Reusable scrollable data table
│       │   ├── stat_card.py         # Dashboard KPI card
│       │   ├── date_picker.py       # Date picker widget
│       │   ├── save_dialog.py       # Themed save/open file dialogs
│       │   └── statement_analysis_widget.py  # Statement upload + 3-scenario cards
│       │
│       └── screens/
│           ├── login_screen.py      # Two-column branded login
│           ├── dashboard_screen.py  # KPI cards, loan status overview, recent activity
│           ├── clients_screen.py    # Searchable client table + add/edit form
│           ├── loans_screen.py      # Loan list, new loan form, statement analysis
│           ├── repayments_screen.py # Record payments, print receipts, payment history
│           ├── agent_screen.py      # AI risk scoring and portfolio scan
│           ├── chatbot_screen.py    # AI chat with 📎 statement upload button
│           ├── reports_screen.py    # One-click PDF and Word generation
│           ├── users_screen.py      # User management (admin only)
│           ├── logs_screen.py       # Audit log viewer
│           └── settings_screen.py  # App settings, Groq model selector
│
├── assets/
│   └── images/
│       └── logo.png                 # Bingongold Credit logo
│
├── data/
│   ├── collaterals/                 # Uploaded collateral documents
│   └── training/
│       └── training_data_200.json   # 200 synthetic records for ML training
│
├── models/
│   ├── risk_model.pkl               # Trained RandomForest model
│   └── feature_info.json            # Model feature metadata
│
└── scripts/
    ├── create_admin.py              # One-time: create first admin account
    ├── train_model.py               # Train offline risk scoring model
    ├── test_training_data.py        # Validate training data before training
    ├── reset_and_reseed.py          # Drop all tables, recreate, seed 50 records
    └── add_indexes.py               # Add DB indexes for query performance
```

---

## Database Schema (PostgreSQL)

| Table | Description |
|---|---|
| `users` | Staff accounts with roles (admin, manager, loan_officer) |
| `clients` | Borrower profiles with NIN, phone, employment, next of kin |
| `loans` | Loan records — principal, interest, status, risk score |
| `repayments` | Payment transactions per loan with receipt numbers |
| `collaterals` | Document and image attachments per loan |
| `audit_logs` | Full action history for every system event |
| `statement_analyses` | Financial statement results linked to loans |

---

## Setup & Installation

### Prerequisites

- Python 3.12+
- PostgreSQL 16+
- `sudo apt-get install python3-tk` (Ubuntu — required for GUI)

### 1. Clone the repository

```bash
git clone https://github.com/Tamujacob/AI-Based-LMS.git
cd AI-Based-LMS
```

### 2. Create and activate virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
pip install scikit-learn pdfplumber joblib pandas numpy groq
```

### 4. Create the database

```bash
sudo -u postgres psql
```
```sql
CREATE DATABASE ailms_db;
\q
```

### 5. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ailms_db
DB_USER=postgres
DB_PASSWORD=your_postgres_password

GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile

APP_NAME=AI-Based Loans Management System
APP_VERSION=1.0.0
DEBUG=False
SECRET_KEY=change_this_in_production
DEFAULT_INTEREST_RATE=10.0
COLLATERAL_UPLOAD_DIR=./data/collaterals
TRAINING_DATA_PATH=./data/training/training_data_200.json
```

Get a **free** Groq API key at [console.groq.com](https://console.groq.com) — no credit card needed.

### 6. Seed the database with sample data

```bash
python scripts/reset_and_reseed.py
```

### 7. Add database indexes (important for performance)

```bash
python scripts/add_indexes.py
```

### 8. Train the offline AI risk model

```bash
python scripts/train_model.py
```

### 9. Launch the application

```bash
python main.py
```

---

## Default Login Credentials

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | Admin — full access |
| `manager` | `manager123` | Manager — loans and reports |
| `officer` | `officer123` | Loan Officer — client and repayment entry |

---

## User Roles

| Role | Permissions |
|---|---|
| `admin` | Full system access, user management, all settings |
| `manager` | All loan operations, reports, AI agent access |
| `loan_officer` | Client registration, loan entry, repayment recording |

---

## AI Features

### AI Risk Agent (agent_screen.py)
Powered by **Groq API** (llama-3.3-70b, free tier):
- Analyses borrower history, loan amount, duration, and income
- Returns **LOW / MEDIUM / HIGH** risk rating with written reasoning
- Scans the full portfolio for overdue and at-risk loans
- Falls back to offline **RandomForestClassifier** model when no internet

### AI Chatbot (chatbot_screen.py)
- Natural language interface with live database context
- **📎 Upload button** — attach MoMo or bank statement PDF directly in chat
- Statement is parsed, income extracted, loan ceiling calculated
- AI responds with a personalised loan recommendation
- Suggested queries panel for quick access

### Financial Statement Analysis
- Parses **MTN Mobile Money**, **Airtel Money**, and **bank PDF statements**
- Extracts transactions, calculates monthly income/expense/net flow
- Generates three loan scenarios: **Conservative**, **Standard**, **Extended**
- Each scenario shows principal, duration, monthly instalment, and % of income
- Clicking **Accept** auto-fills the loan application form

---

## Interest Calculation

Fixed rate: **10% flat** on principal (configurable in `.env`).

```
Total Interest      = Principal × 10%
Total Repayable     = Principal + Total Interest
Monthly Installment = Total Repayable ÷ Duration (months)
```

---

## Performance Notes

- All DB queries run in background threads — UI never freezes
- Screen caching: built once, shown/hidden with pack/pack_forget
- Smart refresh: data reloads only after 30s (dashboard) or 60s (other screens)
- Raw SQL used for bulk table loads (10-50x faster than ORM)
- Database indexes on: clients (name, NIN, phone), loans (status, client_id, due_date), repayments (loan_id, date)
- Connection pool: size=20, overflow=30, timeout=5s, semaphore=8 concurrent threads

---

## Case Study Institution

**Bingongold Credit**
4th Floor, Ham Tower, Wandegeya, Kampala, Uganda
*Providing Business, School Fees, Tax Clearance, Development, and Asset Acquisition loans.*

---

## Author

**Tamukedde Jacob** | 24/BIT/BU/R/0010
Bachelor of Information Technology — Final Year Project
Bugema University, Kampala, Uganda

📧 [jacobtamukedde@gmail.com](mailto:jacobtamukedde@gmail.com)
📞 +256 787 022 284
🔗 [github.com/Tamujacob](https://github.com/Tamujacob)

---

## License

Academic and educational use. Not for commercial redistribution without written permission from the author.