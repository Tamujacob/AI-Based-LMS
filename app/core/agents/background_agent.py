"""
app/core/agents/background_agent.py
══════════════════════════════════════════════════════════════════════════════
Background Agent — Bingongold Credit LMS
Tamukedde Jacob | Bugema University FYP

This module implements two agentic behaviours that run autonomously
without any human trigger:

  1. AUTO RISK FLAG
     Triggered immediately when a new loan is created.
     Runs LocalScorer (offline ML model) and writes the risk score
     (LOW / MEDIUM / HIGH) back to the loan record before it reaches
     the manager's approval queue.
     → Manager always sees a risk-informed loan, no manual assessment needed.

  2. SCHEDULED OVERDUE DETECTION
     Runs every 24 hours in a background daemon thread.
     Finds every active loan whose due_date < today, logs a system
     audit event, and stores a notification so the dashboard and
     agent screen can display an alert.
     → The system notices overdue loans by itself — no human needs to
       click "Check Overdue" to discover them.

Both behaviours are intentionally limited:
  - The agent NEVER approves, rejects, or modifies loan decisions.
  - All actions are written to the audit log for full traceability.
  - Human oversight is preserved at every decision point.

This makes the system agentic (perceive → act autonomously) while
remaining appropriate for a regulated financial environment.

Usage:
    # In app_root.py, after login():
    from app.core.agents.background_agent import BackgroundAgent
    BackgroundAgent.start()

    # In loan_service.py, after create_loan():
    from app.core.agents.background_agent import BackgroundAgent
    BackgroundAgent.flag_loan_risk(loan.id)
"""

import time
import threading
import logging
from datetime import date

logger = logging.getLogger(__name__)


class BackgroundAgent:
    """
    Autonomous background agent for Bingongold Credit LMS.

    All methods are thread-safe and safe to call from any thread.
    The agent runs as daemon threads so it never blocks app shutdown.
    """

    # ── State ──────────────────────────────────────────────────────────────────
    _running          = False
    _thread           = None
    _lock             = threading.Lock()

    # How often the overdue detection loop runs (seconds)
    # 86400 = 24 hours.  Set to 3600 for hourly during development.
    OVERDUE_CHECK_INTERVAL = 86400

    # ══════════════════════════════════════════════════════════════════════════
    # Public API
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    def start(cls):
        """
        Start the background agent after a successful login.
        Safe to call multiple times — only one agent loop runs at a time.
        """
        with cls._lock:
            if cls._running:
                return   # already running

            cls._running = True
            cls._thread  = threading.Thread(
                target=cls._agent_loop,
                name="BackgroundAgent",
                daemon=True,   # dies when main app exits
            )
            cls._thread.start()
            logger.info("[BackgroundAgent] Started.")

    @classmethod
    def stop(cls):
        """Stop the background agent (called on logout)."""
        with cls._lock:
            cls._running = False
            logger.info("[BackgroundAgent] Stopped.")

    @classmethod
    def flag_loan_risk(cls, loan_id: int):
        """
        Auto Risk Flag — called immediately after a new loan is created.
        Runs in a separate thread so it never slows down the UI save action.

        Perception:  reads loan + client data from database
        Reasoning:   runs LocalScorer (RandomForestClassifier)
        Action:      writes risk_score + risk_reasoning back to the loan
        Audit:       logs the autonomous action to audit_logs table
        """
        threading.Thread(
            target=cls._run_risk_flag,
            args=(loan_id,),
            name=f"RiskFlag-{loan_id}",
            daemon=True,
        ).start()

    # ══════════════════════════════════════════════════════════════════════════
    # Feature 1 — Auto Risk Flag
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    def _run_risk_flag(cls, loan_id: int):
        """
        Autonomous risk assessment triggered on loan creation.

        Steps:
          1. Load loan and client from database
          2. Run LocalScorer (offline ML — no internet needed)
          3. Write risk_score and risk_reasoning to loans table
          4. Log autonomous action to audit_logs
        """
        try:
            logger.info(f"[BackgroundAgent] Auto-flagging risk for loan #{loan_id}")

            from app.core.services.loan_service  import LoanService
            from app.core.services.client_service import ClientService
            from app.core.agents.local_scorer     import LocalScorer
            from app.core.services.audit_service  import AuditService, Actions
            from app.database.connection          import get_db
            from app.core.models.loan             import Loan

            # ── Step 1: Load loan ──────────────────────────────────────────
            loan = LoanService.get_loan_by_id(loan_id)
            if not loan:
                logger.warning(f"[BackgroundAgent] Loan #{loan_id} not found.")
                return

            # ── Step 2: Load client for income / occupation ────────────────
            client        = ClientService.get_client_by_id(loan.client_id)
            monthly_income = 0.0
            occupation     = ""

            if client:
                occupation = client.occupation or ""
                if client.monthly_income:
                    try:
                        monthly_income = float(
                            str(client.monthly_income).replace(",", ""))
                    except (ValueError, TypeError):
                        monthly_income = 0.0

            # ── Step 3: Run LocalScorer ────────────────────────────────────
            score = LocalScorer.score(
                principal           = float(loan.principal_amount or 0),
                duration_months     = int(loan.duration_months or 12),
                loan_type           = (loan.loan_type.value
                                       if loan.loan_type
                                       else "Business Loan"),
                occupation          = occupation,
                monthly_income      = monthly_income,
                payment_consistency = 1.0,   # new loan — no history yet
            )

            risk_label    = score.risk_level        # "LOW" / "MEDIUM" / "HIGH"
            risk_reasoning = (
                f"[AUTO-ASSESSED by Background Agent on {date.today()}]\n"
                f"Risk Level:  {risk_label}\n"
                f"Score:       {getattr(score, 'score', 'N/A')}\n\n"
                f"{getattr(score, 'summary', score.as_text())}"
            )

            # ── Step 4: Write back to loan record ──────────────────────────
            with get_db() as db:
                loan_record = db.query(Loan).filter_by(id=loan_id).first()
                if loan_record:
                    loan_record.risk_score     = risk_label
                    loan_record.risk_reasoning = risk_reasoning
                    db.commit()

            # ── Step 5: Audit log ──────────────────────────────────────────
            AuditService.log(
                action      = Actions.LOAN_UPDATED,
                user_id     = None,   # autonomous — no human user
                entity_type = "Loan",
                entity_id   = loan_id,
                description = (
                    f"[AGENT] Auto risk assessment completed for "
                    f"{loan.loan_number}: {risk_label}"
                ),
                new_value   = {"risk_score": risk_label,
                               "assessed_by": "BackgroundAgent",
                               "assessed_on": str(date.today())},
            )

            logger.info(
                f"[BackgroundAgent] Loan #{loan_id} ({loan.loan_number}) "
                f"flagged as {risk_label}."
            )

        except Exception as e:
            logger.exception(
                f"[BackgroundAgent] Risk flag failed for loan #{loan_id}: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # Feature 2 — Scheduled Overdue Detection loop
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    def _agent_loop(cls):
        """
        Main agent loop — runs every OVERDUE_CHECK_INTERVAL seconds.

        Perception:  queries loans table for active loans past due date
        Reasoning:   determines severity (days overdue)
        Action:      writes audit log entry + stores notification record
        Human role:  loan officer sees the notification on dashboard/agent screen
                     and decides what collection action to take

        The loop runs immediately on first start, then sleeps.
        """
        logger.info("[BackgroundAgent] Agent loop started.")

        while cls._running:
            try:
                cls._detect_overdue_loans()
            except Exception as e:
                logger.exception(f"[BackgroundAgent] Overdue detection error: {e}")

            # Sleep in 60-second increments so stop() is responsive
            elapsed = 0
            while cls._running and elapsed < cls.OVERDUE_CHECK_INTERVAL:
                time.sleep(60)
                elapsed += 60

        logger.info("[BackgroundAgent] Agent loop exited.")

    @classmethod
    def _detect_overdue_loans(cls):
        """
        Scheduled overdue detection — the core agentic perception-action cycle.

        Perceives:  all active loans with due_date < today
        Acts:       logs each newly-overdue loan to audit trail
                    stores a notification in the agent_notifications table
                    (creates table if it does not exist)
        """
        try:
            from app.core.services.loan_service   import LoanService
            from app.core.services.client_service  import ClientService
            from app.core.services.audit_service   import AuditService, Actions
            from app.database.connection           import get_db
            from sqlalchemy                        import text

            today    = date.today()
            overdue  = LoanService.get_overdue_loans()

            if not overdue:
                logger.info(
                    f"[BackgroundAgent] Overdue check {today}: "
                    f"no overdue loans found.")
                return

            logger.info(
                f"[BackgroundAgent] Overdue check {today}: "
                f"{len(overdue)} overdue loan(s) detected.")

            # Ensure notifications table exists
            cls._ensure_notifications_table()

            new_alerts = 0

            for loan in overdue:
                days_overdue = (today - loan.due_date).days if loan.due_date else 0

                # Determine severity
                if days_overdue >= 90:
                    severity = "CRITICAL"
                elif days_overdue >= 30:
                    severity = "HIGH"
                elif days_overdue >= 7:
                    severity = "MEDIUM"
                else:
                    severity = "LOW"

                client = ClientService.get_client_by_id(loan.client_id)
                client_name = client.full_name if client else "Unknown"

                # Write notification (skip if already notified today for
                # this loan to avoid duplicate alerts on every loop run)
                with get_db() as db:
                    existing = db.execute(text("""
                        SELECT id FROM agent_notifications
                        WHERE loan_id   = :lid
                          AND notif_date = :today
                          AND notif_type = 'overdue_detected'
                    """), {"lid": loan.id, "today": str(today)}).fetchone()

                    if not existing:
                        db.execute(text("""
                            INSERT INTO agent_notifications
                                (loan_id, notif_type, notif_date,
                                 severity, message, is_read)
                            VALUES
                                (:lid, 'overdue_detected', :today,
                                 :severity, :message, false)
                        """), {
                            "lid":      loan.id,
                            "today":    str(today),
                            "severity": severity,
                            "message":  (
                                f"{loan.loan_number} — {client_name} — "
                                f"{days_overdue} days overdue "
                                f"[{severity}]"
                            ),
                        })
                        db.commit()
                        new_alerts += 1

                        # Audit log for traceability
                        AuditService.log(
                            action      = Actions.LOAN_UPDATED,
                            user_id     = None,
                            entity_type = "Loan",
                            entity_id   = loan.id,
                            description = (
                                f"[AGENT] Overdue detected: "
                                f"{loan.loan_number} | {client_name} | "
                                f"{days_overdue}d overdue | {severity}"
                            ),
                            new_value   = {
                                "detected_by":  "BackgroundAgent",
                                "detected_on":  str(today),
                                "days_overdue": days_overdue,
                                "severity":     severity,
                            },
                        )

            if new_alerts > 0:
                logger.info(
                    f"[BackgroundAgent] {new_alerts} new overdue "
                    f"notification(s) created.")

        except Exception as e:
            logger.exception(
                f"[BackgroundAgent] _detect_overdue_loans failed: {e}")

    @classmethod
    def _ensure_notifications_table(cls):
        """
        Create the agent_notifications table if it does not exist.
        This keeps the feature self-contained — no migration script needed.
        """
        try:
            from app.database.connection import get_db
            from sqlalchemy import text

            with get_db() as db:
                db.execute(text("""
                    CREATE TABLE IF NOT EXISTS agent_notifications (
                        id         SERIAL PRIMARY KEY,
                        loan_id    INTEGER NOT NULL,
                        notif_type VARCHAR(50) NOT NULL,
                        notif_date DATE NOT NULL,
                        severity   VARCHAR(20) NOT NULL DEFAULT 'LOW',
                        message    TEXT NOT NULL,
                        is_read    BOOLEAN NOT NULL DEFAULT false,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                db.commit()
        except Exception as e:
            logger.warning(
                f"[BackgroundAgent] Could not create notifications table: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # Utility — read notifications for UI display
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    def get_unread_notifications(cls, limit: int = 20) -> list:
        """
        Return unread agent notifications for display on the dashboard
        or agent screen.

        Returns a list of dicts:
          {id, loan_id, notif_type, notif_date, severity, message, is_read}
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
                    ORDER  BY created_at DESC
                    LIMIT  :limit
                """), {"limit": limit}).mappings().fetchall()

                return [dict(r) for r in rows]

        except Exception:
            return []

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
            logger.warning(
                f"[BackgroundAgent] mark_read failed: {e}")

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
            logger.warning(
                f"[BackgroundAgent] mark_all_read failed: {e}")