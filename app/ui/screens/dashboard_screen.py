"""
app/ui/screens/dashboard_screen.py
────────────────────────────────────
Performance fixes:
  1. All DB queries run in ONE background thread call
  2. Single combined query instead of 4 separate ones
  3. self.after() used for all widget updates from background
  4. refresh() reuses cached widgets — never rebuilds
"""

import threading
import customtkinter as ctk
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


class DashboardScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master         = master
        self.current_user   = master.current_user
        self._active_status = None
        self._loans_panel   = None
        self._build()
        # Load data once in background after UI is drawn
        threading.Thread(target=self._fetch_and_update, daemon=True).start()
        threading.Thread(target=self._load_reminder_badge, daemon=True).start()

    # ── Refresh — called by AppRoot on every return visit ─────────────────

    def refresh(self):
        threading.Thread(target=self._fetch_and_update, daemon=True).start()
        threading.Thread(target=self._load_reminder_badge, daemon=True).start()

    def _navigate(self, screen):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    # ── Build UI skeleton (no DB calls here) ──────────────────────────────

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
        self._build_recent_activity()

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
        ctk.CTkLabel(header, text="Bingongold Credit  ·  Loans Management System",
                     font=FONTS["body"],
                     text_color=COLORS["text_secondary"]).grid(
            row=1, column=0, sticky="w", pady=(4, 0))
        ctk.CTkButton(header, text="↻  Refresh", width=110, height=34,
                      font=FONTS["body_small"],
                      fg_color=COLORS["accent_green"],
                      hover_color=COLORS["accent_green_dark"],
                      text_color="#FFFFFF", corner_radius=8,
                      command=lambda: self.master.force_refresh("dashboard")).grid(row=0, column=2, sticky="e")

    def _build_stat_cards(self):
        cf = ctk.CTkFrame(self.content, fg_color="transparent")
        cf.grid(row=2, column=0, sticky="ew", padx=28, pady=(20, 0))
        for i in range(4):
            cf.columnconfigure(i, weight=1)

        self.card_total   = StatCard(cf, "UGX", "Total Portfolio",   "—", accent=COLORS["accent_green"])
        self.card_active  = StatCard(cf, "✓",   "Active Loans",      "—", accent=COLORS["accent_green_dark"])
        self.card_overdue = StatCard(cf, "!",   "Overdue Loans",     "—", accent=COLORS["danger"])
        self.card_clients = StatCard(cf, "P",   "Total Clients",     "—", accent=COLORS["accent_gold"])

        self.card_total.grid(row=0,   column=0, padx=(0, 8), sticky="ew")
        self.card_active.grid(row=0,  column=1, padx=8,      sticky="ew")
        self.card_overdue.grid(row=0, column=2, padx=8,      sticky="ew")
        self.card_clients.grid(row=0, column=3, padx=(8, 0), sticky="ew")

    def _build_reminder_banner(self):
        self.reminder_banner = ctk.CTkFrame(self.content,
                                             fg_color=COLORS["warning"],
                                             corner_radius=8)
        self.reminder_label  = ctk.CTkLabel(self.reminder_banner, text="",
                                             font=FONTS["body_small"],
                                             text_color=COLORS["text_on_gold"])
        self.reminder_label.pack(padx=16, pady=(10, 4))
        ctk.CTkButton(self.reminder_banner, text="View Reminders & Alerts  →",
                      height=28, font=FONTS["body_small"],
                      fg_color=COLORS["accent_green_dark"],
                      hover_color=COLORS["accent_green"],
                      text_color="#FFFFFF", corner_radius=6,
                      command=lambda: self._navigate("agent")).pack(
            padx=16, pady=(0, 10))

    def _show_reminder_banner(self, text):
        self.reminder_label.configure(text=text)
        self.reminder_banner.grid(row=3, column=0, sticky="ew", padx=28, pady=(12, 0))

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

        self.status_labels = {}
        self._status_cards = {}
        for i, (key, label, color, bg, hover) in enumerate(STATUS_CONFIG):
            self._build_status_card(i, key, label, color, bg, hover)

    def _build_status_card(self, col, key, label, color, bg_color, hover_color):
        card = ctk.CTkFrame(self.status_frame, fg_color=bg_color,
                             corner_radius=12, border_width=2,
                             border_color=color, cursor="hand2")
        card.grid(row=0, column=col, padx=4, sticky="ew")
        ctk.CTkFrame(card, fg_color=color, height=5, corner_radius=0).pack(fill="x")
        ctk.CTkLabel(card, text="↓", font=("Helvetica", 11, "bold"),
                     text_color=color, anchor="e").pack(fill="x", padx=(0, 10), pady=(4, 0))
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

    def _build_recent_activity(self):
        ctk.CTkLabel(self.content, text="Recent Repayments",
                     font=FONTS["heading"],
                     text_color=COLORS["accent_green_dark"],
                     anchor="w").grid(row=7, column=0, sticky="w",
                                      padx=28, pady=(28, 8))
        self.activity_frame = ctk.CTkFrame(self.content, fg_color=COLORS["bg_card"],
                                            corner_radius=10, border_width=1,
                                            border_color=COLORS["border"])
        self.activity_frame.grid(row=8, column=0, sticky="ew", padx=28, pady=(0, 28))
        self.activity_frame.columnconfigure(0, weight=1)
        self._render_activity_header()
        ctk.CTkLabel(self.activity_frame, text="Loading…",
                     font=FONTS["body"],
                     text_color=COLORS["text_muted"]).pack(pady=20)

    def _render_activity_header(self):
        hdr = ctk.CTkFrame(self.activity_frame, fg_color=COLORS["accent_green"],
                            corner_radius=0, height=36)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        for col_text, width in [("Receipt",170),("Loan No.",140),("Amount",130),("Date",100)]:
            ctk.CTkLabel(hdr, text=col_text, font=FONTS["badge"],
                         text_color="#FFFFFF", width=width).pack(
                side="left", padx=(16 if col_text=="Receipt" else 0, 0))

    # ── Single combined DB fetch — runs in background thread ──────────────

    def _fetch_and_update(self):
        """
        ONE background thread does ALL database work.
        Optimized: Single query with CTEs for all dashboard metrics.
        UI updated via self.after() on the main thread.
        """
        try:
            from app.database.connection import get_db
            from app.core.models.loan       import Loan, LoanStatus
            from app.core.models.client     import Client
            from app.core.models.repayment  import Repayment
            from sqlalchemy                 import func, text

            with get_db() as db:
                # ── Single optimized query with CTEs ────────────────────────
                dashboard_sql = text("""
                    WITH loan_stats AS (
                        SELECT 
                            COUNT(*) as total_loans,
                            COUNT(CASE WHEN status = 'active' THEN 1 END) as active_loans,
                            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_loans,
                            COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_loans,
                            COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_loans,
                            COUNT(CASE WHEN status = 'defaulted' THEN 1 END) as defaulted_loans,
                            COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected_loans,
                            SUM(CASE WHEN status IN ('active', 'approved') THEN principal_amount END) as portfolio_value,
                            COUNT(CASE WHEN status = 'active' AND due_date < CURRENT_DATE THEN 1 END) as overdue_count
                        FROM loans
                    ),
                    client_stats AS (
                        SELECT COUNT(*) as total_clients FROM clients WHERE is_active = true
                    ),
                    recent_repayments AS (
                        SELECT 
                            r.receipt_number,
                            r.amount,
                            r.payment_date,
                            l.loan_number
                        FROM repayments r
                        JOIN loans l ON r.loan_id = l.id
                        ORDER BY r.created_at DESC
                        LIMIT 8
                    )
                    SELECT 
                        ls.*,
                        cs.total_clients,
                        rr.receipt_number,
                        rr.amount,
                        rr.payment_date,
                        rr.loan_number
                    FROM loan_stats ls
                    CROSS JOIN client_stats cs
                    LEFT JOIN LATERAL (
                        SELECT * FROM recent_repayments
                    ) rr ON true
                """)
                
                result = db.execute(dashboard_sql).fetchall()
                
                # Parse results
                if result:
                    row = result[0]
                    status_counts = {
                        'active': row.active_loans or 0,
                        'pending': row.pending_loans or 0,
                        'approved': row.approved_loans or 0,
                        'completed': row.completed_loans or 0,
                        'defaulted': row.defaulted_loans or 0,
                        'rejected': row.rejected_loans or 0,
                    }
                    
                    portfolio = float(row.portfolio_value or 0)
                    overdue_count = row.overdue_count or 0
                    client_count = row.total_clients or 0
                    
                    # Get recent repayments (multiple rows)
                    recent = []
                    for r in result:
                        if r.receipt_number:
                            recent.append((
                                r.receipt_number,
                                float(r.amount),
                                str(r.payment_date),
                                r.loan_number
                            ))
                else:
                    status_counts = {status: 0 for status in ['active', 'pending', 'approved', 'completed', 'defaulted', 'rejected']}
                    portfolio = 0
                    overdue_count = 0
                    client_count = 0
                    recent = []

            # ── Update UI on main thread ───────────────────────────────
            def _update(
                portfolio=portfolio, status_counts=status_counts,
                overdue_count=overdue_count, client_count=client_count,
                recent=recent,
            ):
                try:
                    # ── Update stat cards (just text, no rebuild) ──────────
                    self.card_total.update_value(f"UGX {float(portfolio):,.0f}")
                    self.card_active.update_value(str(status_counts.get("active", 0)))
                    self.card_overdue.update_value(str(overdue_count))
                    self.card_clients.update_value(str(client_count))

                    # ── Update status card counts (just text) ──────────────
                    for key, lbl in self.status_labels.items():
                        lbl.configure(text=str(status_counts.get(key, 0)))

                    # ── Only rebuild activity frame if data changed ─────────
                    # Compare new receipts vs what is currently displayed
                    new_receipts = [r[0] for r in recent]
                    current_receipts = getattr(self, "_last_receipts", None)

                    if new_receipts != current_receipts:
                        self._last_receipts = new_receipts
                        for w in self.activity_frame.winfo_children():
                            w.destroy()
                        self._render_activity_header()

                        if not recent:
                            ctk.CTkLabel(
                                self.activity_frame,
                                text="No repayments recorded yet.",
                                font=FONTS["body"],
                                text_color=COLORS["text_muted"],
                            ).pack(pady=20)
                        else:
                            for i, (receipt, amount, pay_date, loan_num) in enumerate(recent):
                                bg  = COLORS["bg_card"] if i % 2 == 0 else COLORS["bg_input"]
                                row = ctk.CTkFrame(
                                    self.activity_frame, fg_color=bg, height=38)
                                row.pack(fill="x")
                                row.pack_propagate(False)
                                for text, width, color in [
                                    (receipt,              170, COLORS["text_primary"]),
                                    (loan_num or "—",      140, COLORS["text_secondary"]),
                                    (f"UGX {amount:,.0f}", 130, COLORS["accent_green_dark"]),
                                    (pay_date,             100, COLORS["text_muted"]),
                                ]:
                                    ctk.CTkLabel(
                                        row, text=text,
                                        font=FONTS["body_small"],
                                        text_color=color,
                                        width=width,
                                    ).pack(side="left",
                                           padx=(16 if width == 170 else 0, 0))
                    # If data unchanged — show cached widgets as-is (instant)

                except Exception as e:
                    print(f"[Dashboard] UI update error: {e}")

            self.after(0, _update)

            # ── Reminder badge ─────────────────────────────────────────
            if overdue_count > 0:
                text = f"⚠  {overdue_count} loan(s) are overdue — check AI Agent for alerts"
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
            card.configure(fg_color=bg_color, border_width=2, border_color=color)
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

        self._loans_panel = ctk.CTkFrame(self.content, fg_color=COLORS["bg_card"],
                                          corner_radius=12, border_width=2,
                                          border_color=color)
        self._loans_panel.grid(row=6, column=0, sticky="ew", padx=28, pady=(10, 0))
        self._loans_panel.columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(self._loans_panel, fg_color=color,
                            corner_radius=0, height=42)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text=f"  {label} Loans",
                     font=FONTS["subheading"],
                     text_color="#FFFFFF").pack(side="left", padx=16, fill="y")
        ctk.CTkButton(hdr, text="✕  Close", width=80, height=28,
                      fg_color="transparent",
                      hover_color=color,
                      border_width=1, border_color="#FFFFFF",
                      text_color="#FFFFFF", font=FONTS["caption"],
                      corner_radius=6,
                      command=lambda: self._toggle_loans_panel(status)).pack(
            side="right", padx=12, pady=7)

        # Load loans for this panel in background
        threading.Thread(
            target=self._load_panel_loans,
            args=(status, label, color, cfg[4]),
            daemon=True,
        ).start()

    def _load_panel_loans(self, status, label, color, hover_color):
        """Load loans for inline panel in background."""
        try:
            from app.database.connection import get_db
            from app.core.models.loan   import Loan, LoanStatus
            from app.core.models.client import Client
            from sqlalchemy             import func

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
                if not self._loans_panel or not self._loans_panel.winfo_exists():
                    return
                if not rows:
                    ctk.CTkLabel(self._loans_panel,
                                 text=f"No {label.lower()} loans found.",
                                 font=FONTS["body"],
                                 text_color=COLORS["text_muted"]).pack(pady=24)
                    return

                col_hdr = ctk.CTkFrame(self._loans_panel,
                                        fg_color=COLORS["bg_input"], height=32)
                col_hdr.pack(fill="x")
                col_hdr.pack_propagate(False)
                for i, (col_label, width) in enumerate([
                    ("Loan No.", 130), ("Client", 190),
                    ("Type", 150), ("Principal", 130), ("Due Date", 110)
                ]):
                    ctk.CTkLabel(col_hdr, text=col_label, font=FONTS["badge"],
                                 text_color=COLORS["text_muted"],
                                 width=width, anchor="w").pack(
                        side="left", padx=(16 if i == 0 else 0, 0))

                for i, row in enumerate(rows):
                    bg = COLORS["bg_card"] if i % 2 == 0 else COLORS["bg_input"]
                    r  = ctk.CTkFrame(self._loans_panel, fg_color=bg, height=36)
                    r.pack(fill="x")
                    r.pack_propagate(False)
                    lt = row.loan_type.value if row.loan_type else "—"
                    for text, width in [
                        (row.loan_number,                          130),
                        (row.full_name or "—",                    190),
                        (lt,                                       150),
                        (f"UGX {float(row.principal_amount):,.0f}", 130),
                        (str(row.due_date) if row.due_date else "—", 110),
                    ]:
                        ctk.CTkLabel(r, text=text, font=FONTS["body_small"],
                                     text_color=COLORS["text_primary"],
                                     width=width, anchor="w").pack(
                            side="left", padx=(16 if width == 130 and text == row.loan_number else 0, 0))

                if total > 10:
                    ctk.CTkLabel(self._loans_panel,
                                 text=f"  … showing 10 of {total}. Go to Loans screen to see all.",
                                 font=FONTS["body_small"],
                                 text_color=COLORS["text_muted"],
                                 anchor="w").pack(fill="x", padx=16, pady=(6, 0))

                ctk.CTkButton(self._loans_panel,
                              text=f"View all {total} {label.lower()} loans  →",
                              height=38, font=FONTS["button"],
                              fg_color=color, hover_color=hover_color,
                              text_color="#FFFFFF", corner_radius=0,
                              command=lambda: self._navigate("loans")).pack(
                    fill="x", pady=(8, 0))

            self.after(0, _render)

        except Exception as e:
            self.after(0, lambda: ctk.CTkLabel(
                self._loans_panel,
                text=f"Error: {e}",
                font=FONTS["body_small"],
                text_color=COLORS["danger"],
            ).pack(pady=12) if self._loans_panel and self._loans_panel.winfo_exists() else None)

    # ── ReminderService badge (full version from original) ─────────────────

    def _load_reminder_badge(self):
        """Checks ReminderService in background and shows banner if needed."""
        try:
            from app.core.agents.reminder_service import ReminderService
            counts  = ReminderService.get_reminder_counts()
            total   = counts.get("total", 0)
            if total > 0:
                overdue = counts.get("overdue", 0)
                urgent  = counts.get("urgent", 0)
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
            pass   # ReminderService not available — silently skip