"""
app/core/agents/chatbot.py
─────────────────────────────────────────────
Natural language chatbot — gathers live DB context
then asks Claude to answer in plain English.
"""

import anthropic
from datetime import date
from app.config.settings import ANTHROPIC_API_KEY, CLAUDE_MODEL


class Chatbot:

    @staticmethod
    def _get_db_context() -> str:
        """Pull a live snapshot of key stats from the database for context."""
        try:
            from app.core.services.loan_service import LoanService
            from app.core.services.client_service import ClientService
            from app.core.services.repayment_service import RepaymentService

            counts = LoanService.count_by_status()
            total_portfolio = LoanService.total_portfolio_value()
            overdue = LoanService.get_overdue_loans()
            client_count = ClientService.count_clients()
            collected_today = RepaymentService.get_total_collected_today()
            recent = RepaymentService.get_all_recent_repayments(limit=5)

            recent_str = "\n".join([
                f"  - {r.receipt_number}: UGX {float(r.amount):,.0f} on {r.payment_date}"
                for r in recent
            ]) or "  None"

            overdue_str = "\n".join([
                f"  - {l.loan_number}: UGX {float(l.principal_amount):,.0f}, due {l.due_date}"
                for l in overdue[:5]
            ]) or "  None"

            return f"""
=== LIVE DATABASE SNAPSHOT ({date.today()}) ===
Total Clients: {client_count}
Loans by Status:
  - Pending:   {counts.get('pending', 0)}
  - Approved:  {counts.get('approved', 0)}
  - Active:    {counts.get('active', 0)}
  - Completed: {counts.get('completed', 0)}
  - Defaulted: {counts.get('defaulted', 0)}
  - Rejected:  {counts.get('rejected', 0)}

Total Active Portfolio: UGX {float(total_portfolio):,.0f}
Total Collected Today: UGX {float(collected_today):,.0f}
Overdue Loans ({len(overdue)} total):
{overdue_str}

Recent Repayments:
{recent_str}
""".strip()
        except Exception as e:
            return f"Database context unavailable: {e}"

    @staticmethod
    def respond(user_message: str, history: list) -> str:
        """
        Generate a chatbot response using live DB context + conversation history.
        """
        if not ANTHROPIC_API_KEY:
            return ("No API key configured. Add ANTHROPIC_API_KEY to your .env file.\n"
                    "Get a free key at https://console.anthropic.com")

        db_context = Chatbot._get_db_context()

        system_prompt = f"""You are an intelligent assistant for Bingongold Credit, 
a microfinance institution in Kampala, Uganda. You help loan officers and managers 
query and understand their loan portfolio using plain English.

Here is the current state of the database:

{db_context}

Answer the user's questions based on this data. Be concise, friendly, and specific.
If you cannot answer from the data provided, say so clearly.
Always format currency as UGX with comma separators (e.g. UGX 1,500,000).
Do not make up data that isn't in the snapshot above."""

        try:
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

            # Build messages with history
            messages = []
            for h in history[-6:]:  # Keep last 6 exchanges for context
                messages.append(h)
            messages.append({"role": "user", "content": user_message})

            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=512,
                system=system_prompt,
                messages=messages,
            )
            return response.content[0].text

        except anthropic.AuthenticationError:
            return "Invalid API key. Check your ANTHROPIC_API_KEY in .env."
        except Exception as e:
            return f"Error communicating with AI: {e}"