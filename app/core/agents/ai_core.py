"""
app/core/agents/ai_core.py
──────────────────────────────────────────────────────────────
Unified AI Core — uses Groq API for natural language.

Groq is free at console.groq.com — no credit card needed.
Model: llama-3.3-70b-versatile (fast, accurate, free tier)

Routing:
  • Risk scoring       → LocalScorer       (offline, instant)
  • Statement analysis → StatementParser   (offline)
  • Loan ceiling       → LoanCeilingEngine (offline)
  • Payment planning   → PaymentPlanner    (offline)
  • Credit score       → CreditScorer      (offline)
  • Reminders         → ReminderService   (offline)
  • Natural language   → Groq API          (online, fallback to local)

Add to your .env:
    GROQ_API_KEY=gsk_your_key_here
"""

from datetime import date
from typing import Optional, Callable


class AICore:
    """
    Central AI coordinator.
    All methods are safe to call from background threads.
    """

    GROQ_MODEL = "llama-3.3-70b-versatile"

    # ── System prompt — restricts AI to Bingongold Credit only ───────────────
    SYSTEM_PROMPT = """You are the AI assistant for Bingongold Credit, a microfinance institution in Kampala, Uganda.

Your ONLY job is to help staff with questions about:
- Loan applications, approvals, rejections, and repayments at Bingongold Credit
- Client profiles and borrower financial analysis
- Portfolio health, overdue loans, and collections
- Risk assessments and repayment schedules
- System operations and reports

STRICT RULES:
1. You ONLY answer questions about Bingongold Credit loans and operations.
2. If anyone asks about news, politics, sports, celebrities, history, or ANYTHING not related to loans or this system, respond EXACTLY with:
   "I can only answer questions about Bingongold Credit operations. Please ask me about your loans, clients, or repayments."
3. Never discuss other financial institutions, other AI systems, or general finance theory.
4. Always refer to amounts in Uganda Shillings (UGX).
5. The interest rate at Bingongold Credit is a flat 10%.
6. Be concise and practical — staff are busy and need quick answers.

You have access to live database data provided below. Use it to answer accurately."""

    # ── Portfolio scan ─────────────────────────────────────────────────────────

    @staticmethod
    def scan_portfolio(callback: Callable[[str], None] = None) -> str:
        """Analyse the full active loan portfolio."""
        context = AICore._build_db_context()
        prompt  = (
            "Analyse the current loan portfolio for Bingongold Credit. "
            "For each loan status group, identify: urgent issues, watchlist items, and healthy loans. "
            "Give a top-3 action list for management. Be specific and practical."
        )
        return AICore._call_groq(
            prompt=prompt,
            context=context,
            callback=callback,
            fallback_fn=lambda: AICore._local_portfolio_summary(context),
        )

    # ── Assess single loan ─────────────────────────────────────────────────────

    @staticmethod
    def assess_single_loan(loan_id: int, callback: Callable[[str], None] = None) -> str:
        """Full risk assessment for one loan using local scorer + Groq explanation."""
        from app.core.agents.local_scorer import LocalScorer
        from app.core.services.loan_service import LoanService
        from app.core.services.client_service import ClientService
        from app.core.services.repayment_service import RepaymentService

        loan = LoanService.get_loan_by_id(loan_id)
        if not loan:
            result = f"Loan #{loan_id} not found."
            if callback:
                callback(result)
            return result

        client = ClientService.get_client_by_id(loan.client_id)
        income = 0
        if client and client.monthly_income:
            try:
                income = float(str(client.monthly_income).replace(",", ""))
            except Exception:
                pass

        balance    = RepaymentService.get_outstanding_balance(loan_id)
        repayments = RepaymentService.get_repayments_for_loan(loan_id)

        on_time     = sum(1 for r in repayments
                          if r.payment_date and loan.due_date
                          and r.payment_date <= loan.due_date)
        consistency = on_time / max(len(repayments), 1) if repayments else 1.0

        score = LocalScorer.score(
            principal           = float(loan.principal_amount or 0),
            duration_months     = int(loan.duration_months or 12),
            loan_type           = loan.loan_type.value if loan.loan_type else "Business Loan",
            occupation          = client.occupation or "" if client else "",
            monthly_income      = income,
            payment_consistency = consistency,
        )

        context = (
            f"LOAN ASSESSMENT REQUEST\n"
            f"Loan Number:         {loan.loan_number}\n"
            f"Client:              {client.full_name if client else '—'}\n"
            f"Loan Type:           {loan.loan_type.value if loan.loan_type else '—'}\n"
            f"Principal:           UGX {float(loan.principal_amount or 0):,.0f}\n"
            f"Duration:            {loan.duration_months} months\n"
            f"Status:              {loan.status.value}\n"
            f"Outstanding Balance: UGX {float(balance):,.0f}\n"
            f"Payments Made:       {len(repayments)}\n"
            f"Payment Consistency: {consistency:.0%}\n"
            f"Occupation:          {client.occupation if client else '—'}\n"
            f"Monthly Income:      UGX {income:,.0f}\n"
            f"\nLOCAL AI RISK SCORE:\n{score.as_text()}\n"
        )
        prompt = (
            f"Based on the data above, provide a professional risk assessment for "
            f"loan {loan.loan_number}. Include: "
            "(1) Final risk rating with justification, "
            "(2) Key risk factors, "
            "(3) Recommended actions for the loan officer, "
            "(4) Whether to approve, monitor, or escalate."
        )
        return AICore._call_groq(
            prompt=prompt,
            context=context,
            callback=callback,
            fallback_fn=lambda: score.as_text(),
        )

    # ── Overdue alerts ─────────────────────────────────────────────────────────

    @staticmethod
    def overdue_alerts(callback: Callable[[str], None] = None) -> str:
        """Generate a collections action plan for all overdue loans."""
        from app.core.services.loan_service import LoanService
        from app.core.services.client_service import ClientService

        overdue = LoanService.get_overdue_loans()
        if not overdue:
            result = "No overdue loans found. All active loans are within their due dates."
            if callback:
                callback(result)
            return result

        lines = [f"OVERDUE LOANS REPORT — {date.today()}\n"]
        for loan in overdue:
            client      = ClientService.get_client_by_id(loan.client_id)
            days_overdue = (date.today() - loan.due_date).days if loan.due_date else 0
            lines.append(
                f"• {loan.loan_number} | {client.full_name if client else '—'} | "
                f"UGX {float(loan.principal_amount):,.0f} | "
                f"Due: {loan.due_date} | {days_overdue} days overdue | "
                f"Phone: {client.phone_number if client else '—'}"
            )

        context = "\n".join(lines)
        prompt  = (
            "For each overdue loan above, provide: "
            "(1) Priority level (URGENT / HIGH / MEDIUM), "
            "(2) Recommended collection action, "
            "(3) A short WhatsApp message template to send the borrower. "
            "Sort by urgency."
        )
        return AICore._call_groq(
            prompt=prompt,
            context=context,
            callback=callback,
            fallback_fn=lambda: context,
        )

    # ── Chatbot ────────────────────────────────────────────────────────────────

    @staticmethod
    def chat(
        message: str,
        history: list,
        callback: Callable[[str], None] = None,
    ) -> str:
        """
        Main chatbot entry point.
        Enriches context with live DB data + local model results,
        then sends to Groq (or returns local answer if offline).
        """
        db_context = AICore._build_db_context()
        local_data = AICore._check_local_data_request(message)

        full_context = db_context
        if local_data:
            full_context += f"\n\nLOCAL AI DATA:\n{local_data}"

        # Build message list for Groq
        messages = []
        for h in history[-6:]:   # last 6 exchanges keeps token count low
            if isinstance(h, dict) and "role" in h and "content" in h:
                messages.append(h)
        messages.append({"role": "user", "content": message})

        system = AICore.SYSTEM_PROMPT + f"\n\nLIVE DATABASE CONTEXT:\n{full_context}"

        return AICore._call_groq_messages(
            messages=messages,
            system=system,
            callback=callback,
            fallback_fn=lambda: AICore._local_chat_answer(message, db_context),
        )

    # ── Groq API calls ─────────────────────────────────────────────────────────

    @staticmethod
    def _call_groq(
        prompt: str,
        context: str,
        callback: Optional[Callable],
        fallback_fn: Callable,
    ) -> str:
        """Single-turn Groq call with context injected into system prompt."""
        messages = [{"role": "user", "content": prompt}]
        system   = AICore.SYSTEM_PROMPT + f"\n\nCONTEXT:\n{context}"
        return AICore._call_groq_messages(messages, system, callback, fallback_fn)

    @staticmethod
    def _call_groq_messages(
        messages: list,
        system: str,
        callback: Optional[Callable],
        fallback_fn: Callable,
    ) -> str:
        """
        Core Groq API call.
        Falls back to local function if API key is missing or call fails.
        """
        try:
            from groq import Groq
            from app.config.settings import GROQ_API_KEY

            if not GROQ_API_KEY or len(GROQ_API_KEY) < 10:
                raise ValueError("GROQ_API_KEY not set in .env")

            client   = Groq(api_key=GROQ_API_KEY)
            response = client.chat.completions.create(
                model    = AICore.GROQ_MODEL,
                messages = [{"role": "system", "content": system}] + messages,
                max_tokens  = 1500,
                temperature = 0.3,   # lower = more factual, less creative
            )
            result = response.choices[0].message.content
            if callback:
                callback(result)
            return result

        except ImportError:
            # groq library not installed
            result = (
                "Groq library not installed.\n"
                "Run:  pip install groq\n\n"
                + fallback_fn()
            )
            if callback:
                callback(result)
            return result

        except Exception as e:
            # No key, network error, rate limit, etc. — use local fallback
            result = fallback_fn()
            if callback:
                callback(result)
            return result

    # ── API status check ───────────────────────────────────────────────────────

    @staticmethod
    def check_groq_status() -> str:
        """
        Quick check — returns a status string for the UI badge.
        Does NOT make an API call — just checks config.
        """
        try:
            from app.config.settings import GROQ_API_KEY
            if GROQ_API_KEY and GROQ_API_KEY.startswith("gsk_") and len(GROQ_API_KEY) > 20:
                return "online"
            return "offline"
        except Exception:
            return "offline"

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_db_context() -> str:
        """Pull a live snapshot of key database statistics."""
        try:
            from app.core.services.loan_service import LoanService
            from app.core.services.client_service import ClientService
            from app.core.services.repayment_service import RepaymentService

            counts    = LoanService.count_by_status()
            portfolio = LoanService.total_portfolio_value()
            overdue   = LoanService.get_overdue_loans()
            clients   = ClientService.count_clients()
            recent    = RepaymentService.get_all_recent_repayments(limit=5)

            lines = [
                f"=== BINGONGOLD CREDIT — LIVE DATA ({date.today()}) ===",
                f"Total Clients:      {clients}",
                f"Active Portfolio:   UGX {float(portfolio):,.0f}",
                "Loans by Status:",
            ]
            for status, count in counts.items():
                lines.append(f"  {status.title():<14} {count}")
            lines.append(f"Overdue Loans:      {len(overdue)}")

            if recent:
                lines.append("\nRecent Repayments (last 5):")
                for r in recent:
                    lines.append(
                        f"  {r.receipt_number}  "
                        f"UGX {float(r.amount):,.0f}  {r.payment_date}"
                    )
            if overdue:
                lines.append("\nOverdue Loan Summary:")
                for loan in overdue[:5]:
                    days = (date.today() - loan.due_date).days if loan.due_date else 0
                    lines.append(f"  {loan.loan_number}  {days} days overdue")

            return "\n".join(lines)
        except Exception as e:
            return f"Database context unavailable: {e}"

    @staticmethod
    def _check_local_data_request(message: str) -> str:
        """
        Check if the message needs local model data.
        If so, run the computation and return results as extra context.
        """
        import re
        msg     = message.lower()
        results = []

        # Risk question about a specific loan number
        loan_match = re.search(r"bg-\d{4}-\d+", message, re.I)
        if loan_match and any(w in msg for w in ["risk", "safe", "reliable", "trust"]):
            try:
                from app.core.services.loan_service import LoanService
                from app.core.agents.local_scorer import LocalScorer
                loans = LoanService.get_all_loans()
                loan  = next(
                    (l for l in loans
                     if l.loan_number.upper() == loan_match.group(0).upper()),
                    None,
                )
                if loan:
                    score = LocalScorer.score(
                        principal       = float(loan.principal_amount or 0),
                        duration_months = int(loan.duration_months or 12),
                        loan_type       = loan.loan_type.value if loan.loan_type else "Business Loan",
                    )
                    results.append(
                        f"Risk score for {loan_match.group(0).upper()}:\n{score.as_text()}"
                    )
            except Exception:
                pass

        if any(w in msg for w in ["how much", "ceiling", "maximum", "can borrow", "afford"]):
            results.append(
                "Loan ceiling calculation requires a financial statement upload. "
                "Please use the Statement Analysis section in the Loans screen."
            )

        return "\n".join(results) if results else ""

    @staticmethod
    def _local_portfolio_summary(context: str) -> str:
        return (
            "PORTFOLIO SUMMARY (offline mode — Groq API not available)\n\n"
            + context
            + "\n\n"
            "─────────────────────────────────────────────────────\n"
            "To get AI-written analysis, add your Groq API key to .env:\n"
            "  GROQ_API_KEY=gsk_your_key_here\n"
            "Get a free key at: console.groq.com"
        )

    @staticmethod
    def _local_chat_answer(message: str, context: str) -> str:
        """Simple rule-based fallback when Groq is unavailable."""
        msg = message.lower()

        if any(w in msg for w in ["overdue", "late", "past due"]):
            lines = [l for l in context.split("\n") if "overdue" in l.lower()]
            return ("Overdue loans:\n" + "\n".join(lines)
                    if lines else "No overdue loans found.")

        if any(w in msg for w in ["active", "how many", "count"]):
            lines = [l for l in context.split("\n") if "active" in l.lower()]
            return "\n".join(lines) if lines else context

        if any(w in msg for w in ["portfolio", "total", "value", "balance"]):
            lines = [l for l in context.split("\n")
                     if "portfolio" in l.lower() or "ugx" in l.lower()]
            return "\n".join(lines) if lines else context

        return (
            "Running in offline mode — Groq API key not configured.\n\n"
            "Current database summary:\n\n"
            + context
            + "\n\n"
            "Add GROQ_API_KEY to your .env file to enable full AI responses.\n"
            "Free key at: console.groq.com"
        )