"""
scripts/reset_and_reseed.py
──────────────────────────────────────────────────────────────
Drops all tables, recreates them, and seeds with 50 records.
Run this instead of using pgAdmin.

Usage:
    python scripts/reset_and_reseed.py
"""

import sys
import os
import random
import bcrypt
from datetime import date, timedelta, datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
random.seed(42)

# ── Ugandan data ───────────────────────────────────────────────────────────────

FIRST_NAMES = [
    "Tamukedde","Nakato","Kayiza","Musisi","Nalwoga","Kiggundu","Namutebi",
    "Ssebuliba","Nambooze","Wasswa","Nakimuli","Nanteza","Lubega","Namukasa",
    "Mulindwa","Nabirye","Katumba","Sserwanga","Kaggwa","Nankya","Mutyaba",
    "Nabwire","Nakigozi","Kizito","Nalugo","Muwonge","Tumwebaze","Mugisha",
    "Atim","Okello","Akello","Opio","Odong","Kyeyune","Ddungu","Tendo",
]

LAST_NAMES = [
    "Mukasa","Ssebunya","Nanteza","Kawuma","Mubiru","Kibirige","Nsubuga",
    "Nalwanga","Namugga","Buyinza","Naluwooza","Muwanguzi","Ssali","Matovu",
    "Wasswa","Nabirye","Nakato","Mugisha","Tumusiime","Atuhaire","Byarugaba",
    "Tusiime","Tumwebaze","Kemigisha","Mbabazi","Arinaitwe","Muhwezi","Kato",
]

DISTRICTS = [
    "Kampala","Wakiso","Mukono","Jinja","Mbale","Mbarara","Gulu",
    "Masaka","Kabale","Tororo","Hoima","Iganga","Entebbe",
]

OCCUPATIONS = [
    "Teacher","Boda Boda Rider","Market Vendor","Carpenter","Mason",
    "Tailor","Farmer","Nurse","Small Business Owner","Driver",
    "Security Guard","Mechanic","Salon Operator","Shopkeeper",
    "Accountant","Police Officer","Civil Servant","Trader",
]

LOAN_TYPES = [
    "Business Loan","School Fees Loan","Tax Clearance Loan",
    "Development Loan","Asset Acquisition Loan",
]

PURPOSES = [
    "Buy stock for shop","Pay school fees","Clear tax arrears",
    "Buy motorcycle","Expand salon","Buy construction materials",
    "Purchase farming inputs","Medical expenses","Business capital",
    "Pay land rates","Repair house","Buy household furniture",
]

PAYMENT_METHODS = ["Cash","Mobile Money","Bank Transfer","Cheque"]


def rname():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def rphone():
    return f"0{random.choice(['701','702','703','772','782','752','756'])}{random.randint(100000,999999)}"

def rnin():
    import string
    return f"CM{random.randint(10000000,99999999)}{random.choice(string.ascii_uppercase)}{random.choice(string.ascii_uppercase)}"

def rdate(start_year=2024, end_year=2025):
    start = date(start_year, 1, 1)
    end   = date(end_year, 12, 31)
    return start + timedelta(days=random.randint(0, (end - start).days))


def main():
    print("\n" + "="*55)
    print("  Bingongold Credit — Reset & Reseed (50 records)")
    print("="*55)

    from app.database.connection import engine
    from app.database.base import Base

    # ── Step 1: Drop all tables ────────────────────────────────────────────
    print("\n  Step 1: Dropping all tables...")
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
        conn.commit()
    print("  ✓  All tables dropped")

    # ── Step 2: Recreate tables ────────────────────────────────────────────
    print("\n  Step 2: Creating tables...")
    from app.core.models import user, client, loan, repayment, collateral, audit_log  # noqa
    try:
        from app.core.models import statement_analysis  # noqa
    except ImportError:
        pass
    Base.metadata.create_all(bind=engine)
    print("  ✓  Tables created")

    # ── Step 3: Seed data ──────────────────────────────────────────────────
    print("\n  Step 3: Seeding 50 records...")

    from app.database.connection import get_db
    from app.core.models.user       import User, UserRole
    from app.core.models.client     import Client
    from app.core.models.loan       import Loan, LoanStatus, LoanType
    from app.core.models.repayment  import Repayment, PaymentMethod, RepaymentStatus

    with get_db() as db:

        # ── Create users ───────────────────────────────────────────────────
        def make_user(full_name, username, password, role):
            hashed = bcrypt.hashpw(
                password.encode(), bcrypt.gensalt()).decode()
            u = User(
                full_name     = full_name,
                username      = username,
                password_hash = hashed,
                role          = UserRole(role),
                is_active     = True,
                created_at    = datetime.utcnow(),
            )
            db.add(u)
            db.flush()
            return u

        admin   = make_user("Tamukedde Jacob",  "admin",   "admin123",   "admin")
        manager = make_user("Sarah Nalwanga",    "manager", "manager123", "manager")
        officer = make_user("John Kato",         "officer", "officer123", "loan_officer")
        db.commit()
        print("  ✓  Users: admin / manager / officer")

        # ── Create 50 clients ──────────────────────────────────────────────
        clients   = []
        used_nins = set()

        for i in range(50):
            nin = rnin()
            while nin in used_nins:
                nin = rnin()
            used_nins.add(nin)

            c = Client(
                full_name                = rname(),
                nin                      = nin,
                phone_number             = rphone(),
                gender                   = random.choice(["Male", "Female"]),
                district                 = random.choice(DISTRICTS),
                village                  = random.choice([
                    "Wandegeya","Kikoni","Kabalagala","Ntinda",
                    "Bukoto","Kisaasi","Kansanga","Luzira"]),
                occupation               = random.choice(OCCUPATIONS),
                monthly_income           = str(random.choice([
                    400000,500000,600000,800000,1000000,1200000,1500000])),
                next_of_kin_name         = rname(),
                next_of_kin_phone        = rphone(),
                next_of_kin_relationship = random.choice([
                    "Spouse","Parent","Sibling","Friend"]),
                is_active                = True,
                created_at               = datetime.utcnow() - timedelta(
                    days=random.randint(0, 365)),
            )
            db.add(c)
            clients.append(c)

        db.commit()
        for c in clients:
            db.refresh(c)
        print(f"  ✓  {len(clients)} clients created")

        # ── Status distribution for 50 loans ──────────────────────────────
        # Realistic spread for a good demo
        statuses = (
            ["active"]    * 20 +
            ["completed"] * 12 +
            ["pending"]   * 8  +
            ["defaulted"] * 5  +
            ["approved"]  * 3  +
            ["rejected"]  * 2
        )
        random.shuffle(statuses)

        loans          = []
        receipt_counter = 1

        for i, client in enumerate(clients):
            principal  = random.choice([
                200000, 300000, 500000, 750000,
                1000000, 1500000, 2000000, 3000000])
            duration   = random.choice([3, 6, 9, 12, 18, 24])
            loan_type  = random.choice(LOAN_TYPES)
            status_str = statuses[i]
            app_date   = rdate(2024, 2025)
            interest   = Decimal(str(principal)) * Decimal("0.10")
            total_rep  = Decimal(str(principal)) + interest
            monthly    = total_rep / duration
            loan_num   = f"BG-{app_date.year}-{10001+i:05d}"

            l = Loan(
                loan_number         = loan_num,
                client_id           = client.id,
                created_by_id       = random.choice([admin.id, officer.id]),
                loan_type           = LoanType(loan_type),
                principal_amount    = Decimal(str(principal)),
                interest_rate       = Decimal("10.00"),
                total_interest      = interest,
                total_repayable     = total_rep,
                monthly_installment = monthly,
                duration_months     = duration,
                purpose             = random.choice(PURPOSES),
                status              = LoanStatus(status_str),
                application_date    = app_date,
                risk_score          = random.choice([
                    "LOW","MEDIUM","HIGH",None,None]),
                created_at          = datetime.combine(
                    app_date, datetime.min.time()),
            )

            if status_str in ("approved","active","completed","defaulted"):
                l.approval_date     = app_date + timedelta(days=2)
                l.disbursement_date = l.approval_date
                l.due_date          = l.disbursement_date + timedelta(
                    days=30 * duration)
                l.approved_by_id    = manager.id

            if status_str == "rejected":
                l.rejection_reason = "Insufficient income documentation"

            db.add(l)
            loans.append((l, status_str, float(monthly), float(total_rep), duration))

        db.commit()
        for l, *_ in loans:
            db.refresh(l)
        print(f"  ✓  {len(loans)} loans created")

        # ── Create repayments ──────────────────────────────────────────────
        repayment_count = 0
        today           = date(2026, 5, 4)

        for loan, status_str, monthly, total_rep, duration in loans:
            if status_str not in ("active","completed","defaulted"):
                continue
            if not loan.disbursement_date:
                continue

            months_passed = min(
                duration,
                max(1, (today - loan.disbursement_date).days // 30))

            if status_str == "completed":
                payments = duration
            elif status_str == "defaulted":
                payments = random.randint(1, max(1, months_passed // 2))
            else:
                payments = random.randint(
                    max(1, months_passed - 1), months_passed)

            for p in range(min(payments, duration)):
                pay_date = loan.disbursement_date + timedelta(days=30*(p+1))
                if random.random() < 0.15:
                    pay_date += timedelta(days=random.randint(1, 7))

                receipt_num = f"RCP-2025-{receipt_counter:06d}"
                receipt_counter += 1

                r = Repayment(
                    receipt_number        = receipt_num,
                    loan_id               = loan.id,
                    amount                = Decimal(str(round(monthly, 2))),
                    payment_date          = pay_date,
                    payment_method        = PaymentMethod(
                        random.choice(PAYMENT_METHODS)),
                    status                = RepaymentStatus("confirmed"),
                    transaction_reference = f"TXN{random.randint(100000,999999)}",
                    recorded_by_id        = random.choice([admin.id, officer.id]),
                    created_at            = datetime.combine(
                        pay_date, datetime.min.time()),
                )
                db.add(r)
                repayment_count += 1

        db.commit()
        print(f"  ✓  {repayment_count} repayment records created")

    # ── Summary ────────────────────────────────────────────────────────────
    from sqlalchemy import text as t
    with engine.connect() as conn:
        counts = {}
        for table in ["users","clients","loans","repayments"]:
            result = conn.execute(t(f"SELECT COUNT(*) FROM {table}"))
            counts[table] = result.scalar()

    status_counts = {}
    for _, status_str, *_ in loans:
        status_counts[status_str] = status_counts.get(status_str, 0) + 1

    print("\n  " + "="*53)
    print("  ✓  Database reset and seeded successfully!")
    print("  " + "-"*53)
    for k, v in counts.items():
        print(f"    {k:<14}: {v}")
    print("  " + "-"*53)
    print("  Loan Status Breakdown:")
    for s, c in sorted(status_counts.items()):
        print(f"    {s:<14}: {c}")
    print("\n  Login credentials:")
    print("    admin   / admin123")
    print("    manager / manager123")
    print("    officer / officer123")
    print("  " + "="*53 + "\n")


if __name__ == "__main__":
    main()