"""
app/core/services/report_service.py
────────────────────────────────────
PDF (ReportLab) and Word (python-docx) report generation.
All reports are saved to ./reports/ and every generation
is audit-logged under Actions.REPORT_GENERATED.
"""

import os
from datetime import date
from decimal import Decimal

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, HRFlowable,
)
from reportlab.lib.units import cm
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.core.services.audit_service import AuditService, Actions

REPORTS_DIR = "./reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

# ── Colour palette ─────────────────────────────────────────────────────────────
GREEN      = colors.HexColor("#1A5C1E")
GOLD       = colors.HexColor("#D4A017")
LIGHT_GREY = colors.HexColor("#F0F7F0")
NAVY       = colors.HexColor("#0D1B2A")


class ReportService:

    # ── PDF helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _base_pdf(filename: str):
        path = os.path.join(REPORTS_DIR, filename)
        doc  = SimpleDocTemplate(
            path, pagesize=A4,
            topMargin=2*cm, bottomMargin=2*cm,
            leftMargin=2*cm, rightMargin=2*cm,
        )
        styles = getSampleStyleSheet()
        return doc, styles, path

    @staticmethod
    def _header_elements(title: str) -> list:
        h1 = ParagraphStyle(
            "H1", fontSize=18, fontName="Helvetica-Bold",
            textColor=GREEN, spaceAfter=4)
        sub = ParagraphStyle(
            "Sub", fontSize=10, textColor=colors.grey, spaceAfter=12)
        return [
            Paragraph("BINGONGOLD CREDIT", h1),
            Paragraph("together as one  |  Ham Tower, 4th Floor, Wandegeya, Kampala", sub),
            Paragraph(f"{title}  —  Generated: {date.today()}", sub),
            HRFlowable(width="100%", thickness=2, color=GREEN, spaceAfter=12),
        ]

    @staticmethod
    def _table_style(header_rows: int = 1) -> TableStyle:
        return TableStyle([
            ("BACKGROUND",     (0, 0), (-1, header_rows - 1), GREEN),
            ("TEXTCOLOR",      (0, 0), (-1, header_rows - 1), colors.white),
            ("FONTNAME",       (0, 0), (-1, header_rows - 1), "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, header_rows), (-1, -1), [LIGHT_GREY, colors.white]),
            ("GRID",           (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",    (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
            ("TOPPADDING",     (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
        ])

    @staticmethod
    def _footer_elements(row_count: int, report_name: str) -> list:
        foot = ParagraphStyle(
            "foot", fontSize=8, textColor=colors.grey, alignment=1, spaceBefore=8)
        return [
            Spacer(1, 0.4*cm),
            HRFlowable(width="100%", thickness=1, color=GREEN),
            Paragraph(
                f"{report_name}  |  Total records: {row_count}  |  "
                f"Bingongold Credit  |  {date.today()}",
                foot,
            ),
        ]

    # ── Word helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _base_word(title: str) -> Document:
        doc = Document()
        # Company header
        h = doc.add_heading("BINGONGOLD CREDIT", 0)
        h.runs[0].font.color.rgb = RGBColor(0x1A, 0x5C, 0x1E)
        h.alignment = WD_ALIGN_PARAGRAPH.CENTER

        sub = doc.add_paragraph("together as one  |  Ham Tower, 4th Floor, Wandegeya, Kampala")
        sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sub.runs[0].font.size = Pt(9)
        sub.runs[0].font.color.rgb = RGBColor(0x88, 0x88, 0x88)

        doc.add_heading(title, 1)
        doc.add_paragraph(f"Generated: {date.today()}")
        doc.add_paragraph()
        return doc

    @staticmethod
    def _word_table_header(table, headers: list):
        row = table.rows[0].cells
        for i, h in enumerate(headers):
            row[i].text = h
            run = row[i].paragraphs[0].runs[0]
            run.bold = True
            run.font.color.rgb = RGBColor(0x1A, 0x5C, 0x1E)

    # ── Portfolio Summary ──────────────────────────────────────────────────────

    @staticmethod
    def portfolio_summary_pdf(generated_by_id: int = None) -> str:
        """Generate a full portfolio summary PDF report."""
        from app.core.services.loan_service import LoanService
        from app.core.services.client_service import ClientService

        doc, _, path = ReportService._base_pdf(
            f"portfolio_summary_{date.today()}.pdf")
        elements = ReportService._header_elements("Portfolio Summary Report")

        counts  = LoanService.count_by_status()
        total   = LoanService.total_portfolio_value()
        clients = ClientService.count_clients()

        # Summary stats table
        summary_data = [
            ["Metric",                "Value"],
            ["Total Registered Clients", str(clients)],
            ["Total Active Portfolio",   f"UGX {float(total):,.0f}"],
            ["Pending Loans",            str(counts.get("pending",   0))],
            ["Approved Loans",           str(counts.get("approved",  0))],
            ["Active Loans",             str(counts.get("active",    0))],
            ["Completed Loans",          str(counts.get("completed", 0))],
            ["Defaulted Loans",          str(counts.get("defaulted", 0))],
        ]
        t = Table(summary_data, colWidths=[10*cm, 7*cm])
        t.setStyle(ReportService._table_style())
        elements.extend([t, Spacer(1, 0.6*cm)])

        # Loan details table
        loans     = LoanService.get_all_loans()
        loan_data = [["Loan No.", "Client", "Type", "Principal (UGX)", "Status", "Due Date"]]
        for loan in loans:
            client = ClientService.get_client_by_id(loan.client_id)
            loan_data.append([
                loan.loan_number,
                client.full_name if client else "—",
                loan.loan_type.value if loan.loan_type else "—",
                f"{float(loan.principal_amount):,.0f}",
                loan.status.value.upper(),
                str(loan.due_date) if loan.due_date else "—",
            ])

        t2 = Table(loan_data, colWidths=[3*cm, 4.5*cm, 3.5*cm, 3*cm, 2.5*cm, 2.5*cm])
        t2.setStyle(ReportService._table_style())
        elements.append(t2)
        elements.extend(ReportService._footer_elements(len(loans), "Portfolio Summary"))

        doc.build(elements)

        AuditService.log(
            action      = Actions.REPORT_GENERATED,
            user_id     = generated_by_id,
            entity_type = "Report",
            description = (
                f"Portfolio Summary PDF generated | "
                f"Loans: {len(loans)} | Active portfolio: UGX {float(total):,.0f}"
            ),
        )
        return path

    @staticmethod
    def portfolio_summary_word(generated_by_id: int = None) -> str:
        """Generate a full portfolio summary Word report."""
        from app.core.services.loan_service import LoanService
        from app.core.services.client_service import ClientService

        path = os.path.join(REPORTS_DIR, f"portfolio_summary_{date.today()}.docx")
        doc  = ReportService._base_word("Portfolio Summary Report")

        counts  = LoanService.count_by_status()
        total   = LoanService.total_portfolio_value()
        clients = ClientService.count_clients()

        doc.add_heading("Summary Statistics", 2)
        stats = [
            ("Total Clients",    str(clients)),
            ("Total Portfolio",  f"UGX {float(total):,.0f}"),
            ("Active Loans",     str(counts.get("active",    0))),
            ("Completed Loans",  str(counts.get("completed", 0))),
            ("Defaulted Loans",  str(counts.get("defaulted", 0))),
        ]
        tbl = doc.add_table(rows=1, cols=2)
        tbl.style = "Table Grid"
        ReportService._word_table_header(tbl, ["Metric", "Value"])
        for label, val in stats:
            row = tbl.add_row().cells
            row[0].text = label
            row[1].text = val

        doc.add_paragraph()
        doc.add_heading("Loan Portfolio Detail", 2)
        loans   = LoanService.get_all_loans()
        headers = ["Loan No.", "Client", "Type", "Principal (UGX)", "Status", "Due Date"]
        tbl2    = doc.add_table(rows=1, cols=len(headers))
        tbl2.style = "Table Grid"
        ReportService._word_table_header(tbl2, headers)
        for loan in loans:
            client = ClientService.get_client_by_id(loan.client_id)
            row    = tbl2.add_row().cells
            row[0].text = loan.loan_number
            row[1].text = client.full_name if client else "—"
            row[2].text = loan.loan_type.value if loan.loan_type else "—"
            row[3].text = f"{float(loan.principal_amount):,.0f}"
            row[4].text = loan.status.value.upper()
            row[5].text = str(loan.due_date) if loan.due_date else "—"

        doc.save(path)

        AuditService.log(
            action      = Actions.REPORT_GENERATED,
            user_id     = generated_by_id,
            entity_type = "Report",
            description = (
                f"Portfolio Summary Word report generated | "
                f"Loans: {len(loans)} | Active portfolio: UGX {float(total):,.0f}"
            ),
        )
        return path

    # ── Overdue Report ─────────────────────────────────────────────────────────

    @staticmethod
    def overdue_report_pdf(generated_by_id: int = None) -> str:
        """Generate a PDF of all overdue loans."""
        from app.core.services.loan_service import LoanService
        from app.core.services.client_service import ClientService

        doc, styles, path = ReportService._base_pdf(
            f"overdue_loans_{date.today()}.pdf")
        elements = ReportService._header_elements("Overdue Loans Report")

        overdue = LoanService.get_overdue_loans()
        if not overdue:
            elements.append(Paragraph(
                "✔  No overdue loans as of today.", styles["Normal"]))
        else:
            data = [["Loan No.", "Client", "Phone", "Principal (UGX)", "Due Date", "Days Overdue"]]
            for loan in overdue:
                client = ClientService.get_client_by_id(loan.client_id)
                days   = (date.today() - loan.due_date).days if loan.due_date else 0
                data.append([
                    loan.loan_number,
                    client.full_name    if client else "—",
                    client.phone_number if client else "—",
                    f"UGX {float(loan.principal_amount):,.0f}",
                    str(loan.due_date),
                    str(days),
                ])
            t = Table(data, colWidths=[3*cm, 4*cm, 3*cm, 3.5*cm, 3*cm, 2.5*cm])
            t.setStyle(ReportService._table_style())
            elements.append(t)
            elements.extend(ReportService._footer_elements(len(overdue), "Overdue Loans"))

        doc.build(elements)

        AuditService.log(
            action      = Actions.REPORT_GENERATED,
            user_id     = generated_by_id,
            entity_type = "Report",
            description = (
                f"Overdue Loans PDF generated | "
                f"Overdue count: {len(overdue)}"
            ),
        )
        return path

    # ── Repayment History ──────────────────────────────────────────────────────

    @staticmethod
    def repayment_history_pdf(generated_by_id: int = None) -> str:
        """Generate a PDF of recent repayment history."""
        from app.core.services.repayment_service import RepaymentService
        from app.core.services.loan_service import LoanService

        doc, _, path = ReportService._base_pdf(
            f"repayment_history_{date.today()}.pdf")
        elements = ReportService._header_elements("Repayment History Report")

        repayments = RepaymentService.get_all_recent_repayments(limit=200)
        all_loans  = {l.id: l for l in LoanService.get_all_loans()}

        data = [["Receipt", "Loan No.", "Amount (UGX)", "Date", "Method"]]
        for r in repayments:
            loan = all_loans.get(r.loan_id)
            data.append([
                r.receipt_number,
                loan.loan_number if loan else "—",
                f"{float(r.amount):,.0f}",
                str(r.payment_date),
                r.payment_method.value if r.payment_method else "—",
            ])

        t = Table(data, colWidths=[4*cm, 3.5*cm, 3.5*cm, 3*cm, 3*cm])
        t.setStyle(ReportService._table_style())
        elements.append(t)
        elements.extend(
            ReportService._footer_elements(len(repayments), "Repayment History"))

        doc.build(elements)

        AuditService.log(
            action      = Actions.REPORT_GENERATED,
            user_id     = generated_by_id,
            entity_type = "Report",
            description = (
                f"Repayment History PDF generated | "
                f"Records: {len(repayments)}"
            ),
        )
        return path

    # ── Client Register ────────────────────────────────────────────────────────

    @staticmethod
    def client_register_pdf(generated_by_id: int = None) -> str:
        """Generate a PDF client register."""
        from app.core.services.client_service import ClientService

        doc, _, path = ReportService._base_pdf(
            f"client_register_{date.today()}.pdf")
        elements = ReportService._header_elements("Client Register")

        clients = ClientService.get_all_clients()
        data    = [["#", "Full Name", "NIN", "Phone", "District", "Occupation"]]
        for i, c in enumerate(clients, 1):
            data.append([
                str(i),
                c.full_name,
                c.nin          or "—",
                c.phone_number,
                getattr(c, "district",   None) or "—",
                getattr(c, "occupation", None) or "—",
            ])

        t = Table(data, colWidths=[1*cm, 5*cm, 3*cm, 3*cm, 3*cm, 3*cm])
        t.setStyle(ReportService._table_style())
        elements.append(t)
        elements.extend(
            ReportService._footer_elements(len(clients), "Client Register"))

        doc.build(elements)

        AuditService.log(
            action      = Actions.REPORT_GENERATED,
            user_id     = generated_by_id,
            entity_type = "Report",
            description = f"Client Register PDF generated | Clients: {len(clients)}",
        )
        return path

    @staticmethod
    def client_register_word(generated_by_id: int = None) -> str:
        """Generate a Word client register."""
        from app.core.services.client_service import ClientService

        path    = os.path.join(REPORTS_DIR, f"client_register_{date.today()}.docx")
        doc     = ReportService._base_word("Client Register")
        clients = ClientService.get_all_clients()

        headers = ["Full Name", "NIN", "Phone", "District", "Occupation"]
        tbl     = doc.add_table(rows=1, cols=len(headers))
        tbl.style = "Table Grid"
        ReportService._word_table_header(tbl, headers)

        for c in clients:
            row    = tbl.add_row().cells
            row[0].text = c.full_name
            row[1].text = c.nin or "—"
            row[2].text = c.phone_number
            row[3].text = getattr(c, "district",   None) or "—"
            row[4].text = getattr(c, "occupation", None) or "—"

        doc.save(path)

        AuditService.log(
            action      = Actions.REPORT_GENERATED,
            user_id     = generated_by_id,
            entity_type = "Report",
            description = f"Client Register Word report generated | Clients: {len(clients)}",
        )
        return path