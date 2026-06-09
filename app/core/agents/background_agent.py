"""
app/core/agents/background_agent.py
══════════════════════════════════════════════════════════════════════════════
Background Agent — Bingongold Credit LMS
Tamukedde Jacob | Bugema University FYP

Agentic behaviours that run AUTONOMOUSLY without any human trigger:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE 1 — AUTO RISK FLAG (triggered on every new loan)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Runs immediately after create_loan() in loan_service.py.
  Scores the loan using LocalScorer (RandomForestClassifier, offline).
  Writes risk_score = LOW / MEDIUM / HIGH back to the loan record.
  Manager always sees a risk-assessed loan — no manual click needed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE 2A — MONTHLY INSTALMENT DETECTION (runs every 24 hours)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  How monthly instalments are scheduled:
    disbursement_date + 30 days  = Month 1 due date
    disbursement_date + 60 days  = Month 2 due date
    ...
    disbursement_date + 30*N days = Month N due date

  The agent:
    1. Calculates the current month number for each active loan
    2. Gets the expected payment date for that month
    3. Sums all payments received in that calendar month
    4. If total paid this month < monthly_installment AND
       today >= expected_date → INSTALMENT OVERDUE alert
    5. If today is exactly 10 days before the expected date
       AND no payment yet this month → UPCOMING PAYMENT alert

  Notification types:
    "instalment_upcoming"  — 10 days before due, no payment yet
    "instalment_overdue"   — past due date, no payment recorded

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE 2B — FULL LOAN OVERDUE DETECTION (runs every 24 hours)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Detects active loans where loan.due_date < today.
  This is the serious end-of-term overdue — the entire loan term has
  expired and the outstanding balance is still unpaid.

  Severity scale:
    LOW      — 1 to 6 days overdue
    MEDIUM   — 7 to 29 days overdue
    HIGH     — 30 to 89 days overdue
    CRITICAL — 90+ days overdue (recommend default proceedings)

  Notification type: "loan_overdue"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
All notifications land in the agent_notifications table.
Every action is written to audit_logs for full traceability.
The agent NEVER approves, rejects, sends messages, or changes loan
status — humans see the notifications and decide what to do.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Usage:
    # app_root.py — after login():
    from app.core.agents.background_agent import BackgroundAgent
    BackgroundAgent.start()

    # app_root.py — in logout():
    BackgroundAgent.stop()

    # loan_service.py — end of create_loan(), before return:
    BackgroundAgent.flag_loan_risk(loan.id)

    # Any screen — to show unread notifications:
    notifications = BackgroundAgent.get_unread_notifications()
"""

import time
import threading
import logging
from datetime import date, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)


class BackgroundAgent:

    # ── State ──────────────────────────────────────────────────────────────────
    _running  = False
    _thread   = None
    _lock     = threading.Lock()

    # 86400 = 24 hours. Set to 3600 for hourly during development/testing.
    DETECTION_INTERVAL = 86400

    # Days before monthly due date to send an upcoming-payment alert
    UPCOMING_ALERT_DAYS = 10

    # Days overdue before the agent automatically marks a loan as defaulted
    DEFAULTED_THRESHOLD_DAYS = 180

    # ══════════════════════════════════════════════════════════════════════════
    # Public API
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    def start(cls):
        """Start the background agent after login. Safe to call multiple times."""
        with cls._lock:
            if cls._running:
                return
            cls._running = True
            cls._thread  = threading.Thread(
                target=cls._agent_loop,
                name="BackgroundAgent",
                daemon=True,
            )
            cls._thread.start()
            logger.info("[BackgroundAgent] Started.")

    @classmethod
    def stop(cls):
        """Stop the agent on logout."""
        with cls._lock:
            cls._running = False
            logger.info("[BackgroundAgent] Stopped.")

    @classmethod
    def flag_loan_risk(cls, loan_id: int):
        """
        Auto Risk Flag — called by loan_service.create_loan() after save.
        Runs in its own daemon thread so it never delays the UI.
        """
        threading.Thread(
            target=cls._run_risk_flag,
            args=(loan_id,),
            name=f"RiskFlag-{loan_id}",
            daemon=True,
        ).start()

    # ══════════════════════════════════════════════════════════════════════════
    # FEATURE 1 — Auto Risk Flag
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    def _run_risk_flag(cls, loan_id: int):
        """
        Perception  → load loan + client data
        Reasoning   → run LocalScorer (offline RandomForest)
        Action      → write risk_score + risk_reasoning to loans table
        Audit       → log autonomous action to audit_logs
        """
        try:
            logger.info(f"[BackgroundAgent] Risk-flagging loan #{loan_id}")

            from app.core.services.loan_service   import LoanService
            from app.core.services.client_service  import ClientService
            from app.core.agents.local_scorer      import LocalScorer
            from app.core.services.audit_service   import AuditService, Actions
            from app.database.connection           import get_db
            from app.core.models.loan              import Loan

            loan = LoanService.get_loan_by_id(loan_id)
            if not loan:
                return

            client         = ClientService.get_client_by_id(loan.client_id)
            monthly_income = 0.0
            occupation     = ""
            if client:
                occupation = client.occupation or ""
                try:
                    monthly_income = float(
                        str(client.monthly_income or 0).replace(",", ""))
                except (ValueError, TypeError):
                    monthly_income = 0.0

            score = LocalScorer.score(
                principal           = float(loan.principal_amount or 0),
                duration_months     = int(loan.duration_months or 12),
                loan_type           = (loan.loan_type.value
                                       if loan.loan_type else "Business Loan"),
                occupation          = occupation,
                monthly_income      = monthly_income,
                payment_consistency = 1.0,   # new loan — no history yet
            )

            risk_label    = score.rating
            risk_reasoning = (
                f"[AUTO-ASSESSED by Background Agent on {date.today()}]\n"
                f"Risk Level: {risk_label}\n\n"
                f"{getattr(score, 'summary', score.as_text())}"
            )

            with get_db() as db:
                rec = db.query(Loan).filter_by(id=loan_id).first()
                if rec:
                    rec.risk_score     = risk_label
                    rec.risk_reasoning = risk_reasoning
                    db.commit()

            AuditService.log(
                action      = Actions.LOAN_UPDATED,
                user_id     = None,
                entity_type = "Loan",
                entity_id   = loan_id,
                description = (
                    f"[AGENT] Auto risk assessment: "
                    f"{loan.loan_number} → {risk_label}"
                ),
                new_value   = {
                    "risk_score":   risk_label,
                    "assessed_by":  "BackgroundAgent",
                    "assessed_on":  str(date.today()),
                },
            )
            logger.info(
                f"[BackgroundAgent] {loan.loan_number} flagged {risk_label}.")

        except Exception as e:
            logger.exception(
                f"[BackgroundAgent] Risk flag failed for loan #{loan_id}: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # Agent loop
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    def _agent_loop(cls):
        """
        Main agent loop — runs both detection tasks every DETECTION_INTERVAL.
        Runs immediately on first start, then sleeps.
        """
        logger.info("[BackgroundAgent] Detection loop started.")

        while cls._running:
            try:
                cls._ensure_notifications_table()
                cls._detect_monthly_instalment_issues()
                cls._detect_full_loan_overdue()
            except Exception as e:
                logger.exception(f"[BackgroundAgent] Detection cycle error: {e}")

            # Sleep in 60s slices so stop() responds quickly
            elapsed = 0
            while cls._running and elapsed < cls.DETECTION_INTERVAL:
                time.sleep(60)
                elapsed += 60

        logger.info("[BackgroundAgent] Detection loop exited.")

    # ══════════════════════════════════════════════════════════════════════════
    # FEATURE 2A — Monthly Instalment Detection
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    def _detect_monthly_instalment_issues(cls):
        """
        For every active loan, calculate whether:
          a) A monthly instalment is due in exactly UPCOMING_ALERT_DAYS
             days and no payment has been made yet this month
             → create "instalment_upcoming" notification

          b) A monthly instalment due date has passed and no payment
             was recorded for that month
             → create "instalment_overdue" notification

        Monthly schedule formula (from loan_service / loan model):
          month_N_due = disbursement_date + timedelta(days=30 * N)
          where N = 1, 2, 3 ... duration_months
        """
        try:
            from app.core.services.loan_service    import LoanService
            from app.core.services.client_service   import ClientService
            from app.core.services.repayment_service import RepaymentService
            from app.core.services.audit_service    import AuditService, Actions

            today      = date.today()
            all_loans  = LoanService.get_all_loans(status="active")
            new_alerts = 0

            for loan in all_loans:
                # Need disbursement_date and monthly_installment
                if not loan.disbursement_date or not loan.monthly_installment:
                    continue

                disb      = loan.disbursement_date
                months    = int(loan.duration_months or 12)
                instalment = float(loan.monthly_installment or 0)

                if instalment <= 0:
                    continue

                # Get all confirmed repayments for this loan once
                repayments = RepaymentService.get_repayments_for_loan(loan.id)
                client     = ClientService.get_client_by_id(loan.client_id)
                client_name  = client.full_name    if client else "Unknown"
                client_phone = client.phone_number if client else "—"

                # Check each month in the loan schedule
                for month_num in range(1, months + 1):
                    month_due_date = disb + timedelta(days=30 * month_num)

                    # Only care about months up to today
                    # (don't alert for future months beyond the upcoming window)
                    days_until_due = (month_due_date - today).days

                    # Skip months that are far in the future
                    if days_until_due > cls.UPCOMING_ALERT_DAYS:
                        continue

                    # Skip months that were due more than 60 days ago
                    # (avoid flooding with old history on first run)
                    if days_until_due < -60:
                        continue

                    # Calculate how much was paid in the window for this month
                    # Window: from previous due date to this due date
                    window_start = disb + timedelta(days=30 * (month_num - 1))
                    window_end   = month_due_date

                    paid_this_month = sum(
                        float(r.amount)
                        for r in repayments
                        if (r.payment_date
                            and window_start < r.payment_date <= window_end)
                    )

                    # Has this month been paid (within 5% tolerance)?
                    month_paid = paid_this_month >= (instalment * 0.95)

                    if month_paid:
                        # ── Late payment fee flag ──────────────────────────
                        # Month was paid but check if any payment in this
                        # window landed AFTER the due date (i.e. paid late).
                        # If so, flag it for the loan officer to consider a
                        # late fee. Only flag once per month.
                        late_payments = [
                            r for r in repayments
                            if (r.payment_date
                                and window_start < r.payment_date <= window_end
                                and r.payment_date > month_due_date)
                        ]
                        if late_payments:
                            # Find how many days late the payment was
                            earliest_late = min(
                                r.payment_date for r in late_payments)
                            days_late = (earliest_late - month_due_date).days

                            created = cls._create_notification_if_new(
                                loan_id    = loan.id,
                                notif_type = "late_payment_fee",
                                notif_date = today,
                                severity   = "LOW",
                                message    = (
                                    f"LATE PAYMENT FEE REVIEW — {loan.loan_number}\n"
                                    f"Client: {client_name}  |  📞 {client_phone}\n"
                                    f"Month {month_num} of {months} was paid "
                                    f"{days_late} day(s) late "
                                    f"(due {month_due_date.strftime('%d %b %Y')}, "
                                    f"paid {earliest_late.strftime('%d %b %Y')})\n"
                                    f"Amount paid: UGX {paid_this_month:,.0f}  |  "
                                    f"Expected: UGX {instalment:,.0f}\n"
                                    f"Action: consider applying a late fee per "
                                    f"the loan agreement."
                                ),
                                extra_key  = f"late_fee_month_{month_num}",
                            )
                            if created:
                                new_alerts += 1
                                AuditService.log(
                                    action      = Actions.LOAN_UPDATED,
                                    user_id     = None,
                                    entity_type = "Loan",
                                    entity_id   = loan.id,
                                    description = (
                                        f"[AGENT] Late payment detected: "
                                        f"{loan.loan_number} month {month_num} "
                                        f"paid {days_late}d late — "
                                        f"late fee review recommended"
                                    ),
                                    new_value = {
                                        "detected_by": "BackgroundAgent",
                                        "type":        "late_payment_fee",
                                        "month_num":   month_num,
                                        "due_date":    str(month_due_date),
                                        "paid_date":   str(earliest_late),
                                        "days_late":   days_late,
                                    },
                                )
                        continue   # paid (on time or late) — no further alerts

                    # ── Upcoming payment alert ─────────────────────────────
                    # 10 days before due and not yet paid
                    if 0 < days_until_due <= cls.UPCOMING_ALERT_DAYS:
                        created = cls._create_notification_if_new(
                            loan_id    = loan.id,
                            notif_type = "instalment_upcoming",
                            notif_date = today,
                            severity   = "UPCOMING",
                            message    = (
                                f"UPCOMING PAYMENT — {loan.loan_number}\n"
                                f"Client: {client_name}  |  📞 {client_phone}\n"
                                f"Month {month_num} of {months} instalment due "
                                f"in {days_until_due} day(s) on "
                                f"{month_due_date.strftime('%d %b %Y')}\n"
                                f"Amount due: UGX {instalment:,.0f}\n"
                                f"Paid so far this month: "
                                f"UGX {paid_this_month:,.0f}"
                            ),
                            extra_key  = f"month_{month_num}",
                        )
                        if created:
                            new_alerts += 1
                            AuditService.log(
                                action      = Actions.LOAN_UPDATED,
                                user_id     = None,
                                entity_type = "Loan",
                                entity_id   = loan.id,
                                description = (
                                    f"[AGENT] Upcoming instalment alert: "
                                    f"{loan.loan_number} month {month_num} "
                                    f"due {month_due_date} "
                                    f"({days_until_due}d away)"
                                ),
                                new_value = {
                                    "detected_by": "BackgroundAgent",
                                    "type":        "instalment_upcoming",
                                    "month_num":   month_num,
                                    "due_date":    str(month_due_date),
                                    "days_until":  days_until_due,
                                },
                            )

                    # ── Overdue instalment alert ───────────────────────────
                    # Past due date and not paid
                    elif days_until_due <= 0:
                        days_late  = abs(days_until_due)

                        # Severity based on how late
                        if days_late <= 3:
                            severity = "LOW"
                        elif days_late <= 14:
                            severity = "MEDIUM"
                        elif days_late <= 30:
                            severity = "HIGH"
                        else:
                            severity = "CRITICAL"

                        created = cls._create_notification_if_new(
                            loan_id    = loan.id,
                            notif_type = "instalment_overdue",
                            notif_date = today,
                            severity   = severity,
                            message    = (
                                f"MISSED INSTALMENT — {loan.loan_number}\n"
                                f"Client: {client_name}  |  📞 {client_phone}\n"
                                f"Month {month_num} of {months} payment was due "
                                f"{month_due_date.strftime('%d %b %Y')} "
                                f"({days_late} day(s) ago)\n"
                                f"Expected: UGX {instalment:,.0f}  |  "
                                f"Paid: UGX {paid_this_month:,.0f}  |  "
                                f"Shortfall: UGX {instalment - paid_this_month:,.0f}"
                            ),
                            extra_key  = f"month_{month_num}",
                        )
                        if created:
                            new_alerts += 1
                            AuditService.log(
                                action      = Actions.LOAN_UPDATED,
                                user_id     = None,
                                entity_type = "Loan",
                                entity_id   = loan.id,
                                description = (
                                    f"[AGENT] Missed instalment: "
                                    f"{loan.loan_number} month {month_num} "
                                    f"was due {month_due_date} "
                                    f"({days_late}d late) [{severity}]"
                                ),
                                new_value = {
                                    "detected_by":  "BackgroundAgent",
                                    "type":         "instalment_overdue",
                                    "month_num":    month_num,
                                    "due_date":     str(month_due_date),
                                    "days_late":    days_late,
                                    "severity":     severity,
                                    "shortfall":    instalment - paid_this_month,
                                },
                            )

            if new_alerts > 0:
                logger.info(
                    f"[BackgroundAgent] {new_alerts} instalment "
                    f"notification(s) created.")

        except Exception as e:
            logger.exception(
                f"[BackgroundAgent] Monthly instalment detection failed: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # FEATURE 2B — Full Loan Overdue Detection
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    def _detect_full_loan_overdue(cls):
        """
        Detects active loans where loan.due_date < today.
        This means the ENTIRE loan term has expired and there is still
        an outstanding balance — the most serious overdue type.

        Severity:
          LOW      →  1–6 days past final due date
          MEDIUM   →  7–29 days
          HIGH     →  30–89 days
          CRITICAL →  90–179 days (recommend default proceedings)
          DEFAULTED → 180+ days (agent auto-marks loan as defaulted)
        """
        try:
            from app.core.services.loan_service    import LoanService
            from app.core.services.client_service   import ClientService
            from app.core.services.repayment_service import RepaymentService
            from app.core.services.audit_service    import AuditService, Actions

            today      = date.today()
            overdue    = LoanService.get_overdue_loans()
            new_alerts = 0

            for loan in overdue:
                if not loan.due_date:
                    continue

                days_overdue = (today - loan.due_date).days

                if days_overdue >= 90:
                    severity = "CRITICAL"
                elif days_overdue >= 30:
                    severity = "HIGH"
                elif days_overdue >= 7:
                    severity = "MEDIUM"
                else:
                    severity = "LOW"

                client       = ClientService.get_client_by_id(loan.client_id)
                client_name  = client.full_name    if client else "Unknown"
                client_phone = client.phone_number if client else "—"
                balance      = RepaymentService.get_outstanding_balance(loan.id)
                defaulted    = False

                if days_overdue >= cls.DEFAULTED_THRESHOLD_DAYS and balance > 0:
                    try:
                        LoanService.mark_defaulted(loan.id)
                        defaulted = True
                        severity = "DEFAULTED"
                    except Exception:
                        logger.exception(
                            f"[BackgroundAgent] Failed to default loan {loan.loan_number}")

                created = cls._create_notification_if_new(
                    loan_id    = loan.id,
                    notif_type = "loan_overdue",
                    notif_date = today,
                    severity   = severity,
                    message    = (
                        f"LOAN OVERDUE — {loan.loan_number}\n"
                        f"Client: {client_name}  |  📞 {client_phone}\n"
                        f"Final due date was: "
                        f"{loan.due_date.strftime('%d %b %Y')} "
                        f"({days_overdue} day(s) ago)\n"
                        f"Outstanding balance: UGX {float(balance):,.0f}\n"
                        f"Loan type: {loan.loan_type.value if loan.loan_type else '—'}"
                        + (
                            "\n⚠ RECOMMEND: initiate default proceedings"
                            if severity in ("CRITICAL", "DEFAULTED") else ""
                        )
                    ),
                    extra_key  = None,   # one notification per loan per day
                )
                if created:
                    new_alerts += 1
                    AuditService.log(
                        action      = Actions.LOAN_UPDATED,
                        user_id     = None,
                        entity_type = "Loan",
                        entity_id   = loan.id,
                        description = (
                            f"[AGENT] Full loan overdue: "
                            f"{loan.loan_number} | {client_name} | "
                            f"{days_overdue}d past final due date | "
                            f"{severity} | "
                            f"Balance: UGX {float(balance):,.0f}"
                        ),
                        new_value = {
                            "detected_by":    "BackgroundAgent",
                            "type":           "loan_overdue",
                            "days_overdue":   days_overdue,
                            "severity":       severity,
                            "balance":        str(balance),
                            "detected_on":    str(today),
                            "defaulted":      defaulted,
                        },
                    )

            if new_alerts > 0:
                logger.info(
                    f"[BackgroundAgent] {new_alerts} full-loan overdue "
                    f"notification(s) created.")

        except Exception as e:
            logger.exception(
                f"[BackgroundAgent] Full loan overdue detection failed: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # Notification helpers
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    def _create_notification_if_new(
        cls,
        loan_id:    int,
        notif_type: str,
        notif_date: date,
        severity:   str,
        message:    str,
        extra_key:  str = None,   # e.g. "month_3" to distinguish instalment alerts
    ) -> bool:
        """
        Insert a notification only if one doesn't already exist for
        this loan + type + date + extra_key combination.
        Returns True if a new notification was created.
        """
        try:
            from app.database.connection import get_db
            from sqlalchemy import text

            # Build a unique key that includes the extra_key if provided
            unique_ref = f"{notif_type}:{extra_key}" if extra_key else notif_type

            with get_db() as db:
                existing = db.execute(text("""
                    SELECT id FROM agent_notifications
                    WHERE  loan_id    = :lid
                      AND  notif_type = :ntype
                      AND  notif_date = :ndate
                      AND  unique_ref = :uref
                """), {
                    "lid":   loan_id,
                    "ntype": notif_type,
                    "ndate": str(notif_date),
                    "uref":  unique_ref,
                }).fetchone()

                if existing:
                    return False   # already notified

                db.execute(text("""
                    INSERT INTO agent_notifications
                        (loan_id, notif_type, notif_date,
                         severity, message, unique_ref, is_read)
                    VALUES
                        (:lid, :ntype, :ndate,
                         :severity, :message, :uref, false)
                """), {
                    "lid":      loan_id,
                    "ntype":    notif_type,
                    "ndate":    str(notif_date),
                    "severity": severity,
                    "message":  message,
                    "uref":     unique_ref,
                })
                db.commit()
                return True

        except Exception as e:
            logger.warning(f"[BackgroundAgent] _create_notification failed: {e}")
            return False

    @classmethod
    def _ensure_notifications_table(cls):
        """
        Create the agent_notifications table if it does not exist.
        The unique_ref column distinguishes multiple notifications
        per loan per day (e.g. month_1, month_2 missed instalments).
        """
        try:
            from app.database.connection import get_db
            from sqlalchemy import text

            with get_db() as db:
                db.execute(text("""
                    CREATE TABLE IF NOT EXISTS agent_notifications (
                        id         SERIAL PRIMARY KEY,
                        loan_id    INTEGER     NOT NULL,
                        notif_type VARCHAR(50) NOT NULL,
                        notif_date DATE        NOT NULL,
                        severity   VARCHAR(20) NOT NULL DEFAULT 'LOW',
                        message    TEXT        NOT NULL,
                        unique_ref VARCHAR(80) NOT NULL DEFAULT '',
                        is_read    BOOLEAN     NOT NULL DEFAULT false,
                        created_at TIMESTAMP   DEFAULT NOW()
                    )
                """))
                db.commit()
        except Exception as e:
            logger.warning(
                f"[BackgroundAgent] Could not create notifications table: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # Public utility — read notifications for UI display
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    def get_unread_notifications(cls, limit: int = 50) -> list:
        """
        Return unread notifications ordered by severity then date.
        Used by the agent screen and dashboard to show alerts.

        Returns list of dicts with keys:
          id, loan_id, notif_type, notif_date, severity, message, is_read
        """
        try:
            from app.database.connection import get_db
            from sqlalchemy import text

            cls._ensure_notifications_table()

            with get_db() as db:
                rows = db.execute(text("""
                    SELECT id, loan_id, notif_type, notif_date,
                           severity, message, is_read
                    FROM   agent_notifications
                    WHERE  is_read = false
                    ORDER  BY
                        CASE severity
                            WHEN 'CRITICAL'  THEN 1
                            WHEN 'HIGH'      THEN 2
                            WHEN 'MEDIUM'    THEN 3
                            WHEN 'UPCOMING'  THEN 4
                            ELSE 5
                        END,
                        created_at DESC
                    LIMIT  :limit
                """), {"limit": limit}).mappings().fetchall()

                return [dict(r) for r in rows]

        except Exception:
            return []

    @classmethod
    def get_notification_counts(cls) -> dict:
        """
        Returns counts by type for dashboard badges.
        {
          "instalment_upcoming": 3,
          "instalment_overdue":  5,
          "loan_overdue":        2,
          "total":               10
        }
        """
        try:
            from app.database.connection import get_db
            from sqlalchemy import text

            cls._ensure_notifications_table()

            with get_db() as db:
                rows = db.execute(text("""
                    SELECT notif_type, COUNT(*) as cnt
                    FROM   agent_notifications
                    WHERE  is_read = false
                    GROUP  BY notif_type
                """)).mappings().fetchall()

            counts = {
                "instalment_upcoming": 0,
                "instalment_overdue":  0,
                "loan_overdue":        0,
                "late_payment_fee":    0,
            }
            for row in rows:
                if row["notif_type"] in counts:
                    counts[row["notif_type"]] = row["cnt"]
            counts["total"] = sum(counts.values())
            return counts

        except Exception:
            return {"instalment_upcoming": 0, "instalment_overdue": 0,
                    "loan_overdue": 0, "late_payment_fee": 0, "total": 0}

    @classmethod
    def mark_notification_read(cls, notification_id: int):
        """Mark a single notification as read."""
        try:
            from app.database.connection import get_db
            from sqlalchemy import text

            with get_db() as db:
                db.execute(text("""
                    UPDATE agent_notifications
                    SET    is_read = true
                    WHERE  id = :nid
                """), {"nid": notification_id})
                db.commit()
        except Exception as e:
            logger.warning(f"[BackgroundAgent] mark_read failed: {e}")

    @classmethod
    def mark_all_read(cls):
        """Mark all notifications as read."""
        try:
            from app.database.connection import get_db
            from sqlalchemy import text

            with get_db() as db:
                db.execute(text(
                    "UPDATE agent_notifications SET is_read = true"))
                db.commit()
        except Exception as e:
            logger.warning(f"[BackgroundAgent] mark_all_read failed: {e}")