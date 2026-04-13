# AI-Based Loans Management System

> A production-grade, agentic AI-powered desktop loan management system built with Python.  
> Developed as a Final Year Project at **Bugema University** and deployed at **Bingongold Credit**, Ham Tower, Wandegeya, Kampala, Uganda.

---

## Overview

The AI-Based LMS replaces manual, paper-based loan management with a fully automated, intelligent desktop application. It supports the complete loan lifecycle — from client registration and loan application through to repayment tracking, AI-powered risk assessment, and natural language interaction via a built-in chatbot.

The system was designed and case-studied at **Bingongold Credit**, a growing microfinance institution in Kampala that offers Business Loans, School Fees Loans, Tax Clearance Loans, Development Loans, and Asset Acquisition Loans at a fixed 10% interest rate.

---

## Key Features

- **Role-Based Access Control** — Admin, Manager, and Loan Officer roles with separate permissions
- **Client Management** — Full borrower profiles with NIN, contact details, next of kin, and employment info
- **Loan Processing** — Application, approval workflow, and automated 10% interest calculation
- **Repayment Tracking** — Real-time payment recording, outstanding balance, and overdue detection
- **AI Risk Agent** — Powered by Anthropic Claude API: risk scoring (LOW / MEDIUM / HIGH), portfolio alerts, and loan health summaries
- **AI Chatbot** — Ask questions in plain English: *"Show all overdue loans"*, *"How much has John paid?"*
- **Reports & Exports** — Generate PDF and Word documents for loan agreements and financial summaries
- **Collateral Management** — Attach and manage document scans and photos per loan
- **Audit Trail** — Every action is logged for accountability and transparency

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| UI Framework | CustomTkinter |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.x |
| AI / LLM | Anthropic Claude API (`claude-sonnet-4-20250514`) |
| ML Risk Model | Scikit-learn (Logistic Regression) |
| Reports | ReportLab (PDF), python-docx (Word) |
| Config | python-dotenv |
| Migrations | Alembic |

---

## Project Structure

```
AI-Based_LMS/
│
├── main.py                          # Application entry point — run this to start
├── .env                             # Environment variables (never commit to Git)
├── .env.example                     # Safe template for environment setup
├── requirements.txt                 # All Python dependencies
├── alembic.ini                      # Database migration config
├── README.md
│
├── app/
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py              # Central app settings (DB URL, API keys, constants)
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py            # SQLAlchemy engine + session factory
│   │   ├── base.py                  # Declarative base for all models
│   │   └── migrations/              # Alembic auto-generated migration versions
│   │
│   ├── core/
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py              # System user / staff accounts
│   │   │   ├── client.py            # Borrower / client profiles
│   │   │   ├── loan.py              # Loan records and financial fields
│   │   │   ├── repayment.py         # Payment transactions
│   │   │   ├── collateral.py        # Collateral document attachments
│   │   │   └── audit_log.py         # System-wide audit trail
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py      # Login, password hashing, session
│   │   │   ├── client_service.py    # Client CRUD operations
│   │   │   ├── loan_service.py      # Loan processing and interest calculation
│   │   │   ├── repayment_service.py # Payment recording and balance tracking
│   │   │   └── report_service.py    # PDF and Word report generation
│   │   │
│   │   └── agents/
│   │       ├── __init__.py
│   │       ├── ai_agent.py          # Anthropic-powered risk assessment agent
│   │       └── chatbot.py           # Natural language chatbot interface
│   │
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── app_root.py              # Root window and screen manager
│   │   │
│   │   ├── styles/
│   │   │   ├── __init__.py
│   │   │   └── theme.py             # Colors, fonts, and widget style presets
│   │   │
│   │   ├── components/
│   │   │   ├── __init__.py
│   │   │   ├── sidebar.py           # Navigation sidebar
│   │   │   ├── header.py            # Top header bar
│   │   │   ├── data_table.py        # Reusable sortable data table
│   │   │   ├── stat_card.py         # Dashboard KPI card
│   │   │   ├── modal.py             # Reusable modal/dialog
│   │   │   └── loading_spinner.py   # Async loading indicator
│   │   │
│   │   └── screens/
│   │       ├── __init__.py
│   │       ├── login_screen.py      # Authentication / sign-in
│   │       ├── dashboard_screen.py  # Main overview dashboard
│   │       ├── clients_screen.py    # Client management
│   │       ├── loans_screen.py      # Loan management
│   │       ├── repayments_screen.py # Repayment recording and history
│   │       ├── reports_screen.py    # Report generation
│   │       ├── agent_screen.py      # AI Risk Agent panel
│   │       ├── chatbot_screen.py    # AI Chatbot interface
│   │       └── settings_screen.py   # System settings and user management
│   │
│   └── utils/
│       ├── __init__.py
│       ├── validators.py            # Input validation helpers
│       ├── formatters.py            # Currency, date, and number formatters
│       └── file_manager.py          # Collateral file upload and access
│
├── assets/
│   ├── images/
│   │   └── logo.png                 # Application logo
│   ├── icons/                       # UI icon assets
│   └── fonts/                       # Custom fonts (if any)
│
├── tests/
│   ├── unit/
│   │   ├── test_loan_service.py
│   │   ├── test_repayment_service.py
│   │   └── test_validators.py
│   └── integration/
│       ├── test_db_connection.py
│       └── test_auth_flow.py
│
├── docs/
│   ├── erd.png                      # Entity Relationship Diagram
│   └── user_manual.md               # Staff user guide
│
└── scripts/
    ├── seed_db.py                   # Populate database with sample/test data
    └── create_admin.py              # One-time script to create the first admin account
```

---

## Database Schema (PostgreSQL)

| Table | Description |
|-------|-------------|
| `users` | Staff accounts with roles (admin, manager, loan_officer) |
| `clients` | Borrower profiles |
| `loans` | Loan records linked to clients |
| `repayments` | Payment transactions per loan |
| `collaterals` | Document and image attachments per loan |
| `audit_logs` | Full action history for every system event |

---

## Setup & Installation

### Prerequisites
- Python 3.12+
- PostgreSQL 16+
- pip

### 1. Clone the repository
```bash
git clone https://github.com/Tamujacob/AI-Based-LMS.git
cd AI-Based-LMS
```

### 2. Create and activate a virtual environment
```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
```bash
cp .env.example .env
# Open .env and fill in your PostgreSQL credentials and Anthropic API key
```

### 5. Create the database
```sql
-- In psql or pgAdmin:
CREATE DATABASE ailms_db;
```

### 6. Run database migrations
```bash
alembic upgrade head
```

### 7. Create the first admin account
```bash
python scripts/create_admin.py
```

### 8. Launch the application
```bash
python main.py
```

---

## Default User Roles

| Role | Permissions |
|------|------------|
| `admin` | Full system access, user management, all settings |
| `manager` | All loan operations, reports, AI agent access |
| `loan_officer` | Client registration, loan entry, repayment recording |

---

## AI Features

### AI Risk Agent
Powered by the **Anthropic Claude API**, the risk agent:
- Analyses borrower history, loan amount, duration, and collateral
- Returns a **LOW / MEDIUM / HIGH** risk rating with written reasoning
- Scans the full portfolio for overdue and at-risk loans
- Generates plain-English loan health summaries for quick review

### AI Chatbot
A natural language interface built into the dashboard. Staff can type questions like:
- *"Show me all overdue loans"*
- *"How much has John Mukasa paid so far?"*
- *"What is our total outstanding balance this month?"*
- *"Which loans haven't had a payment in 60 days?"*

Both AI features use the **Anthropic Claude API**. Free-tier credits from [console.anthropic.com](https://console.anthropic.com) are sufficient for academic and testing use.

---

## Interest Calculation

Fixed rate: **10% flat** on principal (configurable in `.env`).

```
Total Interest      = Principal × 10%
Total Repayable     = Principal + Total Interest
Monthly Installment = Total Repayable ÷ Duration (months)
```

---

## Case Study Institution

This system was developed for and tested at:

**Bingongold Credit**  
4th Floor, Ham Tower, Wandegeya, Kampala, Uganda  
*Established 2021 — providing Business, School Fees, Tax Clearance, Development, and Asset Acquisition loans.*

The institution previously relied on a fully manual, paper-based system. This project digitises and automates their entire loan management workflow.

---

## Author

**Tamukedde Jacob** 
Bachelor of Information Technology — Final Year Project  
Bugema University, Kampala, Uganda

📧 jacobtamukedde@gmail.com  
📞 +256 787 022 284  
🔗 [github.com/Tamujacob](https://github.com/Tamujacob)

---

## License

Academic and educational use. Not for commercial redistribution without written permission from the author.