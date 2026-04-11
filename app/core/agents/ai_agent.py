"""
app/core/agents/ai_agent.py
─────────────────────────────────────────────
Anthropic Claude-powered AI Risk Agent.
Handles risk scoring, portfolio scanning, and overdue alerts.
"""

import anthropic
from datetime import date
from app.config.settings import ANTHROPIC_API_KEY, CLAUDE_MODEL


class AIAgent:

    @staticmethod
    def _call_claude(prompt: str) -> str:
        """Send a prompt to Claude and return the text response."""
        if not ANTHROPIC_API_KEY:
            return ("⚠️ No API key found.\n\n"
                    "Add your ANTHROPIC_API_KEY to the .env file.\n"
                    "Get a free key at: https://console.anthropic.com")
        try:
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            message = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except anthropic.AuthenticationError:
            return "✗ Invalid API key. Check your ANTHROPIC_API_KEY in .env."
        except Exception as e:
            return f"✗ API error: {e}"

    @staticmethod
    def assess_loan_risk(loan, client, repayments, outstanding_balance) -> str:
        """
        Generate a full risk assessment for a single loan.
        Returns a formatted string with risk rating and reasoning.
        """
        repayment_count = len(repayments) if repayments else 0
        total_paid = sum(float(r.amount) for r in repayments) if repayments else 0

        prompt = f"""
You are a credit risk analyst for Bingongold Credit, a microfinance institution in Kampala, Uganda.

Analyse the following loan and provide a risk assessment.

=== LOAN DETAILS ===
Loan Number: {loan.loan_number}
Loan Type: {loan.loan_type.value if loan.loan_type else 'Unknown'}
Principal: UGX {float(loan.principal_amount):,.0f}
Interest Rate: 10% flat
Total Repayable: UGX {float(loan.total_repayable):,.0f if loan.total_repayable else 0:,.0f}
Duration: {loan.duration_months} months
Monthly Installment: UGX {float(loan.monthly_installment):,.0f if loan.monthly_installment else 0:,.0f}
Application Date: {loan.application_date}
Due Date: {loan.due_date or 'Not set'}
Status: {loan.status.value}
Outstanding Balance: UGX {float(outstanding_balance):,.0f}
Purpose: {loan.purpose or 'Not specified'}

=== BORROWER DETAILS ===
Name: {client.full_name if client else 'Unknown'}
Occupation: {client.occupation or 'Not specified'}
Monthly Income: {client.monthly_income or 'Not provided'}
District: {client.district or 'Unknown'}

=== REPAYMENT HISTORY ===
Total Payments Made: {repayment_count}
Total Amount Paid: UGX {total_paid:,.0f}
Days Until/Since Due: {(loan.due_date - date.today()).days if loan.due_date else 'N/A'}

=== YOUR TASK ===
Provide:
1. RISK RATING: LOW / MEDIUM / HIGH (on its own line)
2. REASONING: 3-5 bullet points explaining your rating
3. RECOMMENDATION: What action should the loan officer take?
4. RED FLAGS (if any): Specific concerns to watch

Be direct, practical, and specific to the Ugandan microfinance context.
        """.strip()

        response = AIAgent._call_claude(prompt)
        return f"=== RISK ASSESSMENT: {loan.loan_number} ===\n\n{response}"

    @staticmethod
    def scan_portfolio(loans: list) -> str:
        """
        Scan a list of active loans and return a prioritised alert report.
        """
        if not loans:
            return "No active loans to scan."

        loan_summaries = []
        for loan in loans[:20]:  # Limit to 20 to control token usage
            days_remaining = (loan.due_date - date.today()).days if loan.due_date else None
            overdue = days_remaining is not None and days_remaining < 0
            loan_summaries.append(
                f"- {loan.loan_number}: UGX {float(loan.principal_amount):,.0f}, "
                f"Due: {loan.due_date or 'Not set'}, "
                f"{'OVERDUE by ' + str(abs(days_remaining)) + ' days' if overdue else str(days_remaining) + ' days remaining' if days_remaining is not None else 'No due date'}"
            )

        prompt = f"""
You are a portfolio risk analyst for Bingongold Credit, a microfinance institution in Kampala, Uganda.

Today's date: {date.today()}

Here are the active loans in the portfolio:

{chr(10).join(loan_summaries)}

=== YOUR TASK ===
Provide a portfolio health report with:
1. PORTFOLIO SUMMARY: Overall health in 2 sentences
2. 🔴 URGENT (requires immediate action today)
3. 🟡 WATCH LIST (monitor closely this week)
4. 🟢 HEALTHY (no action needed)
5. RECOMMENDATIONS: Top 3 actions management should take this week

Be concise and practical. Focus on what matters most for a small microfinance team.
        """.strip()

        response = AIAgent._call_claude(prompt)
        return f"=== PORTFOLIO SCAN — {date.today()} ===\nLoans analysed: {len(loans)}\n\n{response}"

    @staticmethod
    def overdue_alert(overdue_loans: list, client_service) -> str:
        """Generate an overdue alert report for all past-due loans."""
        summaries = []
        for loan in overdue_loans:
            days_overdue = (date.today() - loan.due_date).days if loan.due_date else 0
            client = client_service.get_client_by_id(loan.client_id)
            summaries.append(
                f"- {loan.loan_number}: {client.full_name if client else 'Unknown'}, "
                f"UGX {float(loan.principal_amount):,.0f}, "
                f"{days_overdue} days overdue, "
                f"Phone: {client.phone_number if client else 'N/A'}"
            )

        prompt = f"""
You are a collections advisor for Bingongold Credit, Kampala, Uganda.

The following loans are overdue as of {date.today()}:

{chr(10).join(summaries)}

=== YOUR TASK ===
For each overdue loan, provide:
1. Urgency level (CRITICAL / HIGH / MEDIUM)
2. Recommended contact approach (call, visit, final notice)
3. Any patterns you notice across the overdue loans

Then give 3 practical steps management should take immediately.
Keep your response actionable and specific.
        """.strip()

        response = AIAgent._call_claude(prompt)
        return f"=== OVERDUE ALERT — {date.today()} ===\nOverdue loans: {len(overdue_loans)}\n\n{response}"