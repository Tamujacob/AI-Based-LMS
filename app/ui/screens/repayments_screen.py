"""
app/ui/screens/repayments_screen.py
Updated: date picker, print receipt button
"""

import threading
import customtkinter as ctk
from datetime import date
from app.ui.styles.theme import COLORS, FONTS, primary_button_style, input_style
from app.ui.components.sidebar import Sidebar
from app.ui.components.date_picker import DatePicker
from app.ui.components.data_table import DataTable

PAYMENT_METHODS = ["Cash", "Mobile Money", "Bank Transfer", "Cheque"]


class RepaymentsScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master = master
        self.current_user = master.current_user
        self.found_loan = None
        self._last_receipt = None
        self._build()

    def _navigate(self, screen):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        Sidebar(self, "repayments", self._navigate, self.current_user).grid(
            row=0, column=0, sticky="nsew")
        main = ctk.CTkFrame(self, fg_color=COLORS["bg_primary"])
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=2)
        main.columnconfigure(1, weight=3)
        main.rowconfigure(0, weight=1)
        self._build_payment_form(main)
        self._build_history_panel(main)

    def _build_payment_form(self, parent):
        form = ctk.CTkScrollableFrame(
            parent, fg_color=COLORS["bg_card"], corner_radius=12,
            border_width=1, border_color=COLORS["border"],
            scrollbar_button_color=COLORS["border"])
        form.grid(row=0, column=0, sticky="nsew", padx=(24, 8), pady=24)
        form.columnconfigure(0, weight=1)

        ctk.CTkLabel(form, text="Record Payment", font=FONTS["subtitle"],
                     text_color=COLORS["accent_green_dark"]).pack(
            anchor="w", padx=20, pady=(20, 16))

        # Loan lookup
        ctk.CTkLabel(form, text="Loan Number *", font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"],
                     anchor="w").pack(fill="x", padx=20, pady=(0, 2))
        self.loan_number_var = ctk.StringVar()
        ctk.CTkEntry(form, textvariable=self.loan_number_var,
                     placeholder_text="e.g. BG-2025-12345",
                     **input_style()).pack(fill="x", padx=20)

        ctk.CTkButton(form, text="Find Loan", height=32,
                      font=FONTS["body_small"],
                      fg_color=COLORS["bg_input"],
                      hover_color=COLORS["border"],
                      text_color=COLORS["text_primary"], corner_radius=6,
                      command=self._find_loan).pack(anchor="w", padx=20, pady=(6, 0))

        self.loan_info = ctk.CTkFrame(
            form, fg_color=COLORS["bg_input"], corner_radius=8)
        self.loan_info.pack(fill="x", padx=20, pady=(10, 8))
        self.loan_info_label = ctk.CTkLabel(
            self.loan_info, text="No loan loaded.",
            font=FONTS["body_small"], text_color=COLORS["text_muted"])
        self.loan_info_label.pack(padx=12, pady=10)

        ctk.CTkFrame(form, fg_color=COLORS["border"],
                     height=1).pack(fill="x", padx=20, pady=8)

        # Amount
        ctk.CTkLabel(form, text="Amount Paid (UGX) *", font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"],
                     anchor="w").pack(fill="x", padx=20, pady=(0, 2))
        self.amount_var = ctk.StringVar()
        ctk.CTkEntry(form, textvariable=self.amount_var,
                     placeholder_text="e.g. 500000",
                     **input_style()).pack(fill="x", padx=20)

        # Payment date picker
        ctk.CTkLabel(form, text="Payment Date *", font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"],
                     anchor="w").pack(fill="x", padx=20, pady=(10, 2))
        date_row = ctk.CTkFrame(form, fg_color="transparent")
        date_row.pack(fill="x", padx=20)
        date_row.columnconfigure(0, weight=1)
        self.payment_date_picker = DatePicker(date_row, initial_date=date.today())
        self.payment_date_picker.grid(row=0, column=0, sticky="ew")

        # Payment method
        ctk.CTkLabel(form, text="Payment Method *", font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"],
                     anchor="w").pack(fill="x", padx=20, pady=(10, 2))
        self.method_var = ctk.StringVar(value="Cash")
        ctk.CTkOptionMenu(form, variable=self.method_var, values=PAYMENT_METHODS,
                          fg_color=COLORS["bg_input"],
                          button_color=COLORS["accent_green"],
                          text_color=COLORS["text_primary"],
                          font=FONTS["body_small"]).pack(fill="x", padx=20)

        # Transaction ref
        ctk.CTkLabel(form, text="Transaction Reference (optional)",
                     font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"],
                     anchor="w").pack(fill="x", padx=20, pady=(10, 2))
        self.ref_var = ctk.StringVar()
        ctk.CTkEntry(form, textvariable=self.ref_var,
                     placeholder_text="Mobile money or bank ref",
                     **input_style()).pack(fill="x", padx=20)

        # Notes
        ctk.CTkLabel(form, text="Notes (optional)", font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"],
                     anchor="w").pack(fill="x", padx=20, pady=(10, 2))
        self.notes_box = ctk.CTkTextbox(
            form, height=60, fg_color=COLORS["bg_input"],
            text_color=COLORS["text_primary"], font=FONTS["body"])
        self.notes_box.pack(fill="x", padx=20)

        self.form_error = ctk.CTkLabel(form, text="",
                                        font=FONTS["body_small"],
                                        text_color=COLORS["danger"])
        self.form_error.pack(padx=20, pady=(8, 0))

        # Submit
        ctk.CTkButton(form, text="Confirm Payment",
                      command=self._record_payment,
                      **primary_button_style()).pack(
            fill="x", padx=20, pady=(12, 8))

        # Print receipt (hidden until payment recorded)
        self.receipt_btn = ctk.CTkButton(
            form, text="Print Receipt",
            height=40, font=FONTS["button"],
            fg_color=COLORS["accent_gold"],
            hover_color=COLORS["accent_gold_dark"],
            text_color=COLORS["text_on_gold"],
            corner_radius=8,
            command=self._print_receipt,
            state="disabled")
        self.receipt_btn.pack(fill="x", padx=20, pady=(0, 20))

    def _build_history_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        panel.grid(row=0, column=1, sticky="nsew", padx=(8, 24), pady=24)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)
        ctk.CTkLabel(panel, text="Payment History",
                     font=FONTS["title"],
                     text_color=COLORS["accent_green_dark"]).grid(
            row=0, column=0, sticky="w", pady=(0, 12))
        self.history_table = DataTable(
            panel,
            columns=[
                ("receipt_number", "Receipt",   130),
                ("loan_number",    "Loan No.",  110),
                ("amount",         "Amount",    110),
                ("payment_date",   "Date",      100),
                ("method",         "Method",     90),
            ],
            on_select=self._on_history_selected,
        )
        self.history_table.grid(row=1, column=0, sticky="nsew")
        self._load_history()

    def _on_history_selected(self, row):
        """When clicking a past receipt, load it for printing."""
        self._last_receipt = row
        self.receipt_btn.configure(state="normal")
        self.form_error.configure(
            text=f"Receipt {row.get('receipt_number','')} loaded — click Print Receipt",
            text_color=COLORS["accent_green"])

    def _find_loan(self):
        from app.core.services.loan_service import LoanService
        from app.core.services.repayment_service import RepaymentService
        from app.core.services.client_service import ClientService
        number = self.loan_number_var.get().strip()
        if not number: return
        loans = LoanService.get_all_loans()
        loan  = next((l for l in loans if l.loan_number == number), None)
        if not loan:
            self.loan_info_label.configure(
                text="Loan not found.", text_color=COLORS["danger"])
            self.found_loan = None
            return
        self.found_loan = loan
        client  = ClientService.get_client_by_id(loan.client_id)
        balance = RepaymentService.get_outstanding_balance(loan.id)
        self.loan_info_label.configure(
            text=(f"Client: {client.full_name if client else '—'}  |  "
                  f"Type: {loan.loan_type.value if loan.loan_type else '—'}  |  "
                  f"Outstanding: UGX {balance:,.0f}  |  "
                  f"Status: {loan.status.value.upper()}"),
            text_color=COLORS["text_primary"])
        self._load_history(loan_id=loan.id)

    def _record_payment(self):
        from app.core.services.repayment_service import RepaymentService
        if not self.found_loan:
            self.form_error.configure(text="Please find a loan first.")
            return
        try:
            amount   = float(self.amount_var.get())
            pay_date = self.payment_date_picker.get_date()
            method   = self.method_var.get()
            ref      = self.ref_var.get().strip() or None
            notes    = self.notes_box.get("1.0", "end").strip() or None

            repayment = RepaymentService.record_payment(
                loan_id=self.found_loan.id,
                amount=amount,
                payment_method=method,
                payment_date=pay_date,
                transaction_reference=ref,
                notes=notes,
                recorded_by_id=self.current_user.id if self.current_user else None,
            )
            self.form_error.configure(
                text=f"Payment recorded — Receipt: {repayment.receipt_number}",
                text_color=COLORS["accent_green"])

            # Store for receipt printing
            from app.core.services.client_service import ClientService
            client = ClientService.get_client_by_id(self.found_loan.client_id)
            from app.core.services.repayment_service import RepaymentService as RS
            balance = RS.get_outstanding_balance(self.found_loan.id)
            self._last_receipt = {
                "receipt_number": repayment.receipt_number,
                "loan_number":    self.found_loan.loan_number,
                "client_name":    client.full_name if client else "—",
                "client_phone":   client.phone_number if client else "—",
                "amount":         f"UGX {amount:,.0f}",
                "payment_date":   str(pay_date),
                "method":         method,
                "reference":      ref or "—",
                "loan_type":      self.found_loan.loan_type.value if self.found_loan.loan_type else "—",
                "balance":        f"UGX {balance:,.0f}",
                "recorded_by":    self.current_user.full_name if self.current_user else "—",
            }
            self.receipt_btn.configure(state="normal")
            self.amount_var.set("")
            self.ref_var.set("")
            self.notes_box.delete("1.0", "end")
            self._load_history(loan_id=self.found_loan.id)
        except Exception as e:
            self.form_error.configure(text=str(e), text_color=COLORS["danger"])

    def _print_receipt(self):
        if not self._last_receipt:
            return
        threading.Thread(target=self._generate_receipt_pdf,
                         args=(self._last_receipt,), daemon=True).start()

    def _generate_receipt_pdf(self, data: dict):
        try:
            import os
            from reportlab.lib.pagesizes import A5
            from reportlab.lib import colors as rl_colors
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.platypus import (SimpleDocTemplate, Paragraph,
                                             Spacer, Table, TableStyle, HRFlowable)
            from reportlab.lib.units import cm
            from datetime import datetime

            os.makedirs("./reports", exist_ok=True)
            filename = f"./reports/receipt_{data['receipt_number']}.pdf"

            doc = SimpleDocTemplate(filename, pagesize=A5,
                                    topMargin=1.5*cm, bottomMargin=1.5*cm,
                                    leftMargin=1.8*cm, rightMargin=1.8*cm)

            GREEN  = rl_colors.HexColor("#1A5C1E")
            LGOLD  = rl_colors.HexColor("#D4A820")
            LGREY  = rl_colors.HexColor("#F0F7F0")

            elements = []

            # Header — company name
            h1 = ParagraphStyle("h1", fontSize=18, fontName="Helvetica-Bold",
                                 textColor=GREEN, alignment=1, spaceAfter=2)
            h2 = ParagraphStyle("h2", fontSize=10, fontName="Helvetica",
                                 textColor=rl_colors.grey, alignment=1, spaceAfter=8)
            body = ParagraphStyle("body", fontSize=10, fontName="Helvetica",
                                   textColor=rl_colors.black, spaceAfter=4)
            label = ParagraphStyle("lbl", fontSize=9, fontName="Helvetica",
                                    textColor=rl_colors.grey)
            bold = ParagraphStyle("bold", fontSize=10, fontName="Helvetica-Bold",
                                   textColor=rl_colors.black)

            elements.append(Paragraph("BINGONGOLD CREDIT", h1))
            elements.append(Paragraph("together as one", h2))
            elements.append(Paragraph(
                "Ham Tower, 4th Floor, Wandegeya, Kampala", h2))
            elements.append(HRFlowable(width="100%", thickness=2,
                                        color=GREEN, spaceAfter=10))

            # Receipt title
            title_s = ParagraphStyle("title", fontSize=14,
                                      fontName="Helvetica-Bold",
                                      textColor=GREEN, alignment=1, spaceAfter=4)
            elements.append(Paragraph("PAYMENT RECEIPT", title_s))
            elements.append(HRFlowable(width="100%", thickness=1,
                                        color=LGOLD, spaceAfter=12))

            # Receipt details table
            tdata = [
                ["Receipt No.", data["receipt_number"]],
                ["Date",        data.get("payment_date", "—")],
                ["Client",      data.get("client_name", "—")],
                ["Phone",       data.get("client_phone", "—")],
                ["Loan No.",    data.get("loan_number", "—")],
                ["Loan Type",   data.get("loan_type", "—")],
                ["Method",      data.get("method", "—")],
                ["Reference",   data.get("reference", "—")],
            ]
            t = Table(tdata, colWidths=[4*cm, 8*cm])
            t.setStyle(TableStyle([
                ("FONTNAME",    (0,0), (0,-1), "Helvetica-Bold"),
                ("FONTSIZE",    (0,0), (-1,-1), 10),
                ("TEXTCOLOR",   (0,0), (0,-1), rl_colors.grey),
                ("ROWBACKGROUNDS", (0,0), (-1,-1),
                 [LGREY, rl_colors.white]),
                ("TOPPADDING",  (0,0), (-1,-1), 5),
                ("BOTTOMPADDING", (0,0), (-1,-1), 5),
                ("LEFTPADDING", (0,0), (-1,-1), 6),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 0.5*cm))

            # Amount box — highlighted
            amt_s = ParagraphStyle("amt", fontSize=20,
                                    fontName="Helvetica-Bold",
                                    textColor=GREEN, alignment=1)
            amt_label = ParagraphStyle("amtl", fontSize=10,
                                        fontName="Helvetica",
                                        textColor=rl_colors.grey, alignment=1)
            amt_table = Table(
                [[Paragraph("AMOUNT PAID", amt_label)],
                 [Paragraph(data.get("amount", "—"), amt_s)],
                 [Paragraph(f"Outstanding Balance: {data.get('balance','—')}",
                             amt_label)]],
                colWidths=[12*cm])
            amt_table.setStyle(TableStyle([
                ("BACKGROUND",  (0,0), (-1,-1), LGREY),
                ("ROUNDEDCORNERS", [8]),
                ("TOPPADDING",  (0,0), (-1,-1), 8),
                ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ]))
            elements.append(amt_table)
            elements.append(Spacer(1, 1*cm))

            # Signature line
            elements.append(HRFlowable(width="100%", thickness=0.5,
                                        color=rl_colors.lightgrey))
            elements.append(Spacer(1, 0.3*cm))
            sig_data = [
                [Paragraph("Received by:", label),
                 Paragraph("", label),
                 Paragraph("Client signature:", label)],
                [Paragraph(data.get("recorded_by", "—"), bold),
                 Paragraph("", label),
                 Paragraph("_________________________", label)],
            ]
            sig_t = Table(sig_data, colWidths=[5*cm, 2*cm, 5*cm])
            sig_t.setStyle(TableStyle([
                ("TOPPADDING", (0,0), (-1,-1), 4),
                ("ALIGN",      (2,0), (2,-1), "RIGHT"),
            ]))
            elements.append(sig_t)
            elements.append(Spacer(1, 0.8*cm))
            elements.append(HRFlowable(width="100%", thickness=2, color=GREEN))
            footer_s = ParagraphStyle("footer", fontSize=8, textColor=rl_colors.grey,
                                       alignment=1, spaceBefore=4)
            elements.append(Paragraph(
                "Thank you for your payment  |  together as one", footer_s))
            elements.append(Paragraph(
                f"Printed: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                footer_s))

            doc.build(elements)

            self.after(0, lambda: self.form_error.configure(
                text=f"Receipt saved: {filename}",
                text_color=COLORS["accent_green"]))

            # Auto-open PDF
            import subprocess
            subprocess.Popen(["xdg-open", filename])

        except Exception as e:
            self.after(0, lambda: self.form_error.configure(
                text=f"Receipt error: {e}",
                text_color=COLORS["danger"]))

    def _load_history(self, loan_id: int = None):
        from app.core.services.repayment_service import RepaymentService
        from app.core.services.loan_service import LoanService
        if loan_id:
            repayments = RepaymentService.get_repayments_for_loan(loan_id)
        else:
            repayments = RepaymentService.get_all_recent_repayments(limit=30)
        all_loans = {l.id: l for l in LoanService.get_all_loans()}
        rows = []
        for r in repayments:
            loan = all_loans.get(r.loan_id)
            rows.append({
                "receipt_number": r.receipt_number,
                "loan_number":    loan.loan_number if loan else "—",
                "amount":         f"UGX {r.amount:,.0f}",
                "payment_date":   str(r.payment_date),
                "method":         r.payment_method.value if r.payment_method else "—",
            })
        if hasattr(self, "history_table"):
            self.history_table.update_rows(rows)