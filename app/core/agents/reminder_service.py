"""
app/core/agents/reminder_service.py
──────────────────────────────────────────────────────────────
Additional Feature — Payment Reminder Generator

Generates ready-to-send WhatsApp/SMS reminder messages for
loan officers. Staff copy-paste them into WhatsApp.

No external API needed — pure offline logic.

Reminder triggers:
  • 14 days before due date  → gentle reminder
  •  7 days before due date  → standard reminder
  •  3 days before due date  → urgent reminder
  •  0 days (due today)      → due today
  •  overdue                 → overdue notice

Usage:
    reminders = ReminderService.get_all_due_reminders()
    for r in reminders:
        print(r.message)
        print(r.urgency)
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List


@dataclass
class ReminderItem:
    loan_number:  str
    client_name:  str
    phone:        str
    amount_due:   float
    due_date:     date
    days_until:   int          # negative = overdue
    urgency:      str          # "gentle" / "standard" / "urgent" / "overdue"
    message:      str          # ready to send via WhatsApp/SMS
    whatsapp_url: str          # opens WhatsApp with pre-filled message


class ReminderService:

    @staticmethod
    def get_all_due_reminders() -> List[ReminderItem]:
        """
        Check all active loans and return reminders for those
        due within 14 days or already overdue.
        """
        try:
            from app.core.services.loan_service import LoanService
            from app.core.services.client_service import ClientService
            from app.core.services.repayment_service import RepaymentService

            active_loans = LoanService.get_all_loans(status="active")
            today        = date.today()
            reminders    = []

            for loan in active_loans:
                if not loan.due_date:
                    continue

                days_until = (loan.due_date - today).days
                if days_until > 14:
                    continue   # not due soon

                client    = ClientService.get_client_by_id(loan.client_id)
                balance   = RepaymentService.get_outstanding_balance(loan.id)
                phone     = client.phone_number if client else ""
                name      = client.full_name if client else "Borrower"

                # Monthly instalment or outstanding balance
                try:
                    monthly = float(loan.monthly_installment or balance)
                except Exception:
                    monthly = float(balance)

                item = ReminderService._build_reminder(
                    loan_number = loan.loan_number,
                    client_name = name,
                    phone       = phone,
                    amount_due  = monthly,
                    due_date    = loan.due_date,
                    days_until  = days_until,
                )
                reminders.append(item)

            # Sort: most urgent first
            reminders.sort(key=lambda r: r.days_until)
            return reminders

        except Exception as e:
            return []

    @staticmethod
    def _build_reminder(
        loan_number: str,
        client_name: str,
        phone: str,
        amount_due: float,
        due_date: date,
        days_until: int,
    ) -> ReminderItem:

        if days_until < 0:
            urgency = "overdue"
            days_text = f"{abs(days_until)} days overdue"
            message = (
                f"Dear {client_name},\n\n"
                f"This is a reminder from Bingongold Credit.\n\n"
                f"Your loan payment of UGX {amount_due:,.0f} for loan {loan_number} "
                f"was due on {due_date} and is now {abs(days_until)} days overdue.\n\n"
                f"Please make payment immediately to avoid penalties.\n\n"
                f"Pay via:\n"
                f"• MTN Mobile Money: [Number]\n"
                f"• Airtel Money: [Number]\n"
                f"• Visit our office: Ham Tower, Wandegeya\n\n"
                f"If you have already paid, please send your receipt to this number.\n\n"
                f"Bingongold Credit — together as one"
            )
        elif days_until == 0:
            urgency = "urgent"
            days_text = "due TODAY"
            message = (
                f"Dear {client_name},\n\n"
                f"Reminder from Bingongold Credit: Your loan payment of "
                f"UGX {amount_due:,.0f} (Loan: {loan_number}) is due TODAY — {due_date}.\n\n"
                f"Please make your payment today to keep your loan in good standing.\n\n"
                f"Bingongold Credit — together as one"
            )
        elif days_until <= 3:
            urgency = "urgent"
            days_text = f"due in {days_until} days"
            message = (
                f"Dear {client_name},\n\n"
                f"URGENT: Your loan payment of UGX {amount_due:,.0f} "
                f"(Loan: {loan_number}) is due in {days_until} day(s) on {due_date}.\n\n"
                f"Please arrange payment before the due date.\n\n"
                f"Bingongold Credit — together as one"
            )
        elif days_until <= 7:
            urgency = "standard"
            days_text = f"due in {days_until} days"
            message = (
                f"Dear {client_name},\n\n"
                f"This is a friendly reminder from Bingongold Credit.\n\n"
                f"Your next loan payment of UGX {amount_due:,.0f} "
                f"(Loan: {loan_number}) is due on {due_date} — {days_until} days from today.\n\n"
                f"Please ensure funds are available. Thank you.\n\n"
                f"Bingongold Credit — together as one"
            )
        else:
            urgency = "gentle"
            days_text = f"due in {days_until} days"
            message = (
                f"Dear {client_name},\n\n"
                f"Advance notice from Bingongold Credit: Your loan payment of "
                f"UGX {amount_due:,.0f} (Loan: {loan_number}) is coming up on {due_date}.\n\n"
                f"Bingongold Credit — together as one"
            )

        # Build WhatsApp URL (opens app with pre-filled message)
        import urllib.parse
        clean_phone = phone.replace(" ", "").replace("+", "").replace("-", "")
        if clean_phone.startswith("0"):
            clean_phone = "256" + clean_phone[1:]
        encoded_msg = urllib.parse.quote(message)
        whatsapp_url = f"https://wa.me/{clean_phone}?text={encoded_msg}" if clean_phone else ""

        return ReminderItem(
            loan_number  = loan_number,
            client_name  = client_name,
            phone        = phone,
            amount_due   = amount_due,
            due_date     = due_date,
            days_until   = days_until,
            urgency      = urgency,
            message      = message,
            whatsapp_url = whatsapp_url,
        )

    @staticmethod
    def get_reminder_counts() -> dict:
        """Quick summary for the dashboard notification badge."""
        reminders = ReminderService.get_all_due_reminders()
        return {
            "overdue":  sum(1 for r in reminders if r.urgency == "overdue"),
            "urgent":   sum(1 for r in reminders if r.urgency == "urgent"),
            "standard": sum(1 for r in reminders if r.urgency == "standard"),
            "gentle":   sum(1 for r in reminders if r.urgency == "gentle"),
            "total":    len(reminders),
        }