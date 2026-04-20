"""
app/ui/screens/reports_screen.py
Updated: loan agreement with signature lines added
"""

import threading
import customtkinter as ctk
from app.ui.styles.theme import COLORS, FONTS, primary_button_style
from app.ui.components.sidebar import Sidebar


class ReportsScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master = master
        self.current_user = master.current_user
        self._build()

    def _navigate(self, screen):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        Sidebar(self, "reports", self._navigate, self.current_user).grid(
            row=0, column=0, sticky="nsew")

        main = ctk.CTkScrollableFrame(
            self, fg_color=COLORS["bg_primary"],
            scrollbar_button_color=COLORS["border"])
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)

        # Header
        ctk.CTkFrame(main, fg_color=COLORS["accent_green"],
                     height=4, corner_radius=0).grid(
            row=0, column=0, sticky="ew")
        ctk.CTkLabel(main, text="Reports", font=FONTS["title"],
                     text_color=COLORS["accent_green_dark"]).grid(
            row=1, column=0, sticky="w", padx=32, pady=(20, 4))
        ctk.CTkLabel(main,
                     text="Generate and print reports, agreements, and receipts.",
                     font=FONTS["body"],
                     text_color=COLORS["text_secondary"]).grid(
            row=2, column=0, sticky="w", padx=32, pady=(0, 8))

        self.status_label = ctk.CTkLabel(main, text="",
                                          font=FONTS["body_small"],
                                          text_color=COLORS["accent_green"])
        self.status_label.grid(row=3, column=0, sticky="w", padx=32, pady=(0, 16))

        reports = [
            {
                "icon":  "P",
                "title": "Portfolio Summary",
                "desc":  "Full overview — all loans, counts by status, total value.",
                "pdf":   self._gen_portfolio_pdf,
                "word":  self._gen_portfolio_word,
            },
            {
                "icon":  "L",
                "title": "Loan Agreement (with Signatures)",
                "desc":  "Official loan agreement for a specific loan. Includes borrower and officer signature lines. Enter loan number below.",
                "pdf":   self._gen_loan_agreement,
                "word":  None,
                "extra": "loan_number",
            },
            {
                "icon":  "!",
                "title": "Overdue Loans Report",
                "desc":  "All loans past their due date with client contact details.",
                "pdf":   self._gen_overdue_pdf,
                "word":  None,
            },
            {
                "icon":  "R",
                "title": "Repayment History",
                "desc":  "All recorded payments — useful for auditing.",
                "pdf":   self._gen_repayments_pdf,
                "word":  None,
            },
            {
                "icon":  "C",
                "title": "Client Register",
                "desc":  "Full list of registered clients with contact and NIN details.",
                "pdf":   self._gen_clients_pdf,
                "word":  self._gen_clients_word,
            },
        ]

        for i, r in enumerate(reports):
            self._build_report_card(main, r, row=4+i)

    def _build_report_card(self, parent, report: dict, row: int):
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"],
                             corner_radius=10, border_width=1,
                             border_color=COLORS["border"])
        card.grid(row=row, column=0, sticky="ew", padx=32, pady=8)
        card.columnconfigure(1, weight=1)

        # Icon badge
        badge = ctk.CTkFrame(card, fg_color=COLORS["accent_green"],
                              width=40, height=40, corner_radius=20)
        badge.grid(row=0, column=0, rowspan=2, padx=20, pady=20, sticky="n")
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text=report["icon"],
                     font=("Helvetica", 14, "bold"),
                     text_color="#FFFFFF").pack(expand=True)

        ctk.CTkLabel(card, text=report["title"],
                     font=FONTS["subheading"],
                     text_color=COLORS["accent_green_dark"],
                     anchor="w").grid(row=0, column=1, sticky="w",
                                      padx=(0, 16), pady=(18, 2))
        ctk.CTkLabel(card, text=report["desc"],
                     font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"],
                     anchor="w", wraplength=520).grid(
            row=1, column=1, sticky="w", padx=(0, 16), pady=(0, 12))

        # Extra input if needed (loan number for agreement)
        if report.get("extra") == "loan_number":
            input_row = ctk.CTkFrame(card, fg_color="transparent")
            input_row.grid(row=2, column=1, sticky="w", pady=(0, 12))
            ctk.CTkLabel(input_row, text="Loan Number:",
                         font=FONTS["body_small"],
                         text_color=COLORS["text_secondary"]).pack(side="left")
            self.agreement_loan_var = ctk.StringVar()
            ctk.CTkEntry(input_row, textvariable=self.agreement_loan_var,
                         placeholder_text="e.g. BG-2025-12345",
                         width=200, height=36,
                         fg_color=COLORS["bg_input"],
                         border_color=COLORS["border"],
                         text_color=COLORS["text_primary"],
                         font=FONTS["body_small"],
                         corner_radius=8,
                         border_width=1).pack(side="left", padx=(8, 0))

        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.grid(row=0, column=2, rowspan=3, padx=16, pady=16, sticky="e")

        ctk.CTkButton(btn_frame, text="PDF", width=90, height=36,
                      fg_color=COLORS["danger"], hover_color="#A93226",
                      text_color="white", font=FONTS["button"],
                      corner_radius=8,
                      command=report["pdf"]).pack(pady=4)

        if report.get("word"):
            ctk.CTkButton(btn_frame, text="Word", width=90, height=36,
                          fg_color=COLORS["info"], hover_color="#1A5276",
                          text_color="white", font=FONTS["button"],
                          corner_radius=8,
                          command=report["word"]).pack(pady=4)

    def _set_status(self, msg: str, color: str = None):
        self.after(0, lambda: self.status_label.configure(
            text=msg, text_color=color or COLORS["accent_green"]))

    # ── Report generators ─────────────────────────────────────────────────

    def _gen_portfolio_pdf(self):
        threading.Thread(target=lambda: self._run_and_open(
            "report_service", "portfolio_summary_pdf"), daemon=True).start()

    def _gen_portfolio_word(self):
        threading.Thread(target=lambda: self._run_and_open(
            "report_service", "portfolio_summary_word"), daemon=True).start()

    def _gen_overdue_pdf(self):
        threading.Thread(target=lambda: self._run_and_open(
            "report_service", "overdue_report_pdf"), daemon=True).start()

    def _gen_repayments_pdf(self):
        threading.Thread(target=lambda: self._run_and_open(
            "report_service", "repayment_history_pdf"), daemon=True).start()

    def _gen_clients_pdf(self):
        threading.Thread(target=lambda: self._run_and_open(
            "report_service", "client_register_pdf"), daemon=True).start()

    def _gen_clients_word(self):
        threading.Thread(target=lambda: self._run_and_open(
            "report_service", "client_register_word"), daemon=True).start()

    def _run_and_open(self, module_name: str, method_name: str):
        try:
            from app.core.services import report_service as rs
            path = getattr(rs.ReportService, method_name)()
            self._set_status(f"Saved: {path}")
            import subprocess
            subprocess.Popen(["xdg-open", path])
        except Exception as e:
            self._set_status(f"Error: {e}", COLORS["danger"])

    def _gen_loan_agreement(self):
        loan_number = self.agreement_loan_var.get().strip()
        if not loan_number:
            self._set_status("Please enter a loan number first.", COLORS["danger"])
            return
        threading.Thread(target=self._generate_agreement_pdf,
                         args=(loan_number,), daemon=True).start()

    def _generate_agreement_pdf(self, loan_number: str):
        try:
            import os
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors as rc
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.platypus import (SimpleDocTemplate, Paragraph,
                                             Spacer, Table, TableStyle,
                                             HRFlowable)
            from reportlab.lib.units import cm
            from datetime import datetime
            from app.core.services.loan_service import LoanService
            from app.core.services.client_service import ClientService

            # Find loan
            loans = LoanService.get_all_loans()
            loan  = next((l for l in loans if l.loan_number == loan_number), None)
            if not loan:
                self._set_status(f"Loan '{loan_number}' not found.", rc.red)
                return

            client = ClientService.get_client_by_id(loan.client_id)

            os.makedirs("./reports", exist_ok=True)
            filename = f"./reports/agreement_{loan_number}.pdf"

            doc = SimpleDocTemplate(filename, pagesize=A4,
                                    topMargin=2*cm, bottomMargin=2*cm,
                                    leftMargin=2.5*cm, rightMargin=2.5*cm)

            GREEN = rc.HexColor("#1A5C1E")
            GOLD  = rc.HexColor("#D4A820")
            LGREY = rc.HexColor("#F0F7F0")

            h1  = ParagraphStyle("h1",  fontSize=20, fontName="Helvetica-Bold",
                                  textColor=GREEN, alignment=1, spaceAfter=2)
            h2  = ParagraphStyle("h2",  fontSize=10, fontName="Helvetica",
                                  textColor=rc.grey, alignment=1, spaceAfter=6)
            sec = ParagraphStyle("sec", fontSize=12, fontName="Helvetica-Bold",
                                  textColor=GREEN, spaceBefore=16, spaceAfter=6)
            body= ParagraphStyle("body",fontSize=10, fontName="Helvetica",
                                  leading=16, spaceAfter=6)
            lbl = ParagraphStyle("lbl", fontSize=9,  fontName="Helvetica",
                                  textColor=rc.grey)
            bold= ParagraphStyle("bold",fontSize=10, fontName="Helvetica-Bold")
            small= ParagraphStyle("small",fontSize=9, fontName="Helvetica",
                                   textColor=rc.grey, alignment=1)

            elements = []

            # ── Letterhead ──
            elements.append(Paragraph("BINGONGOLD CREDIT", h1))
            elements.append(Paragraph("together as one", h2))
            elements.append(Paragraph(
                "Ham Tower, 4th Floor, Wandegeya, Kampala, Uganda", h2))
            elements.append(HRFlowable(width="100%", thickness=3,
                                        color=GREEN, spaceAfter=4))
            elements.append(HRFlowable(width="100%", thickness=1,
                                        color=GOLD, spaceAfter=12))

            # Title
            title_s = ParagraphStyle("title", fontSize=16,
                                      fontName="Helvetica-Bold",
                                      textColor=GREEN, alignment=1, spaceAfter=4)
            elements.append(Paragraph("LOAN AGREEMENT", title_s))
            elements.append(Paragraph(f"Reference: {loan_number}", h2))
            elements.append(HRFlowable(width="100%", thickness=1,
                                        color=GOLD, spaceAfter=16))

            # ── Borrower details ──
            elements.append(Paragraph("1. BORROWER DETAILS", sec))
            bdata = [
                ["Full Name",    client.full_name if client else "—"],
                ["NIN",          client.nin or "—" if client else "—"],
                ["Phone",        client.phone_number if client else "—"],
                ["Address",      (client.district or "—") if client else "—"],
                ["Occupation",   client.occupation or "—" if client else "—"],
            ]
            bt = Table(bdata, colWidths=[5*cm, 11*cm])
            bt.setStyle(TableStyle([
                ("FONTNAME",   (0,0), (0,-1), "Helvetica-Bold"),
                ("FONTSIZE",   (0,0), (-1,-1), 10),
                ("ROWBACKGROUNDS",(0,0),(-1,-1),[LGREY, rc.white]),
                ("TOPPADDING", (0,0),(-1,-1), 5),
                ("BOTTOMPADDING",(0,0),(-1,-1),5),
                ("LEFTPADDING",(0,0),(-1,-1),6),
            ]))
            elements.append(bt)

            # ── Loan details ──
            elements.append(Paragraph("2. LOAN DETAILS", sec))
            ldata = [
                ["Loan Number",       loan.loan_number],
                ["Loan Type",         loan.loan_type.value if loan.loan_type else "—"],
                ["Principal Amount",  f"UGX {float(loan.principal_amount):,.0f}"],
                ["Interest Rate",     f"{float(loan.interest_rate)}% flat"],
                ["Total Interest",    f"UGX {float(loan.total_interest):,.0f}" if loan.total_interest else "—"],
                ["Total Repayable",   f"UGX {float(loan.total_repayable):,.0f}" if loan.total_repayable else "—"],
                ["Duration",          f"{loan.duration_months} months"],
                ["Monthly Instalment",f"UGX {float(loan.monthly_installment):,.0f}" if loan.monthly_installment else "—"],
                ["Application Date",  str(loan.application_date)],
                ["Disbursement Date", str(loan.disbursement_date) if loan.disbursement_date else "—"],
                ["Due Date",          str(loan.due_date) if loan.due_date else "—"],
                ["Purpose",           loan.purpose or "—"],
            ]
            lt = Table(ldata, colWidths=[5*cm, 11*cm])
            lt.setStyle(bt.getStyle())
            elements.append(lt)

            # ── Terms ──
            elements.append(Paragraph("3. TERMS AND CONDITIONS", sec))
            terms = [
                "The borrower agrees to repay the total loan amount plus interest as stated above.",
                "Repayments shall be made in equal monthly instalments on or before the agreed due date each month.",
                "Late payments will attract a penalty as determined by Bingongold Credit management.",
                "The borrower authorises Bingongold Credit to recover the outstanding balance from any collateral provided in the event of default.",
                "This agreement is governed by the laws of the Republic of Uganda.",
                "Any disputes arising from this agreement shall be resolved through mutual dialogue and, if necessary, through competent courts in Uganda.",
            ]
            for i, term in enumerate(terms, 1):
                elements.append(Paragraph(
                    f"{i}. {term}", body))

            elements.append(Spacer(1, 1*cm))

            # ── Signature section ──
            elements.append(HRFlowable(width="100%", thickness=0.5,
                                        color=rc.lightgrey, spaceAfter=8))
            elements.append(Paragraph("4. SIGNATURES", sec))
            elements.append(Paragraph(
                "By signing below, both parties confirm they have read, understood, and agree to the terms of this loan agreement.",
                body))
            elements.append(Spacer(1, 0.8*cm))

            sig_data = [
                # Row 1: labels
                [Paragraph("BORROWER", bold),
                 Paragraph("", lbl),
                 Paragraph("LOAN OFFICER", bold)],
                # Row 2: name
                [Paragraph(client.full_name if client else "—", body),
                 Paragraph("", lbl),
                 Paragraph(self.current_user.full_name if self.current_user else "—", body)],
                # Row 3: sig lines
                [Paragraph("Signature: _______________________", lbl),
                 Paragraph("", lbl),
                 Paragraph("Signature: _______________________", lbl)],
                # Row 4: date lines
                [Paragraph("Date: ____________________________", lbl),
                 Paragraph("", lbl),
                 Paragraph("Date: ____________________________", lbl)],
                # Row 5: stamp
                [Paragraph("", lbl),
                 Paragraph("", lbl),
                 Paragraph("Official Stamp:", lbl)],
                [Paragraph("", lbl),
                 Paragraph("", lbl),
                 Paragraph("", lbl)],
            ]
            sig_t = Table(sig_data, colWidths=[7*cm, 2*cm, 7*cm])
            sig_t.setStyle(TableStyle([
                ("TOPPADDING",    (0,0), (-1,-1), 5),
                ("BOTTOMPADDING",(0,0), (-1,-1), 5),
                ("ROWBACKGROUNDS",(0,4),(-1,5),[LGREY,LGREY]),
                ("MINROWHEIGHT", (0,4), (-1,5), 1.5*cm),
            ]))
            elements.append(sig_t)

            # Footer
            elements.append(Spacer(1, 0.5*cm))
            elements.append(HRFlowable(width="100%", thickness=2, color=GREEN))
            elements.append(Paragraph(
                f"Bingongold Credit  |  Ham Tower, Wandegeya, Kampala  |  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                small))

            doc.build(elements)
            self._set_status(f"Saved: {filename}")

            import subprocess
            subprocess.Popen(["xdg-open", filename])

        except Exception as e:
            self._set_status(f"Error: {e}", COLORS["danger"])