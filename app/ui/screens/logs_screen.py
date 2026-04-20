"""
app/ui/screens/logs_screen.py
User activity logs — view operations, filter by user/action, print report.
"""

import threading
import customtkinter as ctk
from datetime import datetime, date
from app.ui.styles.theme import COLORS, FONTS, primary_button_style, input_style
from app.ui.components.sidebar import Sidebar
from app.ui.components.data_table import DataTable


class LogsScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master = master
        self.current_user = master.current_user
        self._build()
        self._load_logs()

    def _navigate(self, screen):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        Sidebar(self, "logs", self._navigate, self.current_user).grid(
            row=0, column=0, sticky="nsew")

        main = ctk.CTkFrame(self, fg_color=COLORS["bg_primary"])
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        self._build_toolbar(main)
        self._build_table(main)
        self._build_detail_panel(main)

    def _build_toolbar(self, parent):
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 12))
        toolbar.columnconfigure(3, weight=1)

        ctk.CTkLabel(toolbar, text="User Activity Logs",
                     font=FONTS["title"],
                     text_color=COLORS["accent_green_dark"]).grid(
            row=0, column=0, sticky="w", columnspan=4, pady=(0, 12))

        # Search
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._load_logs())
        ctk.CTkEntry(toolbar, textvariable=self.search_var,
                     placeholder_text="Search action or user...",
                     width=200, **input_style()).grid(
            row=1, column=0, padx=(0, 8))

        # Action filter
        self.action_filter = ctk.CTkOptionMenu(
            toolbar,
            values=["All Actions", "LOGIN", "CLIENT_CREATED", "LOAN_APPROVED",
                    "LOAN_REJECTED", "REPAYMENT_RECORDED", "USER_CREATED",
                    "USER_DEACTIVATED", "REPORT_GENERATED"],
            command=lambda v: self._load_logs(),
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_green"],
            text_color=COLORS["text_primary"],
            font=FONTS["body_small"],
            width=180,
        )
        self.action_filter.grid(row=1, column=1, padx=(0, 8))

        # Date filter
        self.date_filter = ctk.CTkOptionMenu(
            toolbar,
            values=["All Time", "Today", "This Week", "This Month"],
            command=lambda v: self._load_logs(),
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_green"],
            text_color=COLORS["text_primary"],
            font=FONTS["body_small"],
            width=140,
        )
        self.date_filter.grid(row=1, column=2, padx=(0, 8))

        # Spacer
        ctk.CTkFrame(toolbar, fg_color="transparent").grid(
            row=1, column=3)

        # Print/Export button
        ctk.CTkButton(toolbar, text="Print Report", width=130, height=38,
                      fg_color=COLORS["accent_green"],
                      hover_color=COLORS["accent_green_dark"],
                      text_color="#FFFFFF",
                      font=FONTS["button"], corner_radius=8,
                      command=self._print_report).grid(
            row=1, column=4, padx=(8, 0))

        # Log count label
        self.count_label = ctk.CTkLabel(toolbar, text="",
                                         font=FONTS["body_small"],
                                         text_color=COLORS["text_muted"])
        self.count_label.grid(row=2, column=0, columnspan=5, sticky="w",
                               pady=(8, 0))

    def _build_table(self, parent):
        table_frame = ctk.CTkFrame(parent, fg_color="transparent")
        table_frame.grid(row=1, column=0, sticky="nsew",
                          padx=24, pady=(0, 8))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.table = DataTable(
            table_frame,
            columns=[
                ("timestamp",   "Timestamp",    150),
                ("user_name",   "User",         140),
                ("action",      "Action",       160),
                ("entity_type", "Entity",        90),
                ("entity_id",   "ID",            50),
                ("description", "Description",  220),
            ],
            on_select=self._on_log_selected,
        )
        self.table.grid(row=0, column=0, sticky="nsew")

    def _build_detail_panel(self, parent):
        self.detail_panel = ctk.CTkFrame(
            parent, fg_color=COLORS["bg_card"],
            corner_radius=10, border_width=1,
            border_color=COLORS["border"], height=120)
        self.detail_panel.grid(row=2, column=0, sticky="ew",
                                padx=24, pady=(0, 24))
        self.detail_panel.grid_propagate(False)
        self.detail_panel.columnconfigure(0, weight=1)
        ctk.CTkLabel(self.detail_panel,
                     text="Click a log entry to see full details",
                     font=FONTS["body_small"],
                     text_color=COLORS["text_muted"]).pack(pady=20)

    def _on_log_selected(self, row):
        for w in self.detail_panel.winfo_children():
            w.destroy()

        content = ctk.CTkFrame(self.detail_panel, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=8)
        content.columnconfigure(1, weight=1)
        content.columnconfigure(3, weight=1)

        fields = [
            ("Timestamp",   row.get("timestamp", "—")),
            ("User",        row.get("user_name", "—")),
            ("Action",      row.get("action", "—")),
            ("Entity",      f"{row.get('entity_type','—')} #{row.get('entity_id','—')}"),
            ("Description", row.get("description", "—")),
        ]
        for i, (label, value) in enumerate(fields):
            col = (i % 2) * 2
            row_num = i // 2
            ctk.CTkLabel(content, text=f"{label}:",
                         font=FONTS["body_small"],
                         text_color=COLORS["text_muted"],
                         anchor="w").grid(row=row_num, column=col,
                                          sticky="w", padx=(0, 6), pady=2)
            ctk.CTkLabel(content, text=value,
                         font=FONTS["body_small"],
                         text_color=COLORS["text_primary"],
                         anchor="w", wraplength=300).grid(
                row=row_num, column=col+1, sticky="w", padx=(0, 20), pady=2)

    def _load_logs(self, *args):
        from app.database.connection import get_db
        from app.core.models.audit_log import AuditLog
        from app.core.models.user import User
        from sqlalchemy import desc
        from datetime import timedelta

        search = self.search_var.get().strip() if hasattr(self, "search_var") else None
        action = self.action_filter.get() if hasattr(self, "action_filter") else "All Actions"
        date_range = self.date_filter.get() if hasattr(self, "date_filter") else "All Time"

        with get_db() as db:
            q = db.query(AuditLog, User).outerjoin(
                User, AuditLog.user_id == User.id)

            if action != "All Actions":
                q = q.filter(AuditLog.action == action)

            today = date.today()
            if date_range == "Today":
                q = q.filter(
                    AuditLog.timestamp >= datetime.combine(today, datetime.min.time()))
            elif date_range == "This Week":
                week_start = today - timedelta(days=today.weekday())
                q = q.filter(
                    AuditLog.timestamp >= datetime.combine(week_start, datetime.min.time()))
            elif date_range == "This Month":
                q = q.filter(
                    AuditLog.timestamp >= datetime(today.year, today.month, 1))

            if search:
                term = f"%{search}%"
                q = q.filter(
                    AuditLog.action.ilike(term) |
                    AuditLog.description.ilike(term) |
                    User.full_name.ilike(term)
                )

            results = q.order_by(desc(AuditLog.timestamp)).limit(200).all()
            rows = []
            for log, user in results:
                rows.append({
                    "id":          log.id,
                    "timestamp":   log.timestamp.strftime("%Y-%m-%d %H:%M") if log.timestamp else "—",
                    "user_name":   user.full_name if user else "System",
                    "action":      log.action or "—",
                    "entity_type": log.entity_type or "—",
                    "entity_id":   str(log.entity_id) if log.entity_id else "—",
                    "description": log.description or "—",
                })

        if hasattr(self, "count_label"):
            self.count_label.configure(text=f"Showing {len(rows)} log entries")
        if hasattr(self, "table"):
            self.table.update_rows(rows)
        self._all_rows = rows

    def _print_report(self):
        threading.Thread(target=self._generate_log_pdf, daemon=True).start()

    def _generate_log_pdf(self):
        try:
            import os
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.units import cm

            os.makedirs("./reports", exist_ok=True)
            filename = f"./reports/user_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            doc = SimpleDocTemplate(filename, pagesize=A4,
                                    topMargin=2*cm, bottomMargin=2*cm,
                                    leftMargin=2*cm, rightMargin=2*cm)

            styles = getSampleStyleSheet()
            elements = []

            # Title
            from reportlab.platypus import Paragraph
            from reportlab.lib.styles import ParagraphStyle
            title_style = ParagraphStyle("T", fontSize=16, fontName="Helvetica-Bold",
                                         textColor=colors.HexColor("#1A5C1E"),
                                         spaceAfter=4)
            sub_style = ParagraphStyle("S", fontSize=10, textColor=colors.grey,
                                       spaceAfter=16)
            elements.append(Paragraph("BINGONGOLD CREDIT", title_style))
            elements.append(Paragraph(
                f"User Activity Log Report  —  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                sub_style))
            elements.append(Spacer(1, 0.3*cm))

            # Table
            data = [["Timestamp", "User", "Action", "Entity", "Description"]]
            rows = getattr(self, "_all_rows", [])
            for r in rows:
                data.append([
                    r.get("timestamp", ""),
                    r.get("user_name", ""),
                    r.get("action", ""),
                    f"{r.get('entity_type','')} {r.get('entity_id','')}".strip(),
                    r.get("description", "")[:60],
                ])

            t = Table(data, colWidths=[3.5*cm, 3.5*cm, 4*cm, 2.5*cm, 5.5*cm])
            t.setStyle(TableStyle([
                ("BACKGROUND",  (0,0), (-1,0), colors.HexColor("#1A5C1E")),
                ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
                ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE",    (0,0), (-1,-1), 8),
                ("ROWBACKGROUNDS", (0,1), (-1,-1),
                 [colors.HexColor("#F0F7F0"), colors.white]),
                ("GRID",        (0,0), (-1,-1), 0.25, colors.lightgrey),
                ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
                ("LEFTPADDING", (0,0), (-1,-1), 5),
                ("TOPPADDING",  (0,0), (-1,-1), 4),
            ]))
            elements.append(t)
            doc.build(elements)

            self.after(0, lambda: self.count_label.configure(
                text=f"Report saved: {filename}",
                text_color=COLORS["accent_green"]))
        except Exception as e:
            self.after(0, lambda: self.count_label.configure(
                text=f"Error: {e}", text_color=COLORS["danger"]))