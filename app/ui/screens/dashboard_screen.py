"""
app/ui/screens/dashboard_screen.py
────────────────────────────────────
Performance fixes:
  1. All DB queries run in ONE background thread call
  2. Single combined query instead of 4 separate ones
  3. self.after() used for all widget updates from background
  4. refresh() reuses cached widgets — never rebuilds

v2 changes:
  - Recent Repayments replaced with Agent Notifications panel
  - Notifications paginated: 25 per page, filterable by week
  - Mark as read / Mark all read buttons
  - Severity colour coding per notification type

v3 fixes:
  - Popup grab_set() removed — was blocking all subsequent notification clicks
  - Popup tracker added — prevents duplicate popups for the same notification
  - Reminder banner now hides itself when count drops to zero on refresh
  - sqlalchemy text import aliased to sa_text — no longer shadows local 'text' variable
  - client_name truncation now appends ellipsis when cut
  - loan_type guard made explicit (handles raw strings safely)
  - _load_reminder_badge and _fetch_and_update banner calls unified with priority
"""

import threading
import customtkinter as ctk
from datetime import date, timedelta
from app.ui.styles.theme import COLORS, FONTS
from app.ui.components.sidebar import Sidebar
from app.ui.components.stat_card import StatCard
from app.ui.components.data_table import DataTable

STATUS_CONFIG = [
    ("pending",   "Pending",   "#F39C12", "#FEF9E7", "#E67E22"),
    ("approved",  "Approved",  "#2980B9", "#EBF5FB", "#2471A3"),
    ("active",    "Active",    "#27AE60", "#EAFAF1", "#1E8449"),
    ("completed", "Completed", "#7F8C8D", "#F2F3F4", "#707B7C"),
    ("defaulted", "Defaulted", "#C0392B", "#FDEDEC", "#A93226"),
]

# Notification type display config
NOTIF_CONFIG = {
    "instalment_upcoming": {
        "label":  "Upcoming Payment",
        "icon":   "🔔",
        "color":  "#2980B9",
    },
    "instalment_overdue": {
        "label":  "Missed Instalment",
        "icon":   "⚠️",
        "color":  "#E67E22",
    },
    "loan_overdue": {
        "label":  "Loan Overdue",
        "icon":   "🚨",
        "color":  "#C0392B",
    },
    "late_payment_fee": {
        "label":  "Late Fee Review",
        "icon":   "💰",
        "color":  "#8E44AD",
    },
}

SEVERITY_COLORS = {
    "CRITICAL": "#C0392B",
    "HIGH":     "#E74C3C",
    "MEDIUM":   "#E67E22",
    "LOW":      "#F39C12",
    "UPCOMING": "#2980B9",
}


class DashboardScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master         = master
        self.current_user   = master.current_user
        self._active_status = None
        self._loans_panel   = None

        # Notification pagination state
        self._notif_page        = 1
        self._notif_page_size   = 10
        self._notif_filter      = "all"   # "all" | "week" | "unread"
        self._notif_total       = 0

        self.details_mode       = None
        self.details_page       = 1
        self.details_page_size  = 10
        self.details_total      = 0

        # Tracks open detail popups keyed by notification id
        # so we never open a duplicate and can close stale ones
        self._open_popups: dict = {}

        # Reminder banner state — tracks which source set it last
        # priority: 0 = none, 1 = reminder_service, 2 = overdue loans
        self._banner_priority   = 0

        self._build()
        threading.Thread(target=self._fetch_and_update, daemon=True).start()
        threading.Thread(target=self._load_reminder_badge, daemon=True).start()

    # ── Refresh ────────────────────────────────────────────────────────────

    def refresh(self):
        threading.Thread(target=self._fetch_and_update, daemon=True).start()
        threading.Thread(target=self._load_reminder_badge, daemon=True).start()

    def _navigate(self, screen):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    # ── Build UI skeleton ──────────────────────────────────────────────────

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        Sidebar(self, "dashboard", self._navigate, self.current_user).grid(
            row=0, column=0, sticky="nsew")

        self.content = ctk.CTkScrollableFrame(
            self, fg_color=COLORS["bg_primary"],
            scrollbar_button_color=COLORS["accent_green"],
            scrollbar_button_hover_color=COLORS["accent_green_dark"],
        )
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)

        self._build_header()
        self._build_stat_cards()
        self._build_reminder_banner()
        self._build_loan_status_row()
        self._build_details_panel()
        self._build_notifications_panel()

    # ── Header ─────────────────────────────────────────────────────────────

    def _build_header(self):
        ctk.CTkFrame(self.content, fg_color=COLORS["accent_green"],
                     height=4, corner_radius=0).grid(row=0, column=0, sticky="ew")

        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.grid(row=1, column=0, sticky="ew", padx=28, pady=(20, 0))
        header.columnconfigure(1, weight=1)

        name = self.current_user.full_name if self.current_user else "User"
        ctk.CTkLabel(header, text=f"Good day,  {name}",
                     font=FONTS["title"],
                     text_color=COLORS["accent_green_dark"]).grid(
            row=0, column=0, sticky="w")
        ctk.CTkLabel(header,
                     text="Bingongold Credit  ·  Loans Management System",
                     font=FONTS["body"],
                     text_color=COLORS["text_secondary"]).grid(
            row=1, column=0, sticky="w", pady=(4, 0))
        ctk.CTkButton(header, text="↻  Refresh", width=110, height=34,
                      font=FONTS["body_small"],
                      fg_color=COLORS["accent_green"],
                      hover_color=COLORS["accent_green_dark"],
                      text_color="#FFFFFF", corner_radius=8,
                      command=lambda: self.master.force_refresh("dashboard")).grid(
            row=0, column=2, sticky="e")

    # ── Stat cards ─────────────────────────────────────────────────────────

    def _build_stat_cards(self):
        cf = ctk.CTkFrame(self.content, fg_color="transparent")
        cf.grid(row=2, column=0, sticky="ew", padx=28, pady=(20, 0))
        for i in range(4):
            cf.columnconfigure(i, weight=1)

        self.card_total    = StatCard(cf, "UGX", "Total Portfolio",  "—",
                                      accent=COLORS["accent_green"])
        self.card_active   = StatCard(cf, "✓",   "Active Loans",     "—",
                                      accent=COLORS["accent_green_dark"],
                                      cursor="hand2")
        self.card_overdue  = StatCard(cf, "!",   "Overdue Loans",    "—",
                                      accent=COLORS["danger"],
                                      cursor="hand2")
        self.card_clients  = StatCard(cf, "P",   "Total Clients",    "—",
                                      accent=COLORS["accent_gold"],
                                      cursor="hand2")

        self.card_total.grid(row=0,   column=0, padx=(0, 8), sticky="ew")
        self.card_active.grid(row=0,  column=1, padx=8,      sticky="ew")
        self.card_overdue.grid(row=0, column=2, padx=8,      sticky="ew")
        self.card_clients.grid(row=0, column=3, padx=(8, 0), sticky="ew")

        self._attach_card_click(self.card_active, self._show_active_loans)
        self._attach_card_click(self.card_overdue, self._show_overdue_loans)
        self._attach_card_click(self.card_clients, self._show_clients)

    # ── Reminder banner ────────────────────────────────────────────────────

    def _build_reminder_banner(self):
        self.reminder_banner = ctk.CTkFrame(
            self.content,
            fg_color=COLORS["warning"],
            corner_radius=8,
        )
        self.reminder_label = ctk.CTkLabel(
            self.reminder_banner, text="",
            font=FONTS["body_small"],
            text_color=COLORS["text_on_gold"],
        )
        self.reminder_label.pack(padx=16, pady=(10, 4))
        ctk.CTkButton(
            self.reminder_banner,
            text="View Reminders & Alerts  →",
            height=28, font=FONTS["body_small"],
            fg_color=COLORS["accent_green_dark"],
            hover_color=COLORS["accent_green"],
            text_color="#FFFFFF", corner_radius=6,
            command=lambda: self._navigate("agent"),
        ).pack(padx=16, pady=(0, 10))

    def _show_reminder_banner(self, text, priority: int = 1):
        """Show the reminder banner. Higher priority wins; pass text=None to hide."""
        if text is None:
            # Only hide if nothing higher-priority is showing
            if priority >= self._banner_priority:
                self._banner_priority = 0
                self.reminder_banner.grid_remove()
            return

        if priority >= self._banner_priority:
            self._banner_priority = priority
            self.reminder_label.configure(text=text)
            self.reminder_banner.grid(
                row=3, column=0, sticky="ew", padx=28, pady=(12, 0))

    # ── Loan status row ────────────────────────────────────────────────────

    def _build_loan_status_row(self):
        hdr = ctk.CTkFrame(self.content, fg_color="transparent")
        hdr.grid(row=4, column=0, sticky="ew", padx=28, pady=(28, 6))
        hdr.columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="Loan Status Overview",
                     font=FONTS["heading"],
                     text_color=COLORS["accent_green_dark"],
                     anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hdr, text="Click a card to view those loans ↓",
                     font=FONTS["body_small"],
                     text_color=COLORS["text_muted"],
                     anchor="e").grid(row=0, column=1, sticky="e")

        self.status_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self.status_frame.grid(row=5, column=0, sticky="ew", padx=28)
        for i in range(5):
            self.status_frame.columnconfigure(i, weight=1)

        self.status_labels  = {}
        self._status_cards  = {}
        for i, (key, label, color, bg, hover) in enumerate(STATUS_CONFIG):
            self._build_status_card(i, key, label, color, bg, hover)

    def _attach_card_click(self, card, command):
        def on_click(_e, cmd=command):
            cmd()

        def bind_recursive(widget):
            widget.bind("<Button-1>", on_click)
            for child in widget.winfo_children():
                bind_recursive(child)

        bind_recursive(card)

    def _show_active_loans(self):
        threading.Thread(target=self._load_dashboard_loans, args=("active",), daemon=True).start()

    def _show_overdue_loans(self):
        threading.Thread(target=self._load_dashboard_loans, args=("overdue",), daemon=True).start()

    def _show_clients(self):
        threading.Thread(target=self._load_dashboard_clients, daemon=True).start()

    def _build_details_panel(self):
        self.details_frame = ctk.CTkFrame(
            self.content,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"],
        )
        self.details_frame.grid(row=6, column=0, sticky="ew", padx=28, pady=(20, 0))
        self.details_frame.columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.details_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 4))
        header.columnconfigure(0, weight=1)

        self.details_title = ctk.CTkLabel(
            header,
            text="Click a KPI card to view details",
            font=FONTS["title"],
            text_color=COLORS["accent_green_dark"],
            anchor="w",
        )
        self.details_title.grid(row=0, column=0, sticky="w")

        self.details_subtitle = ctk.CTkLabel(
            header,
            text="Active loans, overdue loans, or client records show here.",
            font=FONTS["body_small"],
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self.details_subtitle.grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.details_table = DataTable(
            self.details_frame,
            columns=[],
            rows=[],
        )
        self.details_table.grid(
            row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))

        pager = ctk.CTkFrame(self.details_frame, fg_color="transparent")
        pager.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))
        pager.columnconfigure(1, weight=1)

        self.details_prev_btn = ctk.CTkButton(
            pager, text="◀ Prev", width=100,
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"],
            font=FONTS["body_small"],
            corner_radius=6,
            command=self._details_prev_page,
        )
        self.details_prev_btn.grid(row=0, column=0, sticky="w")

        self.details_page_label = ctk.CTkLabel(
            pager, text="Page 1 of 1",
            font=FONTS["body_small"],
            text_color=COLORS["text_muted"],
        )
        self.details_page_label.grid(row=0, column=1)

        self.details_next_btn = ctk.CTkButton(
            pager, text="Next ▶", width=100,
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["accent_green_dark"],
            text_color="#FFFFFF",
            font=FONTS["body_small"],
            corner_radius=6,
            command=self._details_next_page,
        )
        self.details_next_btn.grid(row=0, column=2, sticky="e")

    def _show_dashboard_details(self, title: str, subtitle: str,
                                columns: list, rows: list):
        self.details_title.configure(text=title)
        self.details_subtitle.configure(text=subtitle)

        self.details_table.destroy()
        self.details_table = DataTable(
            self.details_frame,
            columns=columns,
            rows=rows,
        )
        self.details_table.grid(
            row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self._update_details_pagination_controls()

    def _update_details_pagination_controls(self):
        total_pages = max(
            1,
            (self.details_total + self.details_page_size - 1)
            // self.details_page_size,
        )
        self.details_page_label.configure(
            text=f"Page {self.details_page} of {total_pages}")
        self.details_prev_btn.configure(
            state="normal" if self.details_page > 1 else "disabled")
        self.details_next_btn.configure(
            state="normal" if self.details_page < total_pages else "disabled")

    def _details_prev_page(self):
        if self.details_page > 1 and self.details_mode:
            self.details_page -= 1
            if self.details_mode in ("active", "overdue"):
                threading.Thread(
                    target=self._load_dashboard_loans,
                    args=(self.details_mode, self.details_page),
                    daemon=True,
                ).start()
            elif self.details_mode == "clients":
                threading.Thread(
                    target=self._load_dashboard_clients,
                    args=(self.details_page,),
                    daemon=True,
                ).start()

    def _details_next_page(self):
        total_pages = max(
            1,
            (self.details_total + self.details_page_size - 1)
            // self.details_page_size,
        )
        if self.details_page < total_pages and self.details_mode:
            self.details_page += 1
            if self.details_mode in ("active", "overdue"):
                threading.Thread(
                    target=self._load_dashboard_loans,
                    args=(self.details_mode, self.details_page),
                    daemon=True,
                ).start()
            elif self.details_mode == "clients":
                threading.Thread(
                    target=self._load_dashboard_clients,
                    args=(self.details_page,),
                    daemon=True,
                ).start()

    def _load_dashboard_loans(self, mode: str, page: int = 1):
        try:
            self.details_mode = mode
            self.details_page = page
            from app.database.connection import get_db
            from sqlalchemy import text

            offset = (self.details_page - 1) * self.details_page_size

            if mode == "active":
                title = "Active Loans"
                subtitle = "Showing active loans currently in repayment."
                sql = text(
                    "SELECT l.loan_number, c.full_name as client_name, "
                    "l.loan_type, "
                    "COALESCE(l.principal_amount, 0) as principal_amount, "
                    "l.due_date "
                    "FROM loans l "
                    "JOIN clients c ON l.client_id = c.id "
                    "WHERE l.status = 'active' "
                    "ORDER BY l.id DESC "
                    "LIMIT :limit OFFSET :offset"
                )
            else:
                title = "Overdue Loans"
                subtitle = "Showing active loans that are past their due date."
                sql = text(
                    "SELECT l.loan_number, c.full_name as client_name, "
                    "l.loan_type, "
                    "COALESCE(l.principal_amount, 0) as principal_amount, "
                    "l.due_date "
                    "FROM loans l "
                    "JOIN clients c ON l.client_id = c.id "
                    "WHERE l.status = 'active' "
                    "AND l.due_date < CURRENT_DATE "
                    "ORDER BY l.id DESC "
                    "LIMIT :limit OFFSET :offset"
                )

            with get_db() as db:
                rows = [
                    {
                        "loan_number": r.loan_number or "—",
                        "client_name": r.client_name or "—",
                        "loan_type":   str(r.loan_type) if r.loan_type else "—",
                        "principal":   f"UGX {float(r.principal_amount):,.0f}",
                        "due_date":    str(r.due_date) if r.due_date else "—",
                    }
                    for r in db.execute(sql, {
                        "limit": self.details_page_size,
                        "offset": offset,
                    }).mappings()
                ]

                count_sql = text(
                    "SELECT COUNT(*) FROM loans l "
                    "JOIN clients c ON l.client_id = c.id "
                    "WHERE l.status = 'active' "
                    + ("AND l.due_date < CURRENT_DATE "
                       if mode == 'overdue' else "")
                )
                self.details_total = db.execute(count_sql).scalar() or 0

            columns = [
                ("loan_number", "Loan No.", 110),
                ("client_name", "Client", 160),
                ("loan_type", "Type", 120),
                ("principal", "Principal", 115),
                ("due_date", "Due Date", 110),
            ]
            self.after(0, lambda: self._show_dashboard_details(
                title, subtitle, columns, rows))
        except Exception as e:
            print(f"[Dashboard] Load dashboard loans error: {e}")

    def _load_dashboard_clients(self, page: int = 1):
        try:
            self.details_mode = "clients"
            self.details_page = page
            from app.database.connection import get_db
            from sqlalchemy import text

            title = "Clients"
            subtitle = "Showing active client records."
            offset = (self.details_page - 1) * self.details_page_size
            sql = text(
                "SELECT full_name, nin, phone_number, occupation "
                "FROM clients "
                "WHERE is_active = true "
                "ORDER BY id DESC "
                "LIMIT :limit OFFSET :offset"
            )
            with get_db() as db:
                rows = [
                    {
                        "full_name":    r.full_name or "—",
                        "nin":          r.nin or "—",
                        "phone_number": r.phone_number or "—",
                        "occupation":   r.occupation or "—",
                    }
                    for r in db.execute(sql, {
                        "limit": self.details_page_size,
                        "offset": offset,
                    }).mappings()
                ]

                count_sql = text(
                    "SELECT COUNT(*) FROM clients "
                    "WHERE is_active = true"
                )
                self.details_total = db.execute(count_sql).scalar() or 0

            columns = [
                ("full_name", "Full Name", 200),
                ("nin", "NIN", 120),
                ("phone_number", "Phone", 120),
                ("occupation", "Occupation", 160),
            ]
            self.after(0, lambda: self._show_dashboard_details(
                title, subtitle, columns, rows))
        except Exception as e:
            print(f"[Dashboard] Load clients error: {e}")

    def _build_status_card(self, col, key, label, color, bg_color, hover_color):
        card = ctk.CTkFrame(self.status_frame, fg_color=bg_color,
                             corner_radius=12, border_width=2,
                             border_color=color, cursor="hand2")
        card.grid(row=0, column=col, padx=4, sticky="ew")
        ctk.CTkFrame(card, fg_color=color, height=5,
                     corner_radius=0).pack(fill="x")
        ctk.CTkLabel(card, text="↓", font=("Helvetica", 11, "bold"),
                     text_color=color, anchor="e").pack(
            fill="x", padx=(0, 10), pady=(4, 0))
        ctk.CTkLabel(card, text=label, font=FONTS["body_small"],
                     text_color="#555555", anchor="center").pack(pady=(0, 2))
        count_lbl = ctk.CTkLabel(card, text="—", font=FONTS["subtitle"],
                                  text_color=color, anchor="center")
        count_lbl.pack()
        ctk.CTkLabel(card, text="tap to view", font=FONTS["caption"],
                     text_color=color, anchor="center").pack(pady=(2, 10))
        self.status_labels[key] = count_lbl
        self._status_cards[key] = (card, color, bg_color)

        def on_enter(_e):
            if self._active_status != key:
                card.configure(fg_color=hover_color)
        def on_leave(_e):
            if self._active_status != key:
                card.configure(fg_color=bg_color)
        def on_click(_e):
            self._toggle_loans_panel(key)

        for w in [card] + card.winfo_children():
            w.bind("<Enter>",    on_enter)
            w.bind("<Leave>",    on_leave)
            w.bind("<Button-1>", on_click)

    # ══════════════════════════════════════════════════════════════════════════
    # Notifications panel
    # ══════════════════════════════════════════════════════════════════════════

    def _build_notifications_panel(self):
        """Build the notifications section with header, filters, list, and pagination."""

        # ── Section header ────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self.content, fg_color="transparent")
        hdr.grid(row=7, column=0, sticky="ew", padx=28, pady=(28, 0))
        hdr.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr, text="Agent Notifications",
            font=FONTS["heading"],
            text_color=COLORS["accent_green_dark"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        # Mark all read button
        ctk.CTkButton(
            hdr, text="✓ Mark all read",
            width=120, height=28,
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_secondary"],
            font=FONTS["caption"], corner_radius=6,
            command=self._mark_all_read,
        ).grid(row=0, column=1, sticky="e", padx=(0, 6))

        ctk.CTkButton(
            hdr, text="↻ Refresh",
            width=80, height=28,
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_secondary"],
            font=FONTS["caption"], corner_radius=6,
            command=self._reload_notifications,
        ).grid(row=0, column=2, sticky="e")

        # ── Filter tabs ───────────────────────────────────────────────────
        filter_row = ctk.CTkFrame(self.content, fg_color="transparent")
        filter_row.grid(row=8, column=0, sticky="ew", padx=28, pady=(8, 0))

        self._filter_btns = {}
        for label, key in [
            ("All",        "all"),
            ("This week",  "week"),
            ("Unread",     "unread"),
            ("Upcoming",   "instalment_upcoming"),
            ("Missed",     "instalment_overdue"),
            ("Loan Due",   "loan_overdue"),
            ("Late Fee",   "late_payment_fee"),
        ]:
            btn = ctk.CTkButton(
                filter_row,
                text=label,
                width=80, height=28,
                fg_color=(COLORS["accent_green"]
                          if key == self._notif_filter
                          else COLORS["bg_input"]),
                hover_color=COLORS["accent_green"],
                text_color=("#FFFFFF"
                            if key == self._notif_filter
                            else COLORS["text_secondary"]),
                font=FONTS["caption"],
                corner_radius=6,
                command=lambda k=key: self._set_filter(k),
            )
            btn.pack(side="left", padx=(0, 6))
            self._filter_btns[key] = btn

        # ── Notifications list container ───────────────────────────────────
        self.notif_container = ctk.CTkFrame(
            self.content,
            fg_color=COLORS["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
        )
        self.notif_container.grid(
            row=9, column=0, sticky="ew", padx=28, pady=(8, 0))
        self.notif_container.columnconfigure(0, weight=1)

        # Placeholder while loading
        self.notif_loading_label = ctk.CTkLabel(
            self.notif_container,
            text="Loading notifications...",
            font=FONTS["body"],
            text_color=COLORS["text_muted"],
        )
        self.notif_loading_label.pack(pady=24)

        # ── Pagination controls ────────────────────────────────────────────
        page_row = ctk.CTkFrame(self.content, fg_color="transparent")
        page_row.grid(row=10, column=0, sticky="ew",
                      padx=28, pady=(6, 28))
        page_row.columnconfigure(1, weight=1)

        self.notif_prev_btn = ctk.CTkButton(
            page_row, text="◀ Previous",
            width=100, height=30,
            fg_color="#FFFFFF",
            hover_color=COLORS["bg_input"],
            text_color=COLORS["text_secondary"],
            border_width=1,
            border_color=COLORS["border"],
            font=FONTS["caption"], corner_radius=6,
            state="disabled",
            command=self._notif_prev_page,
        )
        self.notif_prev_btn.grid(row=0, column=0, sticky="w")

        self.notif_page_label = ctk.CTkLabel(
            page_row, text="",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
        )
        self.notif_page_label.grid(row=0, column=1)

        self.notif_next_btn = ctk.CTkButton(
            page_row, text="Next ▶",
            width=100, height=30,
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["accent_green_dark"],
            text_color="#FFFFFF",
            font=FONTS["caption"], corner_radius=6,
            state="disabled",
            command=self._notif_next_page,
        )
        self.notif_next_btn.grid(row=0, column=2, sticky="e")

        # Load notifications
        threading.Thread(
            target=self._fetch_notifications, daemon=True).start()

    # ── Filter + pagination controls ───────────────────────────────────────

    def _set_filter(self, key: str):
        self._notif_filter = key
        self._notif_page   = 1

        # Update button styles
        for k, btn in self._filter_btns.items():
            if k == key:
                btn.configure(
                    fg_color=COLORS["accent_green"],
                    text_color="#FFFFFF",
                )
            else:
                btn.configure(
                    fg_color=COLORS["bg_input"],
                    text_color=COLORS["text_secondary"],
                )

        threading.Thread(
            target=self._fetch_notifications, daemon=True).start()

    def _notif_prev_page(self):
        if self._notif_page > 1:
            self._notif_page -= 1
            threading.Thread(
                target=self._fetch_notifications, daemon=True).start()

    def _notif_next_page(self):
        total_pages = max(
            1,
            (self._notif_total + self._notif_page_size - 1)
            // self._notif_page_size,
        )
        if self._notif_page < total_pages:
            self._notif_page += 1
            threading.Thread(
                target=self._fetch_notifications, daemon=True).start()

    def _reload_notifications(self):
        self._notif_page = 1
        threading.Thread(
            target=self._fetch_notifications, daemon=True).start()

    def _mark_all_read(self):
        def run():
            try:
                from app.core.agents.background_agent import BackgroundAgent
                BackgroundAgent.mark_all_read()
                self.after(0, self._reload_notifications)
            except Exception as e:
                print(f"[Dashboard] mark_all_read error: {e}")
        threading.Thread(target=run, daemon=True).start()

    # ── Notification data fetching ─────────────────────────────────────────

    def _fetch_notifications(self):
        """Fetch notifications from DB with filter and pagination.
        Joins loans + clients to include client name, loan number, and NIN."""
        try:
            from app.database.connection import get_db
            from sqlalchemy import text as sa_text

            offset = (self._notif_page - 1) * self._notif_page_size
            filt   = self._notif_filter

            # Build WHERE clause based on filter
            where_clauses = []
            params: dict  = {
                "limit":  self._notif_page_size,
                "offset": offset,
            }

            if filt == "unread":
                where_clauses.append("an.is_read = false")
            elif filt == "week":
                where_clauses.append("an.notif_date >= :week_start")
                params["week_start"] = str(
                    date.today() - timedelta(days=7))
            elif filt in NOTIF_CONFIG:
                where_clauses.append("an.notif_type = :ntype")
                params["ntype"] = filt

            where_sql = (
                "WHERE " + " AND ".join(where_clauses)
                if where_clauses else ""
            )

            with get_db() as db:
                # Total count
                count_sql = sa_text(f"""
                    SELECT COUNT(*)
                    FROM   agent_notifications an
                    {where_sql}
                """)
                total = db.execute(count_sql, params).scalar() or 0

                # Fetch page — join loans + clients for identity fields
                data_sql = sa_text(f"""
                    SELECT
                        an.id,
                        an.loan_id,
                        an.notif_type,
                        an.notif_date,
                        an.severity,
                        an.message,
                        an.is_read,
                        an.created_at,
                        l.loan_number,
                        c.full_name   AS client_name,
                        c.nin         AS client_nin,
                        c.phone_number AS client_phone
                    FROM   agent_notifications an
                    LEFT JOIN loans   l ON an.loan_id   = l.id
                    LEFT JOIN clients c ON l.client_id  = c.id
                    {where_sql}
                    ORDER BY
                        CASE an.severity
                            WHEN 'CRITICAL' THEN 1
                            WHEN 'HIGH'     THEN 2
                            WHEN 'MEDIUM'   THEN 3
                            WHEN 'UPCOMING' THEN 4
                            ELSE 5
                        END,
                        an.created_at DESC
                    LIMIT  :limit OFFSET :offset
                """)
                rows = db.execute(data_sql, params).mappings().fetchall()
                notifications = [dict(r) for r in rows]

            self._notif_total = total
            self.after(0, lambda: self._render_notifications(
                notifications, total))

        except Exception as e:
            print(f"[Dashboard] fetch_notifications error: {e}")
            self.after(0, lambda: self._show_notif_error(str(e)))

    # ── Notification rendering ─────────────────────────────────────────────

    def _render_notifications(self, notifications: list, total: int):
        """Render notification cards inside notif_container."""

        # Clear container
        for w in self.notif_container.winfo_children():
            w.destroy()

        if not notifications:
            msg = {
                "all":    "No notifications yet — the agent is watching.",
                "week":   "No notifications this week.",
                "unread": "All caught up — no unread notifications.",
            }.get(self._notif_filter,
                  "No notifications for this filter.")

            ctk.CTkLabel(
                self.notif_container,
                text=msg,
                font=FONTS["body"],
                text_color=COLORS["text_muted"],
            ).pack(pady=32)

            self._update_pagination_controls(total)
            return

        # Column headers
        col_hdr = ctk.CTkFrame(
            self.notif_container,
            fg_color=COLORS["accent_green"],
            corner_radius=0, height=34,
        )
        col_hdr.pack(fill="x")
        col_hdr.pack_propagate(False)

        for col_text, width in [
            ("Type",        110),
            ("Loan No.",     80),
            ("Client",      100),
            ("NIN",          90),
            ("Message",     140),
            ("Date",         80),
            ("Severity",     64),
            ("",             90),
        ]:
            ctk.CTkLabel(
                col_hdr, text=col_text,
                font=FONTS["badge"],
                text_color="#FFFFFF",
                width=width, anchor="w",
            ).pack(side="left",
                   padx=(16 if col_text == "Type" else 4, 0))

        # Notification rows
        for i, notif in enumerate(notifications):
            self._render_notif_row(notif, i)

        self._update_pagination_controls(total)

    def _render_notif_row(self, notif: dict, index: int):
        """Render a single notification row.

        Click handling: the entire row (frame + every child label) is bound
        to <Button-1> so a touchpad tap anywhere on the row opens the detail
        popup.  The "✓ Read" button is excluded from that binding so it keeps
        its own independent action.
        """
        cfg       = NOTIF_CONFIG.get(notif["notif_type"], {
            "label": notif["notif_type"].replace("_", " ").title(),
            "icon":  "ℹ",
            "color": COLORS["text_secondary"],
        })
        sev_color = SEVERITY_COLORS.get(
            notif["severity"], COLORS["text_muted"])
        is_read   = notif["is_read"]

        # Row background
        bg      = COLORS["bg_card"] if index % 2 == 0 else COLORS["bg_input"]
        hover_bg = "#D6EFD6"   # consistent hover colour regardless of read state
        if not is_read:
            bg = "#F0FAF0" if index % 2 == 0 else "#E8F5E8"

        # Fixed-height compact row — 44px (slightly taller = easier to tap)
        row = ctk.CTkFrame(
            self.notif_container,
            fg_color=bg,
            corner_radius=0,
            height=44,
            cursor="hand2",
        )
        row.pack(fill="x")
        row.pack_propagate(False)

        # Left accent bar (4 px, severity colour) — not clickable for detail
        ctk.CTkFrame(
            row, fg_color=sev_color, width=4, corner_radius=0,
        ).pack(side="left", fill="y")

        # Unread dot
        ctk.CTkLabel(
            row,
            text="●" if not is_read else " ",
            font=("Helvetica", 8),
            text_color=COLORS["accent_green"] if not is_read else bg,
            width=12,
        ).pack(side="left", padx=(4, 0))

        # Type label
        ctk.CTkLabel(
            row,
            text=f"{cfg['icon']} {cfg['label']}",
            font=FONTS["caption"],
            text_color=cfg["color"],
            width=120,
            anchor="w",
        ).pack(side="left", padx=(4, 4))

        # Loan number
        loan_num = notif.get("loan_number") or "—"
        ctk.CTkLabel(
            row,
            text=loan_num,
            font=FONTS["caption"],
            text_color=COLORS["accent_green_dark"],
            width=90,
            anchor="w",
        ).pack(side="left", padx=(0, 4))

        # Client name — truncated with ellipsis when over 18 chars
        raw_name    = notif.get("client_name") or "—"
        client_name = (raw_name[:17] + "…") if len(raw_name) > 18 else raw_name
        ctk.CTkLabel(
            row,
            text=client_name,
            font=FONTS["caption"],
            text_color=COLORS["text_primary"],
            width=120,
            anchor="w",
        ).pack(side="left", padx=(0, 4))

        # NIN
        nin = notif.get("client_nin") or "—"
        ctk.CTkLabel(
            row,
            text=nin,
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            width=110,
            anchor="w",
        ).pack(side="left", padx=(0, 4))

        # Message preview — remove loan number from the preview and keep it short.
        raw_message = notif.get("message", "")
        first_line = raw_message.split("\n")[0]
        if " — " in first_line:
            first_line = first_line.split(" — ", 1)[0]
        loan_num = notif.get("loan_number") or ""
        if loan_num and loan_num in first_line:
            first_line = first_line.replace(loan_num, "").strip()
        if len(first_line) > 28:
            first_line = first_line[:28].rstrip() + "…"

        ctk.CTkLabel(
            row,
            text=first_line or "Notification",
            font=FONTS["body_small"],
            text_color=(COLORS["text_primary"] if not is_read
                        else COLORS["text_secondary"]),
            anchor="w",
        ).pack(side="left", padx=(0, 8), fill="x", expand=True)

        # Date
        ctk.CTkLabel(
            row,
            text=str(notif["notif_date"]),
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            width=80,
            anchor="w",
        ).pack(side="left", padx=(0, 8))

        # Severity badge
        ctk.CTkLabel(
            row,
            text=notif["severity"],
            font=FONTS["caption"],
            text_color=sev_color,
            fg_color=COLORS["bg_card"],
            corner_radius=4,
            width=72,
        ).pack(side="left", padx=(0, 6))

        action_frame = ctk.CTkFrame(
            row,
            fg_color=COLORS["bg_card"],
            corner_radius=0,
        )
        action_frame.pack(side="right", padx=(0, 10), fill="y")
        action_frame.bind("<Button-1>", lambda e: "break")

        # WhatsApp button
        whatsapp_btn = ctk.CTkButton(
            action_frame,
            text="💬",
            width=42, height=28,
            fg_color="#25D366",
            hover_color="#1FA851",
            text_color="#FFFFFF",
            font=FONTS["caption"], corner_radius=4,
            command=lambda n=notif: self._open_whatsapp_notification(n),
        )
        whatsapp_btn.pack(side="right", padx=(4, 0))
        whatsapp_btn.bind("<Button-1>", lambda e: "break")

        # Copy button
        copy_btn = ctk.CTkButton(
            action_frame,
            text="📋",
            width=42, height=28,
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["accent_green"],
            text_color=COLORS["text_secondary"],
            font=FONTS["caption"], corner_radius=4,
            border_width=1, border_color=COLORS["border"],
            command=lambda n=notif: self._copy_notification(n),
        )
        copy_btn.pack(side="right", padx=(4, 0))
        copy_btn.bind("<Button-1>", lambda e: "break")

        # "✓ Read" button (opens the detail popup and disappears after marking read)
        read_btn = None
        if not is_read:
            read_btn = ctk.CTkButton(
                action_frame,
                text="✓ Read",
                width=54, height=28,
                fg_color="#FFFFFF",
                hover_color=COLORS["accent_green"],
                text_color=COLORS["text_secondary"],
                font=FONTS["caption"], corner_radius=4,
                border_width=1,
                border_color=COLORS["border"],
            )
            read_btn.configure(
                command=lambda n=notif, btn_ref=read_btn:
                    self._show_and_mark(n, btn_ref)
            )
            read_btn.pack(side="right", padx=(4, 0))
            read_btn.bind("<Button-1>", lambda e: "break")

        # Row hover effect
        def _highlight(_e):
            row.configure(fg_color=hover_bg)

        def _unhighlight(_e):
            row.configure(fg_color=bg)

        for widget in [row, action_frame]:
            widget.bind("<Enter>", _highlight)
            widget.bind("<Leave>", _unhighlight)

        # Click the row to open full notification detail popup.
        def _open(_e, n=notif):
            self._show_notif_detail(n)

        row.bind("<Button-1>", _open)
        for widget in row.winfo_children():
            if widget is not action_frame:
                widget.bind("<Button-1>", _open)

    def _show_notif_detail(self, notif: dict):
        """Show full notification message in a popup.

        FIX: grab_set() removed — it was blocking all click events on every
        other notification after the first popup was opened, making it appear
        as though only one popup would ever open.  Each popup is now tracked
        in self._open_popups so duplicates are raised rather than reopened.
        """
        import tkinter as tk

        notif_id = notif["id"]

        # If a popup for this notification is already open, just raise it
        existing = self._open_popups.get(notif_id)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except Exception:
                pass
            # Window gone — remove stale entry and fall through to create
            del self._open_popups[notif_id]

        cfg = NOTIF_CONFIG.get(notif["notif_type"], {
            "label": notif["notif_type"].replace("_", " ").title(),
            "icon":  "ℹ",
            "color": COLORS["text_secondary"],
        })
        sev_color    = SEVERITY_COLORS.get(notif["severity"], "#718096")
        loan_num     = notif.get("loan_number")   or "—"
        client_name  = notif.get("client_name")   or "—"
        client_nin   = notif.get("client_nin")    or "—"
        client_phone = notif.get("client_phone")  or "—"

        popup = tk.Toplevel(self)
        popup.title(f"{cfg['icon']} {cfg['label']}")
        popup.configure(bg=COLORS.get("bg_card", "#FFFFFF"))
        popup.resizable(False, False)

        # Track this popup; clean up the dict entry when it closes
        self._open_popups[notif_id] = popup
        popup.protocol(
            "WM_DELETE_WINDOW",
            lambda: (
                self._open_popups.pop(notif_id, None),
                popup.destroy(),
            ),
        )

        # Position centred over the app window
        popup.update_idletasks()
        pw, ph = 580, 400
        x = self.winfo_rootx() + (self.winfo_width()  - pw) // 2
        y = self.winfo_rooty() + (self.winfo_height() - ph) // 2
        popup.geometry(f"{pw}x{ph}+{x}+{y}")
        popup.attributes("-topmost", True)

        # ── Header bar ────────────────────────────────────────────────────
        hdr = tk.Frame(popup, bg=sev_color, height=46)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(
            hdr,
            text=f"{cfg['icon']}  {cfg['label']}  —  {notif['severity']}",
            bg=sev_color, fg="#FFFFFF",
            font=("Helvetica", 12, "bold"),
        ).pack(side="left", padx=16, pady=8)

        tk.Label(
            hdr,
            text=str(notif["notif_date"]),
            bg=sev_color, fg="#FFFFFF",
            font=("Helvetica", 10),
        ).pack(side="right", padx=16, pady=8)

        # ── Identity bar ──────────────────────────────────────────────────
        id_bg = COLORS.get("bg_input", "#F7FAFC")
        id_bar = tk.Frame(popup, bg=id_bg, height=30)
        id_bar.pack(fill="x")
        id_bar.pack_propagate(False)

        tk.Label(
            id_bar,
            text=(f"  Loan: {loan_num}     "
                  f"Client: {client_name}     "
                  f"NIN: {client_nin}     "
                  f"Phone: {client_phone}"),
            bg=id_bg,
            fg=COLORS.get("text_secondary", "#4A5568"),
            font=("Helvetica", 9),
            anchor="w",
        ).pack(side="left", padx=8, fill="y")

        # ── Message body ──────────────────────────────────────────────────
        body_frame = tk.Frame(popup, bg=id_bg)
        body_frame.pack(fill="both", expand=True, padx=12, pady=8)

        scrollbar = tk.Scrollbar(body_frame)
        scrollbar.pack(side="right", fill="y")

        body = tk.Text(
            body_frame,
            font=("Courier", 10),
            bg=id_bg,
            fg=COLORS.get("text_primary", "#1A202C"),
            wrap="word",
            relief="flat",
            bd=0,
            yscrollcommand=scrollbar.set,
            state="normal",
        )
        body.pack(side="left", fill="both", expand=True)
        body.insert("end", notif["message"])
        body.configure(state="disabled")
        scrollbar.config(command=body.yview)

        # ── Buttons ───────────────────────────────────────────────────────
        btn_frame = tk.Frame(
            popup, bg=COLORS.get("bg_card", "#FFFFFF"), pady=8)
        btn_frame.pack(fill="x", padx=12)

        def _close():
            self._open_popups.pop(notif_id, None)
            popup.destroy()

        tk.Button(
            btn_frame,
            text="Close",
            bg=COLORS.get("bg_input", "#F7FAFC"),
            fg=COLORS.get("text_secondary", "#4A5568"),
            font=("Helvetica", 10),
            relief="flat", bd=1,
            padx=16, pady=6,
            cursor="hand2",
            command=_close,
        ).pack(side="right", padx=(6, 0))

        if not notif["is_read"]:
            tk.Button(
                btn_frame,
                text="✓ Mark as read",
                bg=COLORS.get("accent_green", "#276749"),
                fg="#FFFFFF",
                font=("Helvetica", 10, "bold"),
                relief="flat", bd=0,
                padx=16, pady=6,
                cursor="hand2",
                command=lambda: (
                    self._mark_one_read(notif["id"]),
                    _close(),
                ),
            ).pack(side="right")

        popup.focus_force()
        # NOTE: grab_set() intentionally removed — it blocked all subsequent
        # notification click events until the first popup was closed.

    def _show_quick_message(self, text: str, duration_ms: int = 1500):
        """Show a small transient popup message near the top-right of the app."""
        import tkinter as tk

        try:
            msg = tk.Toplevel(self)
            msg.overrideredirect(True)
            msg.attributes("-topmost", True)
            label = tk.Label(
                msg, text=text,
                bg=COLORS.get("bg_card", "#FFFFFF"),
                fg=COLORS.get("text_primary", "#1A202C"),
                font=("Helvetica", 10), bd=1, relief="solid", padx=8, pady=6
            )
            label.pack()

            # Position near top-right of main window
            msg.update_idletasks()
            w = msg.winfo_width()
            h = msg.winfo_height()
            x = self.winfo_rootx() + max(16, self.winfo_width() - w - 40)
            y = self.winfo_rooty() + 40
            msg.geometry(f"{w}x{h}+{x}+{y}")

            # Auto-destroy after duration
            self.after(duration_ms, lambda: (msg.destroy() if msg.winfo_exists() else None))
        except Exception:
            # Fallback: print to console if UI popup fails
            print(text)

    def _open_whatsapp_notification(self, notif: dict):
        """Open WhatsApp Web for a notification message (non-blocking)."""
        try:
            from app.core.agents.whatsapp_quick import QuickWhatsApp
            import re

            loan = notif.get("loan_number") or ""
            client = notif.get("client_name") or ""
            phone = notif.get("client_phone") or ""
            msg_text = notif.get("message", "")

            # Try to extract an amount (UGX 123,456) from the notification message
            m = re.search(r"UGX\s*([0-9,]+)", msg_text)
            amount = float(m.group(1).replace(",", "")) if m else 0.0

            due_date = str(notif.get("notif_date") or "")
            days_until = 0

            full_message = QuickWhatsApp.format_reminder_for_whatsapp(
                loan_number=loan,
                client_name=client,
                amount_due=amount,
                due_date=due_date,
                days_until=days_until,
                message=msg_text,
            )

            ok = QuickWhatsApp.open_whatsapp_chat(phone, full_message)
            if ok:
                if getattr(QuickWhatsApp, "_last_opened", False):
                    self._show_quick_message(
                        "Opening WhatsApp and copying message to clipboard. Paste into the chat."
                    )
                else:
                    self._show_quick_message(
                        "Message copied to clipboard. Switch to WhatsApp Web and paste into the existing tab."
                    )
            else:
                self._show_quick_message("Could not open WhatsApp.")
        except Exception as e:
            self._show_quick_message(f"Error: {e}")

    def _copy_notification(self, notif: dict):
        """Copy the notification message (formatted) to clipboard."""
        try:
            from app.core.agents.whatsapp_quick import QuickWhatsApp
            import re

            loan = notif.get("loan_number") or ""
            client = notif.get("client_name") or ""
            msg_text = notif.get("message", "")

            m = re.search(r"UGX\s*([0-9,]+)", msg_text)
            amount = float(m.group(1).replace(",", "")) if m else 0.0

            due_date = str(notif.get("notif_date") or "")
            days_until = 0

            full_message = QuickWhatsApp.format_reminder_for_whatsapp(
                loan_number=loan,
                client_name=client,
                amount_due=amount,
                due_date=due_date,
                days_until=days_until,
                message=msg_text,
            )

            ok = QuickWhatsApp.copy_to_clipboard(full_message)
            if ok:
                self._show_quick_message("Message copied to clipboard!")
            else:
                self._show_quick_message("Could not copy message.")
        except Exception as e:
            self._show_quick_message(f"Error: {e}")

    def _mark_one_read(self, notif_id: int, button_widget=None):
        def run():
            try:
                from app.core.agents.background_agent import BackgroundAgent
                BackgroundAgent.mark_notification_read(notif_id)
                if button_widget is not None:
                    self.after(0, lambda: button_widget.destroy())
                else:
                    self.after(0, self._reload_notifications)
            except Exception as e:
                print(f"[Dashboard] mark_read error: {e}")
        threading.Thread(target=run, daemon=True).start()

    def _show_and_mark(self, notif: dict, button_widget=None):
        self._show_notif_detail(notif)
        self._mark_one_read(notif["id"], button_widget)

    def _show_notif_error(self, msg: str):
        for w in self.notif_container.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.notif_container,
            text=f"Could not load notifications: {msg}",
            font=FONTS["body_small"],
            text_color=COLORS["danger"],
        ).pack(pady=20)

    def _update_pagination_controls(self, total: int):
        """Update page label and prev/next button states and colours."""
        page_size   = self._notif_page_size
        total_pages = max(1, (total + page_size - 1) // page_size)
        page        = self._notif_page

        start = (page - 1) * page_size + 1
        end   = min(page * page_size, total)

        if total == 0:
            self.notif_page_label.configure(text="No notifications")
        else:
            self.notif_page_label.configure(
                text=f"Page {page} of {total_pages}  "
                     f"({start}–{end} of {total})")

        # Previous — white when enabled, greyed when disabled
        prev_enabled = page > 1
        self.notif_prev_btn.configure(
            state="normal" if prev_enabled else "disabled",
            fg_color="#FFFFFF" if prev_enabled else COLORS["bg_input"],
            text_color=(COLORS["text_secondary"] if prev_enabled
                        else COLORS["text_muted"]),
        )

        # Next — green when enabled, greyed when disabled
        next_enabled = page < total_pages
        self.notif_next_btn.configure(
            state="normal" if next_enabled else "disabled",
            fg_color=(COLORS["accent_green"] if next_enabled
                      else COLORS["bg_input"]),
            text_color="#FFFFFF" if next_enabled else COLORS["text_muted"],
        )

    # ══════════════════════════════════════════════════════════════════════════
    # Dashboard data fetch
    # ══════════════════════════════════════════════════════════════════════════

    def _fetch_and_update(self):
        try:
            from app.database.connection import get_db
            from app.core.models.loan    import Loan, LoanStatus
            from app.core.models.client  import Client
            from sqlalchemy              import text as sa_text

            with get_db() as db:
                dashboard_sql = sa_text("""
                    WITH loan_stats AS (
                        SELECT
                            COUNT(*) as total_loans,
                            COUNT(CASE WHEN status = 'active'    THEN 1 END) as active_loans,
                            COUNT(CASE WHEN status = 'pending'   THEN 1 END) as pending_loans,
                            COUNT(CASE WHEN status = 'approved'  THEN 1 END) as approved_loans,
                            COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_loans,
                            COUNT(CASE WHEN status = 'defaulted' THEN 1 END) as defaulted_loans,
                            SUM(CASE WHEN status IN ('active','approved')
                                     THEN principal_amount END)              as portfolio_value,
                            COUNT(CASE WHEN status = 'active'
                                         AND due_date < CURRENT_DATE
                                        THEN 1 END)                         as overdue_count
                        FROM loans
                    ),
                    client_stats AS (
                        SELECT COUNT(*) as total_clients
                        FROM   clients
                        WHERE  is_active = true
                    )
                    SELECT ls.*, cs.total_clients
                    FROM   loan_stats  ls
                    CROSS JOIN client_stats cs
                """)
                row = db.execute(dashboard_sql).fetchone()

            if row:
                status_counts = {
                    "active":    row.active_loans    or 0,
                    "pending":   row.pending_loans   or 0,
                    "approved":  row.approved_loans  or 0,
                    "completed": row.completed_loans or 0,
                    "defaulted": row.defaulted_loans or 0,
                }
                portfolio     = float(row.portfolio_value or 0)
                overdue_count = row.overdue_count  or 0
                client_count  = row.total_clients  or 0
            else:
                status_counts = {k: 0 for k in
                                 ["active","pending","approved","completed","defaulted"]}
                portfolio = overdue_count = client_count = 0

            def _update(
                portfolio=portfolio, status_counts=status_counts,
                overdue_count=overdue_count, client_count=client_count,
            ):
                try:
                    self.card_total.update_value(f"UGX {portfolio:,.0f}")
                    self.card_active.update_value(str(status_counts["active"]))
                    self.card_overdue.update_value(str(overdue_count))
                    self.card_clients.update_value(str(client_count))
                    for key, lbl in self.status_labels.items():
                        lbl.configure(text=str(status_counts.get(key, 0)))

                    # Show or hide the overdue banner (priority 2)
                    if overdue_count > 0:
                        banner_msg = (
                            f"⚠  {overdue_count} loan(s) are overdue — "
                            f"check Agent Notifications below"
                        )
                        self._show_reminder_banner(banner_msg, priority=2)
                    else:
                        self._show_reminder_banner(None, priority=2)

                except Exception as e:
                    print(f"[Dashboard] UI update error: {e}")

            self.after(0, _update)

        except Exception as e:
            print(f"[Dashboard] Fetch error: {e}")

    # ── Inline loans panel ─────────────────────────────────────────────────

    def _toggle_loans_panel(self, status):
        if self._active_status == status:
            self._active_status = None
            self._hide_loans_panel()
            self._reset_card_styles()
            return
        self._active_status = status
        self._reset_card_styles()
        self._highlight_active_card(status)
        self._show_loans_panel(status)

    def _reset_card_styles(self):
        for key, (card, color, bg_color) in self._status_cards.items():
            card.configure(fg_color=bg_color, border_width=2,
                           border_color=color)
            children = card.winfo_children()
            if len(children) >= 4:
                try:
                    children[1].configure(text_color=color)
                    children[2].configure(text_color="#555555")
                    children[3].configure(text_color=color)
                    if len(children) >= 5:
                        children[4].configure(text_color=color)
                except Exception:
                    pass

    def _highlight_active_card(self, status):
        card, color, _ = self._status_cards[status]
        card.configure(border_width=4, border_color=color, fg_color=color)
        for child in card.winfo_children():
            try:
                child.configure(text_color="#FFFFFF")
            except Exception:
                pass

    def _hide_loans_panel(self):
        if self._loans_panel and self._loans_panel.winfo_exists():
            self._loans_panel.destroy()
        self._loans_panel = None

    def _show_loans_panel(self, status):
        self._hide_loans_panel()
        cfg   = next(c for c in STATUS_CONFIG if c[0] == status)
        color = cfg[2]
        label = cfg[1]

        self._loans_panel = ctk.CTkFrame(
            self.content, fg_color=COLORS["bg_card"],
            corner_radius=12, border_width=2, border_color=color)
        self._loans_panel.grid(
            row=6, column=0, sticky="ew", padx=28, pady=(10, 0))
        self._loans_panel.columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(
            self._loans_panel, fg_color=color, corner_radius=0, height=42)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text=f"  {label} Loans",
                     font=FONTS["subheading"],
                     text_color="#FFFFFF").pack(
            side="left", padx=16, fill="y")
        ctk.CTkButton(hdr, text="✕  Close", width=80, height=28,
                      fg_color="transparent",
                      hover_color=color,
                      border_width=1, border_color="#FFFFFF",
                      text_color="#FFFFFF", font=FONTS["caption"],
                      corner_radius=6,
                      command=lambda: self._toggle_loans_panel(status)).pack(
            side="right", padx=12, pady=7)

        threading.Thread(
            target=self._load_panel_loans,
            args=(status, label, color, cfg[4]),
            daemon=True,
        ).start()

    def _load_panel_loans(self, status, label, color, hover_color):
        try:
            from app.database.connection import get_db
            from app.core.models.loan    import Loan, LoanStatus
            from app.core.models.client  import Client
            from sqlalchemy              import func

            with get_db() as db:
                rows = (
                    db.query(
                        Loan.id, Loan.loan_number, Loan.loan_type,
                        Loan.principal_amount, Loan.due_date,
                        Client.full_name,
                    )
                    .join(Client, Loan.client_id == Client.id)
                    .filter(Loan.status == LoanStatus(status))
                    .limit(10)
                    .all()
                )
                total = db.query(func.count(Loan.id)).filter(
                    Loan.status == LoanStatus(status)).scalar() or 0

            def _render(rows=rows, total=total):
                if not self._loans_panel or \
                        not self._loans_panel.winfo_exists():
                    return
                if not rows:
                    ctk.CTkLabel(
                        self._loans_panel,
                        text=f"No {label.lower()} loans found.",
                        font=FONTS["body"],
                        text_color=COLORS["text_muted"],
                    ).pack(pady=24)
                    return

                col_hdr = ctk.CTkFrame(
                    self._loans_panel,
                    fg_color=COLORS["bg_input"], height=32)
                col_hdr.pack(fill="x")
                col_hdr.pack_propagate(False)
                for i, (col_label, width) in enumerate([
                    ("Loan No.", 130), ("Client", 190),
                    ("Type", 150), ("Principal", 130), ("Due Date", 110),
                ]):
                    ctk.CTkLabel(
                        col_hdr, text=col_label, font=FONTS["badge"],
                        text_color=COLORS["text_muted"],
                        width=width, anchor="w",
                    ).pack(side="left",
                           padx=(16 if i == 0 else 0, 0))

                for i, row in enumerate(rows):
                    bg = (COLORS["bg_card"] if i % 2 == 0
                          else COLORS["bg_input"])
                    r  = ctk.CTkFrame(
                        self._loans_panel, fg_color=bg, height=36)
                    r.pack(fill="x")
                    r.pack_propagate(False)

                    # Explicit guard: handle both enum and raw-string loan_type
                    if row.loan_type is None:
                        lt = "—"
                    elif hasattr(row.loan_type, "value"):
                        lt = row.loan_type.value
                    else:
                        lt = str(row.loan_type)

                    for j, (cell_text, width) in enumerate([
                        (row.loan_number,                           130),
                        (row.full_name or "—",                     190),
                        (lt,                                        150),
                        (f"UGX {float(row.principal_amount):,.0f}", 130),
                        (str(row.due_date) if row.due_date else "—", 110),
                    ]):
                        ctk.CTkLabel(
                            r, text=cell_text, font=FONTS["body_small"],
                            text_color=COLORS["text_primary"],
                            width=width, anchor="w",
                        ).pack(side="left",
                               padx=(16 if j == 0 else 0, 0))

                if total > 10:
                    ctk.CTkLabel(
                        self._loans_panel,
                        text=(f"  … showing 10 of {total}. "
                              f"Go to Loans screen to see all."),
                        font=FONTS["body_small"],
                        text_color=COLORS["text_muted"],
                        anchor="w",
                    ).pack(fill="x", padx=16, pady=(6, 0))

                ctk.CTkButton(
                    self._loans_panel,
                    text=f"View all {total} {label.lower()} loans  →",
                    height=38, font=FONTS["button"],
                    fg_color=color, hover_color=hover_color,
                    text_color="#FFFFFF", corner_radius=0,
                    command=lambda: self._navigate("loans"),
                ).pack(fill="x", pady=(8, 0))

            self.after(0, _render)

        except Exception as e:
            self.after(0, lambda: (
                ctk.CTkLabel(
                    self._loans_panel,
                    text=f"Error: {e}",
                    font=FONTS["body_small"],
                    text_color=COLORS["danger"],
                ).pack(pady=12)
                if self._loans_panel
                and self._loans_panel.winfo_exists()
                else None
            ))

    # ── Reminder badge via ReminderService ────────────────────────────────

    def _load_reminder_badge(self):
        try:
            from app.core.agents.reminder_service import ReminderService
            counts = ReminderService.get_reminder_counts()
            total  = counts.get("total", 0)
            if total > 0:
                overdue = counts.get("overdue", 0)
                urgent  = counts.get("urgent",  0)
                parts   = []
                if overdue:
                    parts.append(f"{overdue} overdue")
                if urgent:
                    parts.append(f"{urgent} urgent")
                banner_msg = (
                    f"⚠  Payment reminders: {', '.join(parts)}  —  "
                    f"{total} loan(s) due soon"
                )
                self.after(
                    0,
                    lambda: self._show_reminder_banner(banner_msg, priority=1),
                )
            else:
                self.after(
                    0,
                    lambda: self._show_reminder_banner(None, priority=1),
                )
        except Exception:
            pass