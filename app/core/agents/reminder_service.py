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

v2 fix:
  - Added outstanding_balance field to ReminderItem so the
    agent screen can display it correctly in the reminder rows.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional


@dataclass
class ReminderItem:
    loan_number:         str
    client_name:         str
    phone:               str
    amount_due:          float
    due_date:            date
    days_until:          int          # negative = overdue
    urgency:             str          # "gentle" / "standard" / "urgent" / "overdue"
    message:             str          # ready to send via WhatsApp/SMS
    whatsapp_url:        str          # opens WhatsApp with pre-filled message
    outstanding_balance: float = 0.0  # actual outstanding balance on the loan
    loan_id:             int   = 0    # loan DB id — used by overdue analysis


class ReminderService:

    @staticmethod
    def get_all_due_reminders() -> List[ReminderItem]:
        """
        Check all active loans and return reminders for:
          - missed monthly instalments
          - upcoming instalments within 14 days
          - full loan overdue loans
        """
        try:
            from app.core.services.loan_service import LoanService
            from app.core.services.client_service import ClientService
            from app.core.services.repayment_service import RepaymentService

            active_loans = LoanService.get_all_loans(status="active")
            today        = date.today()
            reminders    = []

            for loan in active_loans:
                balance = RepaymentService.get_outstanding_balance(loan.id)

                if float(balance) <= 0:
                    continue

                client  = ClientService.get_client_by_id(loan.client_id)
                phone   = client.phone_number if client else ""
                name    = client.full_name if client else "Borrower"

                # Monthly instalment schedule reminders
                if loan.disbursement_date and loan.monthly_installment:
                    reminders.extend(
                        ReminderService._build_monthly_schedule_reminders(
                            loan=loan,
                            client_name=name,
                            phone=phone,
                            outstanding_balance=float(balance),
                            today=today,
                        )
                    )

                # Full loan overdue reminder for completed loan term
                if loan.due_date and loan.due_date < today:
                    reminders.append(
                        ReminderService._build_reminder(
                            loan_id     = loan.id,
                            loan_number = loan.loan_number,
                            client_name = name,
                            phone       = phone,
                            amount_due  = float(balance),
                            due_date    = loan.due_date,
                            days_until  = (loan.due_date - today).days,
                            outstanding_balance = float(balance),
                            custom_message = (
                                f"Dear {name},\n\n"
                                f"Your loan {loan.loan_number} is full overdue. "
                                f"The final due date was {loan.due_date}.\n\n"
                                f"Outstanding balance: UGX {float(balance):,.0f}.\n\n"
                                f"Please make payment immediately or contact us to "
                                f"arrange repayment.\n\n"
                                f"Bingongold Credit — together as one"
                            ),
                            override_urgency="overdue",
                        )
                    )

                # Fallback for loans without schedule but due soon
                elif loan.due_date and not loan.disbursement_date:
                    days_until = (loan.due_date - today).days
                    if days_until <= 14:
                        reminders.append(
                            ReminderService._build_reminder(
                                loan_id     = loan.id,
                                loan_number = loan.loan_number,
                                client_name = name,
                                phone       = phone,
                                amount_due  = float(balance),
                                due_date    = loan.due_date,
                                days_until  = days_until,
                                outstanding_balance = float(balance),
                            )
                        )

            reminders.sort(key=lambda r: (r.days_until, r.urgency))
            return reminders

        except Exception as e:
            return []

    @staticmethod
    def _build_reminder(
        loan_id:             int,
        loan_number:         str,
        client_name:         str,
        phone:               str,
        amount_due:          float,
        due_date:            date,
        days_until:          int,
        outstanding_balance: float = 0.0,
        custom_message:      Optional[str] = None,
        override_urgency:    Optional[str] = None,
    ) -> ReminderItem:

        if custom_message is not None:
            message = custom_message
        elif days_until < 0:
            urgency = "overdue"
            message = (
                f"Dear {client_name},\n\n"
                f"This is a reminder from Bingongold Credit.\n\n"
                f"Your loan payment of UGX {amount_due:,.0f} for loan {loan_number} "
                f"was due on {due_date} and is now {abs(days_until)} days overdue.\n\n"
                f"Outstanding balance: UGX {outstanding_balance:,.0f}\n\n"
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
            message = (
                f"Dear {client_name},\n\n"
                f"Reminder from Bingongold Credit: Your loan payment of "
                f"UGX {amount_due:,.0f} (Loan: {loan_number}) is due TODAY — {due_date}.\n\n"
                f"Please make your payment today to keep your loan in good standing.\n\n"
                f"Bingongold Credit — together as one"
            )
        elif days_until <= 3:
            urgency = "urgent"
            message = (
                f"Dear {client_name},\n\n"
                f"URGENT: Your loan payment of UGX {amount_due:,.0f} "
                f"(Loan: {loan_number}) is due in {days_until} day(s) on {due_date}.\n\n"
                f"Please arrange payment before the due date.\n\n"
                f"Bingongold Credit — together as one"
            )
        elif days_until <= 7:
            urgency = "standard"
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
            message = (
                f"Dear {client_name},\n\n"
                f"Advance notice from Bingongold Credit: Your loan payment of "
                f"UGX {amount_due:,.0f} (Loan: {loan_number}) is coming up on {due_date}.\n\n"
                f"Bingongold Credit — together as one"
            )

        if override_urgency is not None:
            urgency = override_urgency
        elif custom_message is not None:
            urgency = ReminderService._classify_urgency(days_until)

        # WhatsApp URL
        import urllib.parse
        clean_phone = phone.replace(" ", "").replace("+", "").replace("-", "")
        if clean_phone.startswith("0"):
            clean_phone = "256" + clean_phone[1:]
        encoded_msg  = urllib.parse.quote(message)
        whatsapp_url = (
            f"https://wa.me/{clean_phone}?text={encoded_msg}"
            if clean_phone else ""
        )

        return ReminderItem(
            loan_id              = loan_id,
            loan_number          = loan_number,
            client_name          = client_name,
            phone                = phone,
            amount_due           = amount_due,
            due_date             = due_date,
            days_until           = days_until,
            urgency              = urgency,
            message              = message,
            whatsapp_url         = whatsapp_url,
            outstanding_balance  = outstanding_balance,
        )

    @staticmethod
    def _classify_urgency(days_until: int) -> str:
        if days_until < 0:
            return "overdue"
        if days_until == 0:
            return "urgent"
        if days_until <= 3:
            return "urgent"
        if days_until <= 7:
            return "standard"
        return "gentle"

    @staticmethod
    def _build_monthly_schedule_reminders(
        loan,
        client_name: str,
        phone: str,
        outstanding_balance: float,
        today: date,
    ) -> List[ReminderItem]:
        reminders = []
        try:
            from app.core.services.repayment_service import RepaymentService

            monthly_amount = float(loan.monthly_installment or 0)
            if monthly_amount <= 0:
                return reminders

            repayments = RepaymentService.get_repayments_for_loan(loan.id)
            months = int(loan.duration_months or 0)
            if not loan.disbursement_date or months <= 0:
                return reminders

            for month_num in range(1, months + 1):
                month_due_date = loan.disbursement_date + timedelta(days=30 * month_num)
                days_until = (month_due_date - today).days

                if days_until > 14:
                    continue
                if days_until < -60:
                    continue

                window_start = loan.disbursement_date + timedelta(days=30 * (month_num - 1))
                window_end = month_due_date
                paid_this_month = sum(
                    float(r.amount)
                    for r in repayments
                    if r.payment_date and window_start < r.payment_date <= window_end
                )
                month_paid = paid_this_month >= (monthly_amount * 0.95)
                if month_paid:
                    continue

                if month_due_date <= today:
                    days_late = abs(days_until)
                    urgency = "overdue"
                    message = (
                        f"Dear {client_name},\n\n"
                        f"Your instalment for loan {loan.loan_number} "
                        f"(month {month_num} of {months}) was due on {month_due_date} "
                        f"and is now {days_late} day(s) late.\n\n"
                        f"Amount due: UGX {monthly_amount:,.0f}\n"
                        f"Outstanding balance: UGX {outstanding_balance:,.0f}\n\n"
                        f"Please pay immediately to avoid further penalties.\n\n"
                        f"Bingongold Credit — together as one"
                    )
                else:
                    urgency = ReminderService._classify_urgency(days_until)
                    message = (
                        f"Dear {client_name},\n\n"
                        f"Your instalment for loan {loan.loan_number} "
                        f"(month {month_num} of {months}) is due in {days_until} day(s) "
                        f"on {month_due_date}.\n\n"
                        f"Amount due: UGX {monthly_amount:,.0f}\n"
                        f"Outstanding balance: UGX {outstanding_balance:,.0f}\n\n"
                        f"Please make payment on time.\n\n"
                        f"Bingongold Credit — together as one"
                    )

                reminders.append(
                    ReminderService._build_reminder(
                        loan_id     = loan.id,
                        loan_number = loan.loan_number,
                        client_name = client_name,
                        phone       = phone,
                        amount_due  = monthly_amount,
                        due_date    = month_due_date,
                        days_until  = days_until,
                        outstanding_balance = outstanding_balance,
                        custom_message = message,
                        override_urgency = urgency,
                    )
                )

        except Exception:
            pass

        return reminders

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