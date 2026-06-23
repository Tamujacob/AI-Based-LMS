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
  • Statement identity  → Groq API (LAST-RESORT fallback when regex fails)

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
 
Your job is to help loan officers with:
 
1. LOAN OPERATIONS — questions about existing loans, clients, repayments,
   overdue accounts, portfolio health, and collections at Bingongold Credit.
 
2. STATEMENT ANALYSIS — when a borrower's financial statement has been analysed
   and the results appear in your context, you must answer questions about it:
   - Explain income consistency scores and what they mean for this borrower
   - Assess the risk of giving a specific loan amount to this borrower
   - Compare a requested loan amount against the borrower's income and scenarios
   - Recommend which loan scenario is most appropriate and why
   - Explain any warnings or red flags in the statement
   - Answer hypothetical questions like "what if we give them 1 million for 10 months"
 
3. CREDIT RISK REASONING — given borrower income, expenses, and consistency,
   calculate and explain whether a specific loan is affordable, risky, or unsafe.
 
RULES:
1. Always refer to amounts in Uganda Shillings (UGX).
2. The interest rate at Bingongold Credit is 10% per month on principal.
   Formula: Total Interest     = Principal × 10% × Duration (months)
            Monthly Instalment = (Principal + Total Interest) ÷ Duration (months)
3. If a statement context is provided above, USE IT to answer questions.
   Never say "no statement provided" if statement data is in your context.
4. Only refuse questions completely unrelated to credit, lending, finance,
   or this system (e.g. sports, politics, entertainment).
5. Be concise and practical — loan officers need quick, clear answers.
 
You have access to live database data and statement analysis results provided below."""

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
        callback=None,
    ) -> str:
        """
        Main chatbot entry point.
        Enriches context with live DB data + local model results,
        then sends to Groq (or returns local answer if offline).
 
        History may contain {"role": "system"} entries injected by
        chatbot_screen.py (e.g. statement analysis context). These are
        extracted and merged into the Groq system prompt so the AI
        always has full context for follow-up questions.
        """
        db_context = AICore._build_db_context()
        local_data = AICore._check_local_data_request(message)
 
        full_context = db_context
        if local_data:
            full_context += f"\n\nLOCAL AI DATA:\n{local_data}"
 
        # ── Separate system messages from conversation history ────────────
        # System messages (e.g. statement context) are injected by
        # chatbot_screen.py at position 0 of history. Extract them and
        # append their content to the system prompt so Groq sees them.
        system_context_parts = []
        conversation = []
 
        for h in history:
            if not isinstance(h, dict) or "role" not in h or "content" not in h:
                continue
            if h["role"] == "system":
                system_context_parts.append(h["content"])
            else:
                conversation.append(h)
 
        # Keep last 6 conversation exchanges to stay within token limits
        messages = conversation[-6:]
        messages.append({"role": "user", "content": message})
 
        # Build full system prompt: base + DB context + statement context
        system = AICore.SYSTEM_PROMPT + f"\n\nLIVE DATABASE CONTEXT:\n{full_context}"
        if system_context_parts:
            system += "\n\n" + "\n\n".join(system_context_parts)
        # ── End fix ───────────────────────────────────────────────────────
 
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

    # ── Statement identity extraction (LLM fallback) ─────────────────────────
    #
    # Used by StatementParser as a LAST-RESORT fallback when institution-
    # specific regex extractors fail to find client_name, account_number,
    # nin, or period from a statement's header text. Regex is preferred
    # when it works (fast, free, deterministic) — this only runs when
    # regex comes up empty, so normal MoMo/Equity parsing never triggers
    # an API call.
    #
    # Returns a dict with keys: client_name, account_number, nin,
    # period_from, period_to — each either a string/None as extracted,
    # or None if the LLM could not find it either. Never raises; any
    # failure (no API key, network error, bad JSON) returns an all-None
    # dict so the caller can safely fall back to "Not found in PDF".

    @staticmethod
    def extract_identity_fields(header_text: str) -> dict:
        empty = {
            "client_name":    None,
            "account_number": None,
            "nin":            None,
            "period_from":    None,
            "period_to":      None,
        }
        try:
            from groq import Groq
            from app.config.settings import GROQ_API_KEY
            import json
            import re as _re

            if not GROQ_API_KEY or len(GROQ_API_KEY) < 10:
                return empty

            client = Groq(api_key=GROQ_API_KEY)

            system_prompt = (
                "You extract structured identity fields from Ugandan bank or "
                "mobile money statement headers. You will be given raw text "
                "extracted from the top portion of a statement PDF. "
                "Find these four fields if present:\n"
                "  - client_name: the account holder's full name (a person's "
                "name, NOT a bank name, NOT a label like 'Account Statement')\n"
                "  - account_number: the bank account or mobile wallet number "
                "(digits only, no label text)\n"
                "  - nin: Uganda National ID Number, exactly 14 characters, "
                "format like CM97027102X4CU or CF85123456ABCD. Most statements "
                "do NOT include this — if absent, return null.\n"
                "  - period_from and period_to: the statement period start "
                "and end dates, formatted as DD/MM/YYYY\n\n"
                "Respond with ONLY a JSON object with these exact keys: "
                'client_name, account_number, nin, period_from, period_to. '
                "Use null for any field you cannot find with confidence. "
                "Do not include any other text, explanation, or markdown "
                "formatting — return raw JSON only."
            )

            response = client.chat.completions.create(
                model=AICore.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": header_text[:2000]},
                ],
                max_tokens=300,
                temperature=0.0,   # deterministic extraction, no creativity
            )

            raw = response.choices[0].message.content.strip()
            # Strip markdown code fences if the model added them anyway
            raw = _re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip())

            data = json.loads(raw)
            return {
                "client_name":    data.get("client_name") or None,
                "account_number": data.get("account_number") or None,
                "nin":            data.get("nin") or None,
                "period_from":    data.get("period_from") or None,
                "period_to":      data.get("period_to") or None,
            }

        except Exception:
            # No key, network error, bad JSON, library missing — fail safe
            return empty

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