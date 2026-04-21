"""
app/ui/screens/logs_screen.py
─────────────────────────────
User Activity Logs screen.
- Filter by: search text, action type, date range, and specific user
- Users dropdown is loaded live from the database
- Click any row to see full details in the detail panel
- Print PDF report of the current filtered view
"""

import threading
import customtkinter as ctk
from datetime import datetime, date, timedelta

from app.ui.styles.theme import COLORS, FONTS, primary_button_style, input_style
from app.ui.components.sidebar import Sidebar
from app.ui.components.data_table import DataTable


ACTION_OPTIONS = [
    "All Actions",
    "LOGIN",
    "CLIENT_CREATED",
    "LOAN_APPROVED",
    "LOAN_REJECTED",
    "REPAYMENT_RECORDED",
    "USER_CREATED",
    "USER_DEACTIVATED",
    "REPORT_GENERATED",
]

DATE_OPTIONS = ["All Time", "Today", "This Week", "This Month"]


class LogsScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master       = master
        self.current_user = master.current_user
        self._all_rows    = []
        self._user_map    = {}   # display_name → user_id  (None = all users)

        self._build()
        self._load_user_filter()   # populate user dropdown first
        self._load_logs()

    # ── navigation ─────────────────────────────────────────────────────────────

    def _navigate(self, screen: str):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    # ── layout ──────────────────────────────────────────────────────────────────

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        Sidebar(self, "logs", self._navigate, self.current_user).grid(
            row=0, column=0, sticky="nsew")

        main = ctk.CTkFrame(self, fg_color=COLORS["bg_primary"])
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)   # table expands

        self._build_toolbar(main)
        self._build_table(main)
        self._build_detail_panel(main)

    # ── toolbar ─────────────────────────────────────────────────────────────────

    def _build_toolbar(self, parent):
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 8))

        # ── Title row ────────────────────────────────────────────────────────
        title_row = ctk.CTkFrame(toolbar, fg_color="transparent")
        title_row.pack(fill="x", pady=(0, 12))
        title_row.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            title_row,
            text="User Activity Logs",
            font=FONTS["title"],
            text_color=COLORS["accent_green_dark"],
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            title_row,
            text="Track every action performed in the system by each user.",
            font=FONTS["body_small"],
            text_color=COLORS["text_muted"],
        ).grid(row=1, column=0, sticky="w")

        ctk.CTkButton(
            title_row,
            text="🖨  Print Report",
            width=140, height=38,
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["accent_green_dark"],
            text_color="#FFFFFF",
            font=FONTS["button"],
            corner_radius=8,
            command=self._print_report,
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        # ── Filter row ────────────────────────────────────────────────────────
        filter_row = ctk.CTkFrame(toolbar, fg_color="transparent")
        filter_row.pack(fill="x")

        # 1. Search
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._load_logs())
        ctk.CTkEntry(
            filter_row,
            textvariable=self.search_var,
            placeholder_text="Search action or description...",
            width=210,
            **input_style(),
        ).pack(side="left", padx=(0, 8))

        # 2. User filter (populated dynamically)
        self.user_filter_var = ctk.StringVar(value="All Users")
        self.user_filter_menu = ctk.CTkOptionMenu(
            filter_row,
            variable=self.user_filter_var,
            values=["All Users"],          # filled in _load_user_filter
            command=lambda _: self._load_logs(),
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_green"],
            button_hover_color=COLORS["accent_green_dark"],
            text_color=COLORS["text_primary"],
            font=FONTS["body_small"],
            width=180,
        )
        self.user_filter_menu.pack(side="left", padx=(0, 8))

        # 3. Action filter
        self.action_filter_var = ctk.StringVar(value="All Actions")
        ctk.CTkOptionMenu(
            filter_row,
            variable=self.action_filter_var,
            values=ACTION_OPTIONS,
            command=lambda _: self._load_logs(),
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_green"],
            button_hover_color=COLORS["accent_green_dark"],
            text_color=COLORS["text_primary"],
            font=FONTS["body_small"],
            width=180,
        ).pack(side="left", padx=(0, 8))

        # 4. Date range filter
        self.date_filter_var = ctk.StringVar(value="All Time")
        ctk.CTkOptionMenu(
            filter_row,
            variable=self.date_filter_var,
            values=DATE_OPTIONS,
            command=lambda _: self._load_logs(),
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_green"],
            button_hover_color=COLORS["accent_green_dark"],
            text_color=COLORS["text_primary"],
            font=FONTS["body_small"],
            width=140,
        ).pack(side="left", padx=(0, 8))

        # 5. Clear filters button
        ctk.CTkButton(
            filter_row,
            text="✕  Clear",
            width=90, height=36,
            fg_color="transparent",
            border_width=1,
            border_color=COLORS["border"],
            hover_color=COLORS["bg_input"],
            text_color=COLORS["text_secondary"],
            font=FONTS["body_small"],
            corner_radius=6,
            command=self._clear_filters,
        ).pack(side="left")

        # ── Result count ──────────────────────────────────────────────────────
        self.count_label = ctk.CTkLabel(
            toolbar, text="",
            font=FONTS["body_small"],
            text_color=COLORS["text_muted"],
        )
        self.count_label.pack(anchor="w", pady=(8, 0))

    # ── table ───────────────────────────────────────────────────────────────────

    def _build_table(self, parent):
        table_frame = ctk.CTkFrame(parent, fg_color="transparent")
        table_frame.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 8))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.table = DataTable(
            table_frame,
            columns=[
                ("timestamp",   "Timestamp",   150),
                ("user_name",   "User",        150),
                ("action",      "Action",      170),
                ("entity_type", "Entity",       90),
                ("entity_id",   "ID",           50),
                ("description", "Description", 240),
            ],
            on_select=self._on_log_selected,
        )
        self.table.grid(row=0, column=0, sticky="nsew")

    # ── detail panel ────────────────────────────────────────────────────────────

    def _build_detail_panel(self, parent):
        self.detail_panel = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
            height=110,
        )
        self.detail_panel.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 24))
        self.detail_panel.grid_propagate(False)
        self.detail_panel.columnconfigure(0, weight=1)
        self._detail_placeholder()

    def _detail_placeholder(self):
        for w in self.detail_panel.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.detail_panel,
            text="Click any log entry above to see its full details here.",
            font=FONTS["body_small"],
            text_color=COLORS["text_muted"],
        ).pack(pady=22)

    def _on_log_selected(self, row: dict):
        for w in self.detail_panel.winfo_children():
            w.destroy()

        content = ctk.CTkFrame(self.detail_panel, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=8)

        fields = [
            ("Timestamp",   row.get("timestamp",   "—")),
            ("User",        row.get("user_name",    "—")),
            ("Action",      row.get("action",       "—")),
            ("Entity",      f"{row.get('entity_type','—')}  #{ row.get('entity_id','—')}"),
            ("Description", row.get("description", "—")),
        ]

        # Two-column grid layout
        for i, (label, value) in enumerate(fields):
            col     = (i % 2) * 2
            row_num = i // 2
            ctk.CTkLabel(
                content, text=f"{label}:",
                font=FONTS["body_small"],
                text_color=COLORS["text_muted"],
                anchor="w",
            ).grid(row=row_num, column=col, sticky="w", padx=(0, 6), pady=2)
            ctk.CTkLabel(
                content, text=value,
                font=FONTS["body_small"],
                text_color=COLORS["text_primary"],
                anchor="w",
                wraplength=320,
            ).grid(row=row_num, column=col + 1, sticky="w", padx=(0, 24), pady=2)

    # ── data loading ────────────────────────────────────────────────────────────

    def _load_user_filter(self):
        """Load all system users into the user filter dropdown."""
        try:
            from app.database.connection import get_db
            from app.core.models.user import User

            with get_db() as db:
                users = db.query(User).order_by(User.full_name).all()
                for u in users:
                    db.expunge(u)

            # Build name → id map; use "Name (username)" to avoid duplicates
            self._user_map = {"All Users": None}
            display_names  = ["All Users"]

            for u in users:
                display = f"{u.full_name} ({u.username})"
                self._user_map[display] = u.id
                display_names.append(display)

            self.user_filter_menu.configure(values=display_names)

        except Exception as e:
            print(f"[LogsScreen] Could not load users for filter: {e}")

    def _load_logs(self, *_args):
        from app.database.connection import get_db
        from app.core.models.audit_log import AuditLog
        from app.core.models.user import User
        from sqlalchemy import desc

        search      = self.search_var.get().strip() if hasattr(self, "search_var") else ""
        action      = self.action_filter_var.get()  if hasattr(self, "action_filter_var")  else "All Actions"
        date_range  = self.date_filter_var.get()    if hasattr(self, "date_filter_var")     else "All Time"
        user_label  = self.user_filter_var.get()    if hasattr(self, "user_filter_var")     else "All Users"
        selected_uid = self._user_map.get(user_label)  # None means all users

        with get_db() as db:
            q = db.query(AuditLog, User).outerjoin(User, AuditLog.user_id == User.id)

            # ── User filter ───────────────────────────────────────────────
            if selected_uid is not None:
                q = q.filter(AuditLog.user_id == selected_uid)

            # ── Action filter ─────────────────────────────────────────────
            if action != "All Actions":
                q = q.filter(AuditLog.action == action)

            # ── Date filter ───────────────────────────────────────────────
            today = date.today()
            if date_range == "Today":
                q = q.filter(AuditLog.timestamp >= datetime.combine(
                    today, datetime.min.time()))
            elif date_range == "This Week":
                week_start = today - timedelta(days=today.weekday())
                q = q.filter(AuditLog.timestamp >= datetime.combine(
                    week_start, datetime.min.time()))
            elif date_range == "This Month":
                q = q.filter(AuditLog.timestamp >= datetime(
                    today.year, today.month, 1))

            # ── Text search ───────────────────────────────────────────────
            if search:
                term = f"%{search}%"
                q = q.filter(
                    AuditLog.action.ilike(term)       |
                    AuditLog.description.ilike(term)  |
                    User.full_name.ilike(term)
                )

            results = q.order_by(desc(AuditLog.timestamp)).limit(200).all()

            rows = []
            for log, user in results:
                rows.append({
                    "id":          log.id,
                    "timestamp":   (log.timestamp.strftime("%Y-%m-%d %H:%M")
                                    if log.timestamp else "—"),
                    "user_name":   user.full_name if user else "System",
                    "action":      log.action       or "—",
                    "entity_type": log.entity_type  or "—",
                    "entity_id":   str(log.entity_id) if log.entity_id else "—",
                    "description": log.description  or "—",
                })

        self._all_rows = rows

        if hasattr(self, "count_label"):
            user_info = (f" for {user_label}" if selected_uid else "")
            self.count_label.configure(
                text=f"Showing {len(rows)} log entr{'y' if len(rows)==1 else 'ies'}{user_info}")

        if hasattr(self, "table"):
            self.table.update_rows(rows)

        # Reset detail panel when filters change
        self._detail_placeholder()

    def _clear_filters(self):
        self.search_var.set("")
        self.user_filter_var.set("All Users")
        self.action_filter_var.set("All Actions")
        self.date_filter_var.set("All Time")
        self._load_logs()

    # ── PDF report ───────────────────────────────────────────────────────────────

    def _print_report(self):
        threading.Thread(target=self._generate_log_pdf, daemon=True).start()

    def _generate_log_pdf(self):
        try:
            import os
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors as rl_colors
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle,
                Paragraph, Spacer, HRFlowable,
            )
            from reportlab.lib.units import cm

            os.makedirs("./reports", exist_ok=True)
            filename = (
                f"./reports/user_logs_"
                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )
            doc = SimpleDocTemplate(
                filename, pagesize=A4,
                topMargin=2*cm, bottomMargin=2*cm,
                leftMargin=2*cm, rightMargin=2*cm,
            )

            GREEN = rl_colors.HexColor("#1A5C1E")
            LGREY = rl_colors.HexColor("#F0F7F0")

            title_s = ParagraphStyle(
                "T", fontSize=16, fontName="Helvetica-Bold",
                textColor=GREEN, spaceAfter=4)
            sub_s = ParagraphStyle(
                "S", fontSize=9, textColor=rl_colors.grey, spaceAfter=12)

            elements = []
            elements.append(Paragraph("BINGONGOLD CREDIT", title_s))

            # Subtitle shows active filters
            user_label  = self.user_filter_var.get()
            action      = self.action_filter_var.get()
            date_range  = self.date_filter_var.get()
            filter_info = "  |  ".join(filter(lambda x: x not in (
                "All Users", "All Actions", "All Time"), [user_label, action, date_range]))
            subtitle = (
                f"User Activity Log Report  —  "
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                + (f"  |  Filters: {filter_info}" if filter_info else "")
            )
            elements.append(Paragraph(subtitle, sub_s))
            elements.append(HRFlowable(
                width="100%", thickness=1.5, color=GREEN, spaceAfter=12))

            rows = getattr(self, "_all_rows", [])
            if not rows:
                elements.append(Paragraph("No log entries found.", sub_s))
            else:
                data = [["Timestamp", "User", "Action", "Entity", "Description"]]
                for r in rows:
                    data.append([
                        r.get("timestamp", ""),
                        r.get("user_name", ""),
                        r.get("action", ""),
                        f"{r.get('entity_type','')} {r.get('entity_id','')}".strip(),
                        r.get("description", "")[:70],
                    ])

                t = Table(
                    data,
                    colWidths=[3.5*cm, 3.5*cm, 4*cm, 2.5*cm, 5.5*cm],
                    repeatRows=1,
                )
                t.setStyle(TableStyle([
                    ("BACKGROUND",     (0,0), (-1,0),  GREEN),
                    ("TEXTCOLOR",      (0,0), (-1,0),  rl_colors.white),
                    ("FONTNAME",       (0,0), (-1,0),  "Helvetica-Bold"),
                    ("FONTSIZE",       (0,0), (-1,-1), 8),
                    ("ROWBACKGROUNDS", (0,1), (-1,-1), [LGREY, rl_colors.white]),
                    ("GRID",           (0,0), (-1,-1), 0.25, rl_colors.lightgrey),
                    ("VALIGN",         (0,0), (-1,-1), "MIDDLE"),
                    ("LEFTPADDING",    (0,0), (-1,-1), 5),
                    ("TOPPADDING",     (0,0), (-1,-1), 4),
                    ("BOTTOMPADDING",  (0,0), (-1,-1), 4),
                ]))
                elements.append(t)
                elements.append(Spacer(1, 0.5*cm))
                elements.append(Paragraph(
                    f"Total entries: {len(rows)}", sub_s))

            doc.build(elements)

            import subprocess
            subprocess.Popen(["xdg-open", filename])

            self.after(0, lambda: self.count_label.configure(
                text=f"✔  Report saved: {filename}",
                text_color=COLORS["accent_green"]))

        except Exception as e:
            self.after(0, lambda: self.count_label.configure(
                text=f"Error generating report: {e}",
                text_color=COLORS["danger"]))