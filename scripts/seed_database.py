"""
scripts/seed_database.py
──────────────────────────────────────────────────────────────
Seeds the database with 200 realistic Ugandan loan records
for presentation and testing purposes.

Creates:
  - 1 admin user (if not exists)
  - 2 extra staff users
  - 200 clients with full profiles
  - 200 loans across all statuses
  - Repayments for active/completed loans
  - Collateral records

Run:
    python scripts/seed_database.py

Safe to run multiple times — checks for existing data first.
"""

import sys
import os
import json
import random
from datetime import date, timedelta, datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

random.seed(99)

# ── Ugandan data pools ────────────────────────────────────────────────────────

FIRST_NAMES = [
    "Tamukedde","Nakato","Kayiza","Musisi","Nalwoga","Kiggundu","Namutebi",
    "Ssebuliba","Nambooze","Wasswa","Nakimuli","Mutesasira","Nanteza","Lubega",
    "Namukasa","Ssekandi","Nakyagaba","Mulindwa","Nabirye","Katumba","Namuli",
    "Sserwanga","Naigaga","Kaggwa","Nankya","Mutyaba","Nabwire","Ssemaganda",
    "Nakigozi","Kizito","Nalugo","Muwonge","Nakawunde","Ssebunya","Namazzi",
    "Tumwebaze","Nakayiza","Mugisha","Namirembe","Byarugaba","Atim","Okello",
    "Akello","Opio","Achen","Odong","Apiyo","Ongom","Amoding","Kyeyune",
    "Nakkazi","Ddungu","Nansubuga","Ssempijja","Naggayi","Kizigo","Tendo",
    "Nalule","Ssemwogerere","Nakyewa","Mukwaya","Nanyonga","Ssemanda",
]

LAST_NAMES = [
    "Mukasa","Ssebunya","Nanteza","Kawuma","Mubiru","Nakirya","Kibirige",
    "Nsubuga","Nalwanga","Ssenoga","Namugga","Buyinza","Naluwooza","Ssemanda",
    "Nakayenga","Muwanguzi","Naggayi","Ssali","Nakimuli","Matovu","Namirembe",
    "Wasswa","Nabirye","Sserwada","Nakato","Mugisha","Tumusiime","Atuhaire",
    "Byarugaba","Tusiime","Atukunda","Tumwebaze","Ainembabazi","Kemigisha",
    "Kyomuhendo","Mbabazi","Tweheyo","Arinaitwe","Tibyangye","Muhwezi",
    "Kato","Nambi","Ssengendo","Kayondo","Nankinga","Mirembe","Katende",
]

DISTRICTS = [
    "Kampala","Wakiso","Mukono","Jinja","Mbale","Mbarara","Gulu","Lira",
    "Arua","Fort Portal","Masaka","Kabale","Soroti","Tororo","Busia",
    "Hoima","Masindi","Iganga","Bugiri","Buikwe","Lugazi","Entebbe",
]

OCCUPATIONS = [
    "Teacher","Boda Boda Rider","Market Vendor","Carpenter","Mason",
    "Tailor","Farmer","Nurse","Small Business Owner","Driver",
    "Security Guard","Mechanic","Salon Operator","Shopkeeper",
    "Accountant","Cleaner","Hawker","Electrician","Plumber","Cook",
    "Police Officer","Civil Servant","Pastor","Trader",
]

EMPLOYERS = [
    "Kampala City Council","Ministry of Education","Uganda Police Force",
    "Makerere University","Mulago Hospital","Self-employed",
    "Kampala International University","Uganda Revenue Authority",
    "National Water & Sewerage Corporation","MTN Uganda","Airtel Uganda",
    "Stanbic Bank","Centenary Bank","DFCU Bank","Equity Bank Uganda",
    "Total Energies Uganda","Shell Uganda","Boda Boda Association",
    "Wandegeya Market Vendors","Owino Market Traders",
]

PURPOSES = [
    "Buy stock for shop","Pay school fees for children","Clear tax arrears",
    "Buy motorcycle for transport business","Expand salon business",
    "Buy construction materials","Purchase farming inputs",
    "Medical expenses for family","Buy household furniture",
    "Business working capital","Pay land rates","Repair house roof",
    "Purchase second-hand car","Buy sewing machine",
    "Stock up grocery shop","Start food stall","Buy generator",
    "Purchase plot of land","Fund market stall expansion",
    "Buy livestock for farming","Pay rent arrears",
    "Children school requirements","Home renovation",
]

LOAN_TYPES = [
    "Business Loan","School Fees Loan","Tax Clearance Loan",
    "Development Loan","Asset Acquisition Loan",
]

LOAN_STATUSES = (
    ["pending"]    * 15 +
    ["approved"]   * 10 +
    ["active"]     * 80 +
    ["completed"]  * 70 +
    ["defaulted"]  * 15 +
    ["rejected"]   * 10
)

PAYMENT_METHODS = ["Cash","Mobile Money","Bank Transfer","Cheque"]


def rname():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def rphone():
    return f"0{random.choice(['70','71','72','75','76','77','78'])}{random.randint(1000000,9999999)}"

def rnin():
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return f"CM{random.randint(10000000,99999999)}{random.choice(letters)}{random.choice(letters)}"

def rdate(start_year=2023, end_year=2025):
    start = date(start_year, 1, 1)
    end   = date(end_year, 12, 31)
    return start + timedelta(days=random.randint(0, (end-start).days))

def rincome():
    base = random.choice([
        300000,400000,500000,600000,700000,800000,
        1000000,1200000,1500000,2000000,2500000,
    ])
    return base + random.randint(-50000, 50000)


def main():
    print("\n" + "="*58)
    print("  Bingongold Credit — Database Seeder")
    print("="*58)

    from app.database.connection import get_db, create_all_tables
    from app.database.base import Base

    # Create tables
    print("\n  Creating tables if not exist...")
    create_all_tables()

    with get_db() as db:

        # ── Check existing data ────────────────────────────────────────
        from app.core.models.client import Client
        existing = db.query(Client).count()
        if existing >= 50:
            print(f"\n  Database already has {existing} clients.")
            ans = input("  Re-seed anyway? This will ADD new records. (y/n): ").strip().lower()
            if ans != "y":
                print("  Skipped.\n")
                return

        # ── Create staff users ─────────────────────────────────────────
        from app.core.models.user import User
        from app.core.models.user import UserRole
        import bcrypt

        def make_user(full_name, username, password, role):
            exists = db.query(User).filter_by(username=username).first()
            if exists:
                return exists
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            user = User(
                full_name     = full_name,
                username      = username,
                password_hash = hashed,
                role          = UserRole(role),
                is_active     = True,
                created_at    = datetime.utcnow(),
            )
            db.add(user)
            db.flush()
            return user

        print("\n  Creating staff users...")
        admin   = make_user("Tamukedde Jacob",   "admin",   "admin123",   "admin")
        manager = make_user("Sarah Nalwanga",     "manager", "manager123", "manager")
        officer = make_user("John Kato",          "officer", "officer123", "loan_officer")
        db.commit()
        print(f"  Users ready: admin / manager / officer")

        # ── Create 200 clients ─────────────────────────────────────────
        print("\n  Creating 200 clients...")
        from app.core.models.client import Client

        clients = []
        used_nins = set()
        for i in range(200):
            nin = rnin()
            while nin in used_nins:
                nin = rnin()
            used_nins.add(nin)

            income = rincome()
            dob    = date(
                random.randint(1970, 2000),
                random.randint(1, 12),
                random.randint(1, 28),
            )
            c = Client(
                full_name                = rname(),
                nin                      = nin,
                phone_number             = rphone(),
                alt_phone_number         = rphone() if random.random() > 0.6 else None,
                gender                   = random.choice(["Male","Female"]),
                date_of_birth            = dob,
                district                 = random.choice(DISTRICTS),
                village                  = f"{random.choice(['Wandegeya','Kikoni','Kabalagala','Ntinda','Bukoto','Kisaasi','Kansanga','Bugolobi','Muyenga','Luzira'])}",
                physical_address         = f"Plot {random.randint(1,200)}, {random.choice(DISTRICTS)} Road",
                occupation               = random.choice(OCCUPATIONS),
                employer_name            = random.choice(EMPLOYERS),
                monthly_income           = str(income),
                next_of_kin_name         = rname(),
                next_of_kin_phone        = rphone(),
                next_of_kin_relationship = random.choice(["Spouse","Parent","Sibling","Child","Friend"]),
                is_active                = True,
                created_at               = datetime.utcnow() - timedelta(days=random.randint(0,730)),
            )
            db.add(c)
            clients.append(c)

        db.commit()
        for c in clients:
            db.refresh(c)
        print(f"  Created {len(clients)} clients")

        # ── Create 200 loans ───────────────────────────────────────────
        print("\n  Creating 200 loans...")
        from app.core.models.loan import Loan, LoanStatus, LoanType
        from app.core.models.repayment import Repayment, PaymentMethod, RepaymentStatus

        loans = []
        statuses_pool = LOAN_STATUSES.copy()
        random.shuffle(statuses_pool)

        for i, client in enumerate(clients):
            income_val = rincome()
            principal  = random.choice(range(200000, 5050000, 50000))
            duration   = random.choice([3,6,9,12,18,24])
            loan_type  = random.choice(LOAN_TYPES)
            status_str = statuses_pool[i]
            app_date   = rdate(2023, 2025)
            interest   = Decimal(str(principal)) * Decimal("0.10")
            total_rep  = Decimal(str(principal)) + interest
            monthly    = total_rep / duration

            # Generate unique loan number
            year    = app_date.year
            loan_num= f"BG-{year}-{10001+i:05d}"

            loan = Loan(
                loan_number          = loan_num,
                client_id            = client.id,
                created_by_id        = random.choice([admin.id, officer.id]),
                loan_type            = LoanType(loan_type),
                principal_amount     = Decimal(str(principal)),
                interest_rate        = Decimal("10.00"),
                total_interest       = interest,
                total_repayable      = total_rep,
                monthly_installment  = monthly,
                duration_months      = duration,
                purpose              = random.choice(PURPOSES),
                status               = LoanStatus(status_str),
                application_date     = app_date,
                risk_score           = random.choice(["LOW","MEDIUM","HIGH",None,None]),
                created_at           = datetime.combine(app_date, datetime.min.time()),
            )

            # Set dates based on status
            if status_str in ("approved","active","completed","defaulted"):
                loan.approval_date     = app_date + timedelta(days=random.randint(1,5))
                loan.disbursement_date = loan.approval_date
                loan.approved_by_id    = manager.id
                loan.due_date          = loan.disbursement_date + timedelta(days=30*duration)

            if status_str == "rejected":
                loan.rejection_reason = random.choice([
                    "Insufficient income documentation",
                    "Existing loans not cleared",
                    "Poor credit history",
                    "Collateral not sufficient",
                ])

            db.add(loan)
            loans.append((loan, status_str, principal, duration,
                          float(monthly), float(total_rep)))

        db.commit()
        for loan, *_ in loans:
            db.refresh(loan)
        print(f"  Created {len(loans)} loans")

        # ── Create repayments ──────────────────────────────────────────
        print("\n  Creating repayments...")
        repayment_count = 0
        receipt_counter = 1

        for loan, status_str, principal, duration, monthly, total_rep in loans:
            if status_str not in ("active","completed","defaulted"):
                continue
            if not loan.disbursement_date:
                continue

            today = date(2026, 4, 30)
            months_passed = min(
                duration,
                max(1, (today - loan.disbursement_date).days // 30)
            )

            if status_str == "completed":
                payments_to_make = duration
            elif status_str == "defaulted":
                payments_to_make = random.randint(1, max(1, months_passed // 2))
            else:
                payments_to_make = random.randint(
                    max(1, months_passed - 2), months_passed)

            for p in range(min(payments_to_make, duration)):
                pay_date = loan.disbursement_date + timedelta(days=30*(p+1))
                if random.random() < 0.2:
                    pay_date += timedelta(days=random.randint(1,10))

                receipt_num = f"RCP-{2025 if pay_date.year < 2026 else 2026}-{receipt_counter:06d}"
                receipt_counter += 1

                r = Repayment(
                    receipt_number     = receipt_num,
                    loan_id            = loan.id,
                    amount             = Decimal(str(round(monthly, 2))),
                    payment_date       = pay_date,
                    payment_method     = PaymentMethod(random.choice(PAYMENT_METHODS)),
                    status             = RepaymentStatus("confirmed"),
                    transaction_reference = f"TXN{random.randint(100000,999999)}",
                    recorded_by_id     = random.choice([admin.id, officer.id]),
                    created_at         = datetime.combine(pay_date, datetime.min.time()),
                )
                db.add(r)
                repayment_count += 1

        db.commit()
        print(f"  Created {repayment_count} repayment records")

        # ── Final count ────────────────────────────────────────────────
        from app.core.models.loan import Loan as L
        from app.core.models.client import Client as C
        from app.core.models.repayment import Repayment as Rp
        from app.core.models.user import User as U

        counts = {
            "Users":      db.query(U).count(),
            "Clients":    db.query(C).count(),
            "Loans":      db.query(L).count(),
            "Repayments": db.query(Rp).count(),
        }

        print("\n  " + "="*56)
        print("  ✓  Database seeded successfully!")
        print("  " + "-"*56)
        for k, v in counts.items():
            print(f"    {k:<14}: {v}")

        status_counts = {}
        for loan, status_str, *_ in loans:
            status_counts[status_str] = status_counts.get(status_str, 0) + 1
        print("  " + "-"*56)
        print("  Loan Status Breakdown:")
        for s, c in sorted(status_counts.items()):
            print(f"    {s:<14}: {c}")

        print("\n  Login credentials:")
        print("    Admin:   admin   / admin123")
        print("    Manager: manager / manager123")
        print("    Officer: officer / officer123")
        print("  " + "="*56 + "\n")


if __name__ == "__main__":
    main()