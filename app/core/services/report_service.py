"""
app/core/services/report_service.py
─────────────────────────────────────────────
PDF (ReportLab) and Word (python-docx) report generation.
All reports saved to ./reports/ folder.
"""

import os
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import cm
from docx import Document
from docx.shared import Pt, RGBColor

REPORTS_DIR = "./reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

GOLD = colors.HexColor("#D4A017")
NAVY = colors.HexColor("#0D1B2A")
LIGHT_GREY = colors.HexColor("#F2F2F2")


class ReportService:

    # ── PDF Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _base_pdf(filename: str):
        path = os.path.join(REPORTS_DIR, filename)
        doc = SimpleDocTemplate(path, pagesize=A4,
                                topMargin=2*cm, bottomMargin=2*cm,
                                leftMargin=2*cm, rightMargin=2*cm)
        styles = getSampleStyleSheet()
        return doc, styles, path

    @staticmethod
    def _header_elements(styles, title: str) -> list:
        title_style = ParagraphStyle("Title", fontSize=18, textColor=NAVY,
                                     fontName="Helvetica-Bold", spaceAfter=4)
        sub_style = ParagraphStyle("Sub", fontSize=10, textColor=colors.grey,
                                   spaceAfter=16)
        return [
            Paragraph("BINGONGOLD CREDIT", title_style),
            Paragraph(f"{title}  —  Generated: {date.today()}", sub_style),
            Spacer(1, 0.3*cm),
        ]

    @staticmethod
    def _table_style(header_rows=1):
        return TableStyle([
            ("BACKGROUND", (0, 0), (-1, header_rows - 1), NAVY),
            ("TEXTCOLOR",  (0, 0), (-1, header_rows - 1), colors.white),
            ("FONTNAME",   (0, 0), (-1, header_rows - 1), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, header_rows), (-1, -1), [LIGHT_GREY, colors.white]),
            ("GRID",       (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])

    # ── Portfolio Summary PDF ──────────────────────────────────────────────

    @staticmethod
    def portfolio_summary_pdf() -> str:
        from app.core.services.loan_service import LoanService
        from app.core.services.client_service import ClientService

        doc, styles, path = ReportService._base_pdf(
            f"portfolio_summary_{date.today()}.pdf")

        elements = ReportService._header_elements(styles, "Portfolio Summary Report")

        counts = LoanService.count_by_status()
        total = LoanService.total_portfolio_value()
        clients = ClientService.count_clients()

        summary_data = [
            ["Metric", "Value"],
            ["Total Registered Clients", str(clients)],
            ["Total Active Portfolio", f"UGX {float(total):,.0f}"],
            ["Pending Loans",   str(counts.get("pending", 0))],
            ["Approved Loans",  str(counts.get("approved", 0))],
            ["Active Loans",    str(counts.get("active", 0))],
            ["Completed Loans", str(counts.get("completed", 0))],
            ["Defaulted Loans", str(counts.get("defaulted", 0))],
        ]
        t = Table(summary_data, colWidths=[10*cm, 7*cm])
        t.setStyle(ReportService._table_style())
        elements.extend([t, Spacer(1, 0.5*cm)])

        # Loan list
        loans = LoanService.get_all_loans()
        from app.core.services.client_service import ClientService as CS
        loan_data = [["Loan No.", "Client", "Type", "Principal (UGX)", "Status", "Due Date"]]
        for loan in loans:
            client = CS.get_client_by_id(loan.client_id)
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

        doc.build(elements)
        return path

    # ── Portfolio Summary Word ─────────────────────────────────────────────

    @staticmethod
    def portfolio_summary_word() -> str:
        from app.core.services.loan_service import LoanService
        from app.core.services.client_service import ClientService

        path = os.path.join(REPORTS_DIR, f"portfolio_summary_{date.today()}.docx")
        doc = Document()

        title = doc.add_heading("BINGONGOLD CREDIT", 0)
        title.runs[0].font.color.rgb = RGBColor(0x0D, 0x1B, 0x2A)

        doc.add_heading("Portfolio Summary Report", 1)
        doc.add_paragraph(f"Generated: {date.today()}")

        counts = LoanService.count_by_status()
        total = LoanService.total_portfolio_value()
        clients = ClientService.count_clients()

        doc.add_heading("Summary Statistics", 2)
        stats = [
            ("Total Clients", str(clients)),
            ("Total Portfolio", f"UGX {float(total):,.0f}"),
            ("Active Loans", str(counts.get("active", 0))),
            ("Completed Loans", str(counts.get("completed", 0))),
            ("Defaulted Loans", str(counts.get("defaulted", 0))),
        ]
        table = doc.add_table(rows=1, cols=2)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        hdr[0].text = "Metric"
        hdr[1].text = "Value"
        for label, val in stats:
            row = table.add_row().cells
            row[0].text = label
            row[1].text = val

        doc.save(path)
        return path

    # ── Overdue Report PDF ─────────────────────────────────────────────────

    @staticmethod
    def overdue_report_pdf() -> str:
        from app.core.services.loan_service import LoanService
        from app.core.services.client_service import ClientService

        doc, styles, path = ReportService._base_pdf(
            f"overdue_loans_{date.today()}.pdf")
        elements = ReportService._header_elements(styles, "Overdue Loans Report")

        overdue = LoanService.get_overdue_loans()
        if not overdue:
            elements.append(Paragraph("No overdue loans as of today.", styles["Normal"]))
        else:
            data = [["Loan No.", "Client", "Phone", "Principal", "Due Date", "Days Overdue"]]
            for loan in overdue:
                client = ClientService.get_client_by_id(loan.client_id)
                days = (date.today() - loan.due_date).days if loan.due_date else 0
                data.append([
                    loan.loan_number,
                    client.full_name if client else "—",
                    client.phone_number if client else "—",
                    f"UGX {float(loan.principal_amount):,.0f}",
                    str(loan.due_date),
                    str(days),
                ])
            t = Table(data, colWidths=[3*cm, 4*cm, 3*cm, 3.5*cm, 3*cm, 2.5*cm])
            t.setStyle(ReportService._table_style())
            elements.append(t)

        doc.build(elements)
        return path

    # ── Repayment History PDF ──────────────────────────────────────────────

    @staticmethod
    def repayment_history_pdf() -> str:
        from app.core.services.repayment_service import RepaymentService
        from app.core.services.loan_service import LoanService

        doc, styles, path = ReportService._base_pdf(
            f"repayment_history_{date.today()}.pdf")
        elements = ReportService._header_elements(styles, "Repayment History Report")

        repayments = RepaymentService.get_all_recent_repayments(limit=200)
        all_loans = {l.id: l for l in LoanService.get_all_loans()}

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
        doc.build(elements)
        return path

    # ── Client Register PDF ────────────────────────────────────────────────

    @staticmethod
    def client_register_pdf() -> str:
        from app.core.services.client_service import ClientService

        doc, styles, path = ReportService._base_pdf(
            f"client_register_{date.today()}.pdf")
        elements = ReportService._header_elements(styles, "Client Register")

        clients = ClientService.get_all_clients()
        data = [["#", "Full Name", "NIN", "Phone", "District", "Occupation"]]
        for i, c in enumerate(clients, 1):
            data.append([
                str(i), c.full_name, c.nin or "—",
                c.phone_number, c.district or "—", c.occupation or "—",
            ])
        t = Table(data, colWidths=[1*cm, 5*cm, 3*cm, 3*cm, 3*cm, 3*cm])
        t.setStyle(ReportService._table_style())
        elements.append(t)
        doc.build(elements)
        return path

    # ── Client Register Word ───────────────────────────────────────────────

    @staticmethod
    def client_register_word() -> str:
        from app.core.services.client_service import ClientService

        path = os.path.join(REPORTS_DIR, f"client_register_{date.today()}.docx")
        doc = Document()
        doc.add_heading("BINGONGOLD CREDIT — Client Register", 0)
        doc.add_paragraph(f"Generated: {date.today()}")

        clients = ClientService.get_all_clients()
        table = doc.add_table(rows=1, cols=5)
        table.style = "Table Grid"
        headers = ["Full Name", "NIN", "Phone", "District", "Occupation"]
        for i, h in enumerate(headers):
            table.rows[0].cells[i].text = h

        for c in clients:
            row = table.add_row().cells
            row[0].text = c.full_name
            row[1].text = c.nin or "—"
            row[2].text = c.phone_number
            row[3].text = c.district or "—"
            row[4].text = c.occupation or "—"

        doc.save(path)
        return path