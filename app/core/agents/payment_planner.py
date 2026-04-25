"""
app/core/agents/payment_planner.py
─────────────────────────────────────────────────────────
Phase 3 — Payment Planner

Generates a complete repayment schedule for a borrower.
100% offline — pure Python maths, no API, no model.

Features:
  • Monthly or weekly schedule
  • Flat interest (Bingongold's 10%)
  • Per-instalment table with date, amount, balance
  • Total summary (principal, interest, total)
  • Printable PDF schedule via ReportLab
  • Human-readable text for UI display

Usage:
    plan = PaymentPlanner.create_plan(
        principal        = 1_000_000,
        duration_months  = 12,
        start_date       = date.today(),
    )
    print(plan.as_text())
    PaymentPlanner.save_pdf(plan, "repayment_schedule.pdf", client_name="John Mukasa")
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional
from dateutil.relativedelta import relativedelta
import calendar


@dataclass
class Instalment:
    """One payment in the repayment schedule."""
    number:          int
    due_date:        date
    amount:          Decimal
    principal_part:  Decimal
    interest_part:   Decimal
    balance_after:   Decimal


@dataclass
class RepaymentPlan:
    """Complete repayment plan for a loan."""
    principal:          Decimal
    interest_rate_pct:  Decimal
    total_interest:     Decimal
    total_repayable:    Decimal
    duration_months:    int
    monthly_instalment: Decimal
    start_date:         date
    end_date:           date
    instalments:        List[Instalment] = field(default_factory=list)

    def as_text(self, client_name: str = "") -> str:
        header = [
            "═" * 60,
            "  REPAYMENT SCHEDULE — BINGONGOLD CREDIT",
        ]
        if client_name:
            header.append(f"  Client: {client_name}")
        header += [
            "═" * 60,
            f"  Principal:        UGX {float(self.principal):>15,.0f}",
            f"  Interest (10%):   UGX {float(self.total_interest):>15,.0f}",
            f"  Total Repayable:  UGX {float(self.total_repayable):>15,.0f}",
            f"  Duration:         {self.duration_months} months",
            f"  Monthly Payment:  UGX {float(self.monthly_instalment):>15,.0f}",
            f"  Start Date:       {self.start_date}",
            f"  Final Due Date:   {self.end_date}",
            "─" * 60,
            f"  {'#':<4} {'Due Date':<14} {'Payment':>14} {'Balance':>14}",
            "─" * 60,
        ]
        rows = []
        for inst in self.instalments:
            rows.append(
                f"  {inst.number:<4} {str(inst.due_date):<14} "
                f"UGX {float(inst.amount):>10,.0f}  "
                f"UGX {float(inst.balance_after):>10,.0f}"
            )
        footer = [
            "─" * 60,
            f"  TOTAL PAID: UGX {float(self.total_repayable):,.0f}",
            "═" * 60,
        ]
        return "\n".join(header + rows + footer)


class PaymentPlanner:

    INTEREST_RATE = Decimal("0.10")   # 10% flat

    @classmethod
    def create_plan(
        cls,
        principal: float,
        duration_months: int,
        start_date: date = None,
        interest_rate: float = None,
    ) -> RepaymentPlan:
        """
        Build a full monthly repayment plan.

        Args:
            principal:       Loan principal in UGX
            duration_months: Loan term in months
            start_date:      First payment date (defaults to today + 1 month)
            interest_rate:   Override interest rate (default 10%)
        """
        if start_date is None:
            start_date = date.today()

        rate = Decimal(str(interest_rate if interest_rate is not None else 10))
        rate_decimal = rate / Decimal("100")

        principal_d  = Decimal(str(principal))
        total_interest   = principal_d * rate_decimal
        total_repayable  = principal_d + total_interest
        monthly          = total_repayable / duration_months

        # Round to nearest 100 UGX
        monthly_rounded = Decimal(str(round(float(monthly) / 100) * 100))

        instalments  = []
        balance      = total_repayable
        current_date = start_date

        for i in range(1, duration_months + 1):
            # Add one month
            try:
                current_date = current_date.replace(
                    month=current_date.month % 12 + 1,
                    year=current_date.year + (1 if current_date.month == 12 else 0)
                )
            except ValueError:
                # Handle months with fewer days (e.g. Feb 30)
                next_month = current_date.month % 12 + 1
                next_year  = current_date.year + (1 if current_date.month == 12 else 0)
                last_day   = calendar.monthrange(next_year, next_month)[1]
                current_date = current_date.replace(
                    day=min(current_date.day, last_day),
                    month=next_month, year=next_year)

            # Last payment clears any rounding difference
            if i == duration_months:
                payment = balance
            else:
                payment = monthly_rounded

            interest_part  = (total_interest / duration_months).quantize(Decimal("1"))
            principal_part = payment - interest_part
            balance        = max(Decimal("0"), balance - payment)

            instalments.append(Instalment(
                number         = i,
                due_date       = current_date,
                amount         = payment,
                principal_part = principal_part,
                interest_part  = interest_part,
                balance_after  = balance,
            ))

        end_date = instalments[-1].due_date if instalments else start_date

        return RepaymentPlan(
            principal          = principal_d,
            interest_rate_pct  = rate,
            total_interest     = total_interest,
            total_repayable    = total_repayable,
            duration_months    = duration_months,
            monthly_instalment = monthly_rounded,
            start_date         = start_date,
            end_date           = end_date,
            instalments        = instalments,
        )

    @classmethod
    def save_pdf(
        cls,
        plan: RepaymentPlan,
        output_path: str,
        client_name: str = "",
        loan_number: str = "",
        officer_name: str = "",
    ) -> str:
        """
        Generate a printable PDF repayment schedule.
        Returns the path to the saved PDF.
        """
        import os
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors as rc
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import (SimpleDocTemplate, Paragraph,
                                         Spacer, Table, TableStyle, HRFlowable)
        from reportlab.lib.units import cm

        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        doc = SimpleDocTemplate(output_path, pagesize=A4,
                                topMargin=1.5*cm, bottomMargin=1.5*cm,
                                leftMargin=2*cm, rightMargin=2*cm)

        GREEN  = rc.HexColor("#1A5C1E")
        GOLD   = rc.HexColor("#D4A820")
        LGREY  = rc.HexColor("#F0F7F0")
        WHITE  = rc.white

        h1 = ParagraphStyle("h1", fontSize=18, fontName="Helvetica-Bold",
                             textColor=GREEN, alignment=1, spaceAfter=2)
        h2 = ParagraphStyle("h2", fontSize=10, fontName="Helvetica",
                             textColor=rc.grey, alignment=1, spaceAfter=6)
        body = ParagraphStyle("body", fontSize=10, fontName="Helvetica", spaceAfter=4)
        small = ParagraphStyle("small", fontSize=8, textColor=rc.grey, alignment=1)

        elements = []
        elements.append(Paragraph("BINGONGOLD CREDIT", h1))
        elements.append(Paragraph("together as one  |  Repayment Schedule", h2))
        elements.append(HRFlowable(width="100%", thickness=2, color=GREEN, spaceAfter=8))

        # Summary box
        summary = [
            ["Client:", client_name or "—",       "Loan No.:", loan_number or "—"],
            ["Principal:", f"UGX {float(plan.principal):,.0f}", "Interest:", f"UGX {float(plan.total_interest):,.0f}"],
            ["Total Repayable:", f"UGX {float(plan.total_repayable):,.0f}", "Duration:", f"{plan.duration_months} months"],
            ["Monthly Payment:", f"UGX {float(plan.monthly_instalment):,.0f}", "Final Due:", str(plan.end_date)],
        ]
        sum_t = Table(summary, colWidths=[4*cm, 4*cm, 4*cm, 5*cm])
        sum_t.setStyle(TableStyle([
            ("FONTNAME",   (0,0), (0,-1), "Helvetica-Bold"),
            ("FONTNAME",   (2,0), (2,-1), "Helvetica-Bold"),
            ("FONTSIZE",   (0,0), (-1,-1), 10),
            ("ROWBACKGROUNDS", (0,0), (-1,-1), [LGREY, WHITE]),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
        ]))
        elements.append(sum_t)
        elements.append(Spacer(1, 0.4*cm))

        # Schedule table
        data = [["#", "Due Date", "Payment (UGX)", "Balance After (UGX)"]]
        for inst in plan.instalments:
            data.append([
                str(inst.number),
                str(inst.due_date),
                f"{float(inst.amount):,.0f}",
                f"{float(inst.balance_after):,.0f}",
            ])
        data.append(["", "TOTAL", f"{float(plan.total_repayable):,.0f}", "0"])

        sched_t = Table(data, colWidths=[1.5*cm, 4*cm, 5.5*cm, 6*cm])
        sched_t.setStyle(TableStyle([
            ("BACKGROUND",   (0,0), (-1,0),  GREEN),
            ("TEXTCOLOR",    (0,0), (-1,0),  WHITE),
            ("FONTNAME",     (0,0), (-1,0),  "Helvetica-Bold"),
            ("BACKGROUND",   (0,-1),(-1,-1), LGREY),
            ("FONTNAME",     (0,-1),(-1,-1), "Helvetica-Bold"),
            ("FONTSIZE",     (0,0), (-1,-1), 9),
            ("ROWBACKGROUNDS",(0,1),(-2,-1), [WHITE, LGREY]),
            ("GRID",         (0,0), (-1,-1), 0.25, rc.lightgrey),
            ("TOPPADDING",   (0,0), (-1,-1), 4),
            ("BOTTOMPADDING",(0,0), (-1,-1), 4),
            ("LEFTPADDING",  (0,0), (-1,-1), 5),
        ]))
        elements.append(sched_t)
        elements.append(Spacer(1, 0.8*cm))

        # Signatures
        elements.append(HRFlowable(width="100%", thickness=0.5, color=rc.lightgrey))
        sig = [
            ["Borrower Signature:", "_________________________",
             "Officer Signature:", "_________________________"],
            ["Date:", "_________________________",
             "Date:", "_________________________"],
        ]
        sig_t = Table(sig, colWidths=[4*cm, 5*cm, 4*cm, 5*cm])
        sig_t.setStyle(TableStyle([
            ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
            ("FONTNAME", (2,0), (2,-1), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("TOPPADDING", (0,0), (-1,-1), 8),
        ]))
        elements.append(sig_t)
        elements.append(Spacer(1, 0.3*cm))
        elements.append(HRFlowable(width="100%", thickness=2, color=GREEN))
        elements.append(Paragraph("Bingongold Credit  |  Ham Tower, Wandegeya, Kampala", small))

        doc.build(elements)
        return output_path