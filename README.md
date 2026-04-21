# AI-Based Loans Management System

> A production-grade, agentic AI-powered desktop loan management system built with Python 3.12.
> Developed as a Final Year Project at **Bugema University** and deployed at **Bingongold Credit**, Ham Tower, Wandegeya, Kampala, Uganda.

---

## Overview

The AI-Based LMS replaces the manual, paper-based loan management process at Bingongold Credit with a fully automated, intelligent desktop application. It covers the complete loan lifecycle — client registration, loan application, collateral management, repayment tracking, AI-powered risk assessment, natural language chatbot interaction, document generation, user management, and activity logging.

---

## Key Features

- **Role-Based Access Control** — Admin, Manager, and Loan Officer with separate permissions
- **Client Management** — Full borrower profiles with NIN uniqueness check, next-of-kin, and soft-delete
- **Loan Processing** — Application form with date picker, collateral photo upload, automated 10% interest calculation
- **Repayment Tracking** — Date picker, outstanding balance, auto-complete on full payment
- **Print Receipt** — Generates A5 PDF receipt with Bingongold letterhead and signature line
- **Loan Agreement** — Full A4 PDF with borrower details, financial terms, 6 conditions, and signature/stamp section
- **AI Risk Agent** — Powered by Anthropic Claude: LOW/MEDIUM/HIGH scoring, portfolio scan, overdue alerts
- **AI Chatbot** — Natural language queries with live database context (RAG)
- **Users Management** — Create, activate, deactivate accounts; reset passwords (Manager/Admin)
- **Activity Logs** — Full filterable audit trail with PDF export (Manager/Admin)
- **Reports** — Portfolio summary, overdue report, repayment history, client register (PDF + Word)
- **Collateral Documents** — Upload photos/scans directly from computer; thumbnails shown in loan view
- **Audit Trail** — Every system action logged with user, entity, and timestamp

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.12 |
| UI Framework | CustomTkinter | 5.2.2 |
| Database | PostgreSQL | 16 |
| ORM | SQLAlchemy | 2.0.x |
| AI / LLM | Anthropic Claude API | claude-sonnet-4 |
| Password Security | bcrypt | 4.2.x |
| PDF Reports | ReportLab | 4.2.x |
| Word Reports | python-docx | 1.1.x |
| Date Picker | tkcalendar | 1.6.x |
| Image Processing | Pillow | 10.x |
| Configuration | python-dotenv | 1.0.x |
| Migrations | Alembic | 1.14.x |

---

## Project Structure

```
AI-Based_LMS/
│
├── main.py                               # Entry point — tests DB, creates tables, launches GUI
├── .env                                  # Secrets (never commit to Git)
├── .env.example                          # Safe template for .env
├── .gitignore                            # Excludes .env, venv/, __pycache__, data/
├── requirements.txt                      # All Python dependencies
├── alembic.ini                           # Database migration config
├── README.md
│
├── app/
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py                   # Central config — reads .env, exposes all constants
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── base.py                       # SQLAlchemy DeclarativeBase
│   │   └── connection.py                 # Engine, SessionLocal, get_db(), test_connection()
│   │
│   ├── core/
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py                   # users table — staff accounts
│   │   │   ├── client.py                 # clients table — borrower profiles
│   │   │   ├── loan.py                   # loans table — financial records
│   │   │   ├── repayment.py              # repayments table — payment transactions
│   │   │   ├── collateral.py             # collaterals table — document metadata
│   │   │   └── audit_log.py              # audit_logs table — action history
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py           # Login, bcrypt hashing, user CRUD
│   │   │   ├── client_service.py         # Client CRUD, NIN lookup, soft delete
│   │   │   ├── loan_service.py           # Loan lifecycle, interest calc, stats
│   │   │   ├── repayment_service.py      # Record payments, balance, auto-complete
│   │   │   └── report_service.py         # PDF and Word report generation
│   │   │
│   │   └── agents/
│   │       ├── __init__.py
│   │       ├── ai_agent.py               # Claude API — risk scoring, portfolio scan
│   │       └── chatbot.py                # Claude API — RAG chatbot with live DB context
│   │
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── app_root.py                   # Window manager, screen switcher, session state
│   │   │
│   │   ├── styles/
│   │   │   ├── __init__.py
│   │   │   └── theme.py                  # Brand colours, fonts, widget presets
│   │   │
│   │   ├── components/
│   │   │   ├── __init__.py
│   │   │   ├── sidebar.py                # Navigation sidebar with logo
│   │   │   ├── data_table.py             # Reusable scrollable table
│   │   │   ├── stat_card.py              # Dashboard KPI card
│   │   │   └── date_picker.py            # ★ Calendar popup date input widget
│   │   │
│   │   └── screens/
│   │       ├── __init__.py
│   │       ├── login_screen.py           # Branded login — green panel + white form
│   │       ├── dashboard_screen.py       # KPI cards, status overview, recent activity
│   │       ├── clients_screen.py         # Register/edit borrowers
│   │       ├── loans_screen.py           # Apply loans, collateral upload, date picker
│   │       ├── repayments_screen.py      # Record payments, print A5 receipt
│   │       ├── agent_screen.py           # AI risk scoring, portfolio scan
│   │       ├── chatbot_screen.py         # Natural language chatbot interface
│   │       ├── reports_screen.py         # Reports + loan agreement with signatures
│   │       ├── users_screen.py           # ★ User management (Manager/Admin)
│   │       ├── logs_screen.py            # ★ Activity audit log (Manager/Admin)
│   │       └── settings_screen.py        # Change password, system info
│   │
│   └── utils/
│       └── __init__.py
│
├── assets/
│   └── images/
│       └── logo.png                      # Bingongold Credit logo
│
├── scripts/
│   └── create_admin.py                   # One-time admin account setup script
│
└── data/
    └── collaterals/                      # Uploaded collateral files (auto-created)
```

> Files marked ★ are new additions beyond the original design.

---

## Database Schema

| Table | Key Fields | Relationships |
|-------|-----------|---------------|
| `users` | id, username, password_hash, role, is_active | Referenced by loans, audit_logs |
| `clients` | id, full_name, nin (unique), phone_number, is_active | One-to-many with loans |
| `loans` | id, loan_number, client_id FK, status, principal_amount, risk_score, due_date | References clients and users; one-to-many with repayments and collaterals |
| `repayments` | id, receipt_number, loan_id FK, amount, payment_date, payment_method | Many-to-one with loans |
| `collaterals` | id, loan_id FK, description, file_path, file_type | Many-to-one with loans |
| `audit_logs` | id, user_id FK, action, entity_type, entity_id, timestamp | References users |

---

## Application Screens

| Screen | Access | Key Functionality |
|--------|--------|------------------|
| Login | Public | Branded login, bcrypt authentication |
| Dashboard | All | KPI cards, loan status, recent repayments |
| Clients | All | Register/edit/search borrowers |
| Loans | All | Apply, approve, reject; collateral upload; date picker |
| Repayments | All | Record payment with date picker; print receipt PDF |
| AI Agent | Manager + Admin | Risk scoring, portfolio scan, overdue alerts |
| AI Chatbot | Manager + Admin | Natural language portfolio queries |
| Reports | Manager + Admin | 5 report types including loan agreement |
| Users | Manager + Admin | Create, activate/deactivate, reset passwords |
| Activity Logs | Manager + Admin | Filterable audit trail with PDF export |
| Settings | All (admin extras) | Change password, create users, system info |

---

## Role Permissions

| Feature | Loan Officer | Manager | Admin |
|---------|-------------|---------|-------|
| Login and dashboard | Yes | Yes | Yes |
| Register clients | Yes | Yes | Yes |
| Apply for loans | Yes | Yes | Yes |
| Record repayments | Yes | Yes | Yes |
| Print receipts | Yes | Yes | Yes |
| Approve / reject loans | No | Yes | Yes |
| AI Agent and Chatbot | No | Yes | Yes |
| Generate reports | No | Yes | Yes |
| Users management | No | Yes | Yes |
| Activity logs | No | Yes | Yes |
| Create system users | No | No | Yes |

---

## Setup & Installation

### Prerequisites
- Python 3.12+
- PostgreSQL 16+
- pip

### Steps

```bash
# 1. Clone
git clone https://github.com/Tamujacob/AI-Based-LMS.git
cd AI-Based-LMS

# 2. Virtual environment
python -m venv venv
source venv/bin/activate       # Linux/Mac

# 3. Install tkinter (Ubuntu)
sudo apt-get install python3-tk

# 4. Install dependencies
pip install -r requirements.txt

# 5. Create database (in psql or pgAdmin)
CREATE DATABASE ailms_db;

# 6. Configure environment
cp .env.example .env
# Edit .env with your PostgreSQL password and Anthropic API key

# 7. Create first admin account
python scripts/create_admin.py

# 8. Launch
python main.py
```

---

## Interest Calculation

Fixed rate: **10% flat** on principal.

```
Total Interest      = Principal × 10%
Total Repayable     = Principal + Total Interest
Monthly Instalment  = Total Repayable ÷ Duration (months)
```

---

## AI Features

The AI features require an Anthropic API key from [console.anthropic.com](https://console.anthropic.com). Free-tier credits are sufficient for academic and demonstration use.

**AI Risk Agent** — analyses loan and borrower data, returns LOW/MEDIUM/HIGH risk rating with written reasoning, scans the full portfolio, and generates collections alerts for overdue loans.

**AI Chatbot** — uses Retrieval Augmented Generation (RAG): pulls a live database snapshot before every response so answers are based on real current data.

---

## Generated Documents

| Document | Format | Details |
|---------|--------|---------|
| Portfolio Summary | PDF + Word | All loans, status counts, totals |
| Loan Agreement | PDF | Letterhead, terms, borrower/officer signatures, stamp box |
| Overdue Loans Report | PDF | Past-due loans with client contacts |
| Repayment History | PDF | All payments for auditing |
| Client Register | PDF + Word | Full borrower list |
| Repayment Receipt | PDF (A5) | Per-payment receipt with signature line |
| Activity Log Report | PDF | Filtered audit trail |

---

## Case Study Institution

**Bingongold Credit**
4th Floor, Ham Tower, Wandegeya, Kampala, Uganda
*Tagline: "together as one"*
Established 2021 — providing Business, School Fees, Tax Clearance, Development, and Asset Acquisition loans at a fixed 10% interest rate.

---

## Author

**Tamukedde Jacob** | 24/BIT/BU/R/0010
Bachelor of Information Technology — Final Year Project
Bugema University, Kampala, Uganda

📧 jacobtamukedde@gmail.com
📞 +256 787 022 284
🔗 [github.com/Tamujacob](https://github.com/Tamujacob)

---

## License

Academic and educational use. Not for commercial redistribution without written permission from the author.