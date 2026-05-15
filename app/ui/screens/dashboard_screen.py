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
"""

import threading
import customtkinter as ctk
from datetime import date, timedelta
from app.ui.styles.theme import COLORS, FONTS
from app.ui.components.sidebar import Sidebar
from app.ui.components.stat_card import StatCard

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
        self._notif_page_size   = 25
        self._notif_filter      = "all"   # "all" | "week" | "unread"
        self._notif_total       = 0

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
                                      accent=COLORS["accent_green_dark"])
        self.card_overdue  = StatCard(cf, "!",   "Overdue Loans",    "—",
                                      accent=COLORS["danger"])
        self.card_clients  = StatCard(cf, "P",   "Total Clients",    "—",
                                      accent=COLORS["accent_gold"])

        self.card_total.grid(row=0,   column=0, padx=(0, 8), sticky="ew")
        self.card_active.grid(row=0,  column=1, padx=8,      sticky="ew")
        self.card_overdue.grid(row=0, column=2, padx=8,      sticky="ew")
        self.card_clients.grid(row=0, column=3, padx=(8, 0), sticky="ew")

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

    def _show_reminder_banner(self, text):
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
    # Notifications panel  (replaces Recent Repayments)
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
            from sqlalchemy import text

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
                count_sql = text(f"""
                    SELECT COUNT(*)
                    FROM   agent_notifications an
                    {where_sql}
                """)
                total = db.execute(count_sql, params).scalar() or 0

                # Fetch page — join loans + clients for identity fields
                data_sql = text(f"""
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
            ("Type",        120),
            ("Loan No.",     90),
            ("Client",      120),
            ("NIN",         110),
            ("Message",     200),
            ("Date",         90),
            ("Severity",     72),
            ("",             68),
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
        """Render a single notification row."""
        cfg       = NOTIF_CONFIG.get(notif["notif_type"], {
            "label": notif["notif_type"].replace("_", " ").title(),
            "icon":  "ℹ",
            "color": COLORS["text_secondary"],
        })
        sev_color = SEVERITY_COLORS.get(
            notif["severity"], COLORS["text_muted"])
        is_read   = notif["is_read"]

        # Row background
        bg = COLORS["bg_card"] if index % 2 == 0 else COLORS["bg_input"]
        if not is_read:
            bg = "#F0FAF0" if index % 2 == 0 else "#E8F5E8"

        # Fixed-height compact row — 38px keeps all rows uniform
        row = ctk.CTkFrame(
            self.notif_container,
            fg_color=bg,
            corner_radius=0,
            height=38,
        )
        row.pack(fill="x")
        row.pack_propagate(False)   # enforce fixed height

        # Left accent bar (4px wide, severity colour)
        ctk.CTkFrame(
            row, fg_color=sev_color, width=4, corner_radius=0,
        ).pack(side="left", fill="y")

        # Unread dot — use bg color to "hide" it when read (transparent not allowed)
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

        # Loan number — green, compact
        loan_num = notif.get("loan_number") or "—"
        ctk.CTkLabel(
            row,
            text=loan_num,
            font=FONTS["caption"],
            text_color=COLORS["accent_green_dark"],
            width=90,
            anchor="w",
        ).pack(side="left", padx=(0, 4))

        # Client name
        client_name = notif.get("client_name") or "—"
        ctk.CTkLabel(
            row,
            text=client_name[:18],
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

        # Message — first line, truncated, clickable
        first_line = notif["message"].split("\n")[0][:38]
        if len(notif["message"].split("\n")[0]) > 38:
            first_line += "…"

        ctk.CTkButton(
            row,
            text=first_line,
            font=FONTS["body_small"],
            text_color=(COLORS["text_primary"] if not is_read
                        else COLORS["text_secondary"]),
            fg_color="transparent",
            hover_color=COLORS["bg_input"],
            anchor="w",
            width=200,
            height=30,
            command=lambda n=notif: self._show_notif_detail(n),
        ).pack(side="left", padx=(0, 8))

        # Date
        ctk.CTkLabel(
            row,
            text=str(notif["notif_date"]),
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            width=90,
            anchor="w",
        ).pack(side="left", padx=(0, 8))

        # Severity badge — small white pill with coloured text
        ctk.CTkLabel(
            row,
            text=notif["severity"],
            font=FONTS["caption"],
            text_color=sev_color,
            fg_color=COLORS["bg_card"],
            corner_radius=4,
            width=72,
        ).pack(side="left", padx=(0, 6))

        # Mark read button — white background, green on hover
        if not is_read:
            ctk.CTkButton(
                row,
                text="✓ Read",
                width=60, height=24,
                fg_color="#FFFFFF",
                hover_color=COLORS["accent_green"],
                text_color=COLORS["text_secondary"],
                font=FONTS["caption"],
                corner_radius=4,
                border_width=1,
                border_color=COLORS["border"],
                command=lambda nid=notif["id"]: self._mark_one_read(nid),
            ).pack(side="right", padx=8)

    def _show_notif_detail(self, notif: dict):
        """Show full notification message in a popup."""
        import tkinter as tk

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

        # Use standard tk.Toplevel — reliable on all platforms including Linux
        popup = tk.Toplevel(self)
        popup.title(f"{cfg['icon']} {cfg['label']}")
        popup.configure(bg=COLORS.get("bg_card", "#FFFFFF"))
        popup.resizable(False, False)

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

        tk.Button(
            btn_frame,
            text="Close",
            bg=COLORS.get("bg_input", "#F7FAFC"),
            fg=COLORS.get("text_secondary", "#4A5568"),
            font=("Helvetica", 10),
            relief="flat", bd=1,
            padx=16, pady=6,
            cursor="hand2",
            command=popup.destroy,
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
                    popup.destroy(),
                ),
            ).pack(side="right")

        # ── Show and grab ─────────────────────────────────────────────────
        popup.focus_force()
        popup.grab_set()
        popup.wait_window()

    def _mark_one_read(self, notif_id: int):
        def run():
            try:
                from app.core.agents.background_agent import BackgroundAgent
                BackgroundAgent.mark_notification_read(notif_id)
                self.after(0, self._reload_notifications)
            except Exception as e:
                print(f"[Dashboard] mark_read error: {e}")
        threading.Thread(target=run, daemon=True).start()

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
            from sqlalchemy              import text

            with get_db() as db:
                dashboard_sql = text("""
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
                except Exception as e:
                    print(f"[Dashboard] UI update error: {e}")

            self.after(0, _update)

            if overdue_count > 0:
                text = (f"⚠  {overdue_count} loan(s) are overdue — "
                        f"check Agent Notifications below")
                self.after(0, lambda: self._show_reminder_banner(text))

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
                    lt = row.loan_type.value if row.loan_type else "—"
                    for j, (text, width) in enumerate([
                        (row.loan_number,                           130),
                        (row.full_name or "—",                     190),
                        (lt,                                        150),
                        (f"UGX {float(row.principal_amount):,.0f}", 130),
                        (str(row.due_date) if row.due_date else "—", 110),
                    ]):
                        ctk.CTkLabel(
                            r, text=text, font=FONTS["body_small"],
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
                text = (
                    f"⚠  Payment reminders: {', '.join(parts)}  —  "
                    f"{total} loan(s) due soon"
                )
                self.after(0, lambda: self._show_reminder_banner(text))
        except Exception:
            pass