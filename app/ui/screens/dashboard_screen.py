"""
app/ui/screens/dashboard_screen.py
────────────────────────────────────
Dashboard screen with:
  • Top stat cards (portfolio, active loans, overdue, clients)
  • Payment reminder notification banner (from ReminderService)
  • Clickable loan status cards that expand an inline filtered loan list
  • Recent repayments feed with loan number column
"""

import threading
import customtkinter as ctk
from app.ui.styles.theme import COLORS, FONTS
from app.ui.components.sidebar import Sidebar
from app.ui.components.stat_card import StatCard


# (key, label, accent_color, bg_color, hover_color)
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
        self._active_status = None   # tracks which status card is expanded
        self._loans_panel   = None   # reference to the inline loans panel
        self._build()
        self._load_stats()
        self._load_reminder_badge()

    # ── Navigation ─────────────────────────────────────────────────────────────

    def _navigate(self, screen: str):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    # ── Layout ─────────────────────────────────────────────────────────────────

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        Sidebar(self, "dashboard", self._navigate, self.current_user).grid(
            row=0, column=0, sticky="nsew")

        self.content = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["bg_primary"],
            scrollbar_button_color=COLORS["accent_green"],
            scrollbar_button_hover_color=COLORS["accent_green_dark"],
        )
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)

        # row 0  = green accent bar
        # row 1  = header (greeting + refresh)
        # row 2  = top stat cards
        # row 3  = reminder banner (hidden until reminders load)
        # row 4  = "Loan Status Overview" heading
        # row 5  = clickable status cards
        # row 6  = inline loans panel (dynamically added/removed)
        # row 7  = "Recent Repayments" heading
        # row 8  = repayments feed
        self._build_header()
        self._build_stat_cards()
        self._build_reminder_banner()
        self._build_loan_status_row()
        self._build_recent_activity()

    # ── Header ─────────────────────────────────────────────────────────────────

    def _build_header(self):
        # Thin green accent bar — in its own row so it never overlaps the title
        ctk.CTkFrame(self.content, fg_color=COLORS["accent_green"],
                     height=4, corner_radius=0).grid(
            row=0, column=0, sticky="ew")

        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.grid(row=1, column=0, sticky="ew", padx=28, pady=(20, 0))
        header.columnconfigure(1, weight=1)

        name = self.current_user.full_name if self.current_user else "User"
        ctk.CTkLabel(
            header,
            text=f"Good day,  {name}",
            font=FONTS["title"],
            text_color=COLORS["accent_green_dark"],
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text="Bingongold Credit  ·  Loans Management System",
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        ctk.CTkButton(
            header, text="↻  Refresh",
            width=110, height=34,
            font=FONTS["body_small"],
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["accent_green_dark"],
            text_color="#FFFFFF",
            corner_radius=8,
            command=self._load_stats,
        ).grid(row=0, column=2, sticky="e")

    # ── Top stat cards ─────────────────────────────────────────────────────────

    def _build_stat_cards(self):
        cards_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        cards_frame.grid(row=2, column=0, sticky="ew", padx=28, pady=(20, 0))
        for i in range(4):
            cards_frame.columnconfigure(i, weight=1)

        self.card_total = StatCard(
            cards_frame, "UGX", "Total Portfolio",
            "Loading...", accent=COLORS["accent_green"])
        self.card_total.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        self.card_active = StatCard(
            cards_frame, "✓", "Active Loans",
            "Loading...", accent=COLORS["accent_green_dark"])
        self.card_active.grid(row=0, column=1, padx=8, sticky="ew")

        self.card_overdue = StatCard(
            cards_frame, "!", "Overdue Loans",
            "Loading...", accent=COLORS["danger"])
        self.card_overdue.grid(row=0, column=2, padx=8, sticky="ew")

        self.card_clients = StatCard(
            cards_frame, "P", "Total Clients",
            "Loading...", accent=COLORS["accent_gold"])
        self.card_clients.grid(row=0, column=3, padx=(8, 0), sticky="ew")

    # ── Reminder banner ────────────────────────────────────────────────────────

    def _build_reminder_banner(self):
        """
        Gold warning banner — hidden by default.
        Shown automatically when ReminderService finds upcoming/overdue payments.
        """
        self.reminder_banner = ctk.CTkFrame(
            self.content,
            fg_color=COLORS["warning"],
            corner_radius=8,
        )
        # Not gridded yet — _show_reminder_banner() places it when needed
        self.reminder_label = ctk.CTkLabel(
            self.reminder_banner,
            text="",
            font=FONTS["body_small"],
            text_color=COLORS["text_on_gold"],
        )
        self.reminder_label.pack(padx=16, pady=(10, 4))

        ctk.CTkButton(
            self.reminder_banner,
            text="View Reminders & Alerts  →",
            height=28,
            font=FONTS["body_small"],
            fg_color=COLORS["accent_green_dark"],
            hover_color=COLORS["accent_green"],
            text_color="#FFFFFF",
            corner_radius=6,
            command=lambda: self._navigate("agent"),
        ).pack(padx=16, pady=(0, 10))

    def _show_reminder_banner(self, text: str):
        self.reminder_label.configure(text=text)
        self.reminder_banner.grid(
            row=3, column=0, sticky="ew", padx=28, pady=(12, 0))

    # ── Loan status overview ───────────────────────────────────────────────────

    def _build_loan_status_row(self):
        # Section header
        hdr_row = ctk.CTkFrame(self.content, fg_color="transparent")
        hdr_row.grid(row=4, column=0, sticky="ew", padx=28, pady=(28, 6))
        hdr_row.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr_row, text="Loan Status Overview",
            font=FONTS["heading"],
            text_color=COLORS["accent_green_dark"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            hdr_row,
            text="Click a card to view those loans ↓",
            font=FONTS["body_small"],
            text_color=COLORS["text_muted"],
            anchor="e",
        ).grid(row=0, column=1, sticky="e")

        # Cards row
        self.status_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self.status_frame.grid(row=5, column=0, sticky="ew", padx=28)
        for i in range(5):
            self.status_frame.columnconfigure(i, weight=1)

        self.status_labels = {}
        self._status_cards = {}

        for i, (key, label, color, bg_color, hover_color) in enumerate(STATUS_CONFIG):
            self._build_status_card(
                col=i,
                key=key,
                label=label,
                color=color,
                bg_color=bg_color,
                hover_color=hover_color,
            )

    def _build_status_card(self, col, key, label, color, bg_color, hover_color):
        card = ctk.CTkFrame(
            self.status_frame,
            fg_color=bg_color,
            corner_radius=12,
            border_width=2,
            border_color=color,
            cursor="hand2",
        )
        card.grid(row=0, column=col, padx=4, sticky="ew")

        # Top colour bar
        ctk.CTkFrame(card, fg_color=color, height=5,
                     corner_radius=0).pack(fill="x")

        # Down-arrow hint
        ctk.CTkLabel(
            card, text="↓",
            font=("Helvetica", 11, "bold"),
            text_color=color,
            anchor="e",
        ).pack(fill="x", padx=(0, 10), pady=(4, 0))

        # Status name
        ctk.CTkLabel(
            card, text=label,
            font=FONTS["body_small"],
            text_color="#555555",
            anchor="center",
        ).pack(pady=(0, 2))

        # Count
        count_lbl = ctk.CTkLabel(
            card, text="—",
            font=FONTS["subtitle"],
            text_color=color,
            anchor="center",
        )
        count_lbl.pack()

        # "tap to view" hint
        ctk.CTkLabel(
            card, text="tap to view",
            font=FONTS["caption"],
            text_color=color,
            anchor="center",
        ).pack(pady=(2, 10))

        self.status_labels[key] = count_lbl
        self._status_cards[key] = (card, color, bg_color)

        # Mouse bindings for hover and click
        def on_enter(_e):
            if self._active_status != key:
                card.configure(fg_color=hover_color)

        def on_leave(_e):
            if self._active_status != key:
                card.configure(fg_color=bg_color)

        def on_click(_e):
            self._toggle_loans_panel(key)

        for widget in [card] + card.winfo_children():
            widget.bind("<Enter>",    on_enter)
            widget.bind("<Leave>",    on_leave)
            widget.bind("<Button-1>", on_click)

    # ── Inline loans panel ─────────────────────────────────────────────────────

    def _toggle_loans_panel(self, status: str):
        """Toggle the inline loans panel for the clicked status card."""
        if self._active_status == status:
            # Same card clicked again — collapse
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
            for child in card.winfo_children():
                try:
                    child.configure(text_color=color if isinstance(child, ctk.CTkLabel) else None)
                except Exception:
                    pass
            # Re-apply correct per-widget colours
            children = card.winfo_children()
            if len(children) >= 4:
                try:
                    children[1].configure(text_color=color)   # arrow
                    children[2].configure(text_color="#555555") # label
                    children[3].configure(text_color=color)   # count
                    if len(children) >= 5:
                        children[4].configure(text_color=color)  # hint
                except Exception:
                    pass

    def _highlight_active_card(self, status: str):
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

    def _show_loans_panel(self, status: str):
        self._hide_loans_panel()

        cfg   = next(c for c in STATUS_CONFIG if c[0] == status)
        color = cfg[2]
        label = cfg[1]

        # Panel container placed at row 6
        self._loans_panel = ctk.CTkFrame(
            self.content,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
            border_width=2,
            border_color=color,
        )
        self._loans_panel.grid(row=6, column=0, sticky="ew",
                                padx=28, pady=(10, 0))
        self._loans_panel.columnconfigure(0, weight=1)

        # Panel header bar
        hdr = ctk.CTkFrame(self._loans_panel, fg_color=color,
                            corner_radius=0, height=42)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr, text=f"  {label} Loans",
            font=FONTS["subheading"],
            text_color="#FFFFFF",
        ).pack(side="left", padx=16, fill="y")

        ctk.CTkButton(
            hdr, text="✕  Close",
            width=80, height=28,
            fg_color="transparent",
            hover_color="#00000033",
            border_width=1,
            border_color="#FFFFFF",
            text_color="#FFFFFF",
            font=FONTS["caption"],
            corner_radius=6,
            command=lambda: self._toggle_loans_panel(status),
        ).pack(side="right", padx=12, pady=7)

        # Load and render loans
        try:
            from app.core.services.loan_service import LoanService
            from app.core.services.client_service import ClientService

            loans = LoanService.get_all_loans(status=status)

            if not loans:
                ctk.CTkLabel(
                    self._loans_panel,
                    text=f"No {label.lower()} loans found.",
                    font=FONTS["body"],
                    text_color=COLORS["text_muted"],
                ).pack(pady=24)
                return

            # Column header row
            col_hdr = ctk.CTkFrame(self._loans_panel, fg_color=COLORS["bg_input"],
                                    height=32)
            col_hdr.pack(fill="x")
            col_hdr.pack_propagate(False)

            columns = [
                ("Loan No.",   130),
                ("Client",     190),
                ("Type",       150),
                ("Principal",  130),
                ("Due Date",   110),
            ]
            for i, (col_label, width) in enumerate(columns):
                ctk.CTkLabel(
                    col_hdr, text=col_label,
                    font=FONTS["badge"],
                    text_color=COLORS["text_muted"],
                    width=width, anchor="w",
                ).pack(side="left",
                       padx=(16 if i == 0 else 0, 0))

            # Loan rows — max 10 displayed
            for i, loan in enumerate(loans[:10]):
                client = ClientService.get_client_by_id(loan.client_id)
                bg     = COLORS["bg_card"] if i % 2 == 0 else COLORS["bg_input"]
                row    = ctk.CTkFrame(self._loans_panel, fg_color=bg, height=36)
                row.pack(fill="x")
                row.pack_propagate(False)

                values = [
                    (loan.loan_number,                                 130),
                    (client.full_name if client else "—",              190),
                    (loan.loan_type.value if loan.loan_type else "—",  150),
                    (f"UGX {float(loan.principal_amount):,.0f}",       130),
                    (str(loan.due_date) if loan.due_date else "—",     110),
                ]
                for j, (val, width) in enumerate(values):
                    ctk.CTkLabel(
                        row, text=val,
                        font=FONTS["body_small"],
                        text_color=COLORS["text_primary"],
                        width=width, anchor="w",
                    ).pack(side="left",
                           padx=(16 if j == 0 else 0, 0))

            # "More" notice
            if len(loans) > 10:
                ctk.CTkLabel(
                    self._loans_panel,
                    text=f"  … showing 10 of {len(loans)}. "
                         "Go to the Loans screen to see all.",
                    font=FONTS["body_small"],
                    text_color=COLORS["text_muted"],
                    anchor="w",
                ).pack(fill="x", padx=16, pady=(6, 0))

            # Footer — navigate to full Loans screen
            ctk.CTkButton(
                self._loans_panel,
                text=f"View all {len(loans)} {label.lower()} loans  →",
                height=38,
                font=FONTS["button"],
                fg_color=color,
                hover_color=cfg[4],
                text_color="#FFFFFF",
                corner_radius=0,
                command=lambda: self._navigate("loans"),
            ).pack(fill="x", pady=(8, 0))

        except Exception as e:
            ctk.CTkLabel(
                self._loans_panel,
                text=f"Error loading loans: {e}",
                font=FONTS["body_small"],
                text_color=COLORS["danger"],
            ).pack(pady=12)

    # ── Recent repayments ──────────────────────────────────────────────────────

    def _build_recent_activity(self):
        ctk.CTkLabel(
            self.content, text="Recent Repayments",
            font=FONTS["heading"],
            text_color=COLORS["accent_green_dark"],
            anchor="w",
        ).grid(row=7, column=0, sticky="w", padx=28, pady=(28, 8))

        self.activity_frame = ctk.CTkFrame(
            self.content,
            fg_color=COLORS["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
        )
        self.activity_frame.grid(row=8, column=0, sticky="ew",
                                  padx=28, pady=(0, 28))
        self.activity_frame.columnconfigure(0, weight=1)

        self._render_activity_header()
        ctk.CTkLabel(
            self.activity_frame, text="Loading…",
            font=FONTS["body"],
            text_color=COLORS["text_muted"],
        ).pack(pady=20)

    def _render_activity_header(self):
        hdr = ctk.CTkFrame(
            self.activity_frame,
            fg_color=COLORS["accent_green"],
            corner_radius=0,
            height=36,
        )
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        for col_text, width in [
            ("Receipt",  170),
            ("Loan No.", 140),
            ("Amount",   130),
            ("Date",     100),
        ]:
            ctk.CTkLabel(
                hdr, text=col_text,
                font=FONTS["badge"],
                text_color="#FFFFFF",
                width=width,
            ).pack(side="left",
                   padx=(16 if col_text == "Receipt" else 0, 0))

    # ── Data loading ───────────────────────────────────────────────────────────

    def _load_stats(self):
        try:
            from app.core.services.loan_service import LoanService
            from app.core.services.client_service import ClientService
            from app.core.services.repayment_service import RepaymentService

            portfolio    = LoanService.total_portfolio_value()
            counts       = LoanService.count_by_status()
            overdue      = len(LoanService.get_overdue_loans())
            client_count = ClientService.count_clients()

            # Top stat cards
            if hasattr(self, "card_total"):
                self.card_total.update_value(f"UGX {portfolio:,.0f}")
            if hasattr(self, "card_active"):
                self.card_active.update_value(str(counts.get("active", 0)))
            if hasattr(self, "card_overdue"):
                self.card_overdue.update_value(str(overdue))
            if hasattr(self, "card_clients"):
                self.card_clients.update_value(str(client_count))

            # Status card counts
            for key, lbl in self.status_labels.items():
                lbl.configure(text=str(counts.get(key, 0)))

            # If an inline panel is open, refresh it
            if self._active_status:
                self._show_loans_panel(self._active_status)

            # Rebuild recent repayments feed
            for w in self.activity_frame.winfo_children():
                w.destroy()
            self._render_activity_header()

            try:
                all_loans = {l.id: l for l in LoanService.get_all_loans()}
            except Exception:
                all_loans = {}

            recent = RepaymentService.get_all_recent_repayments(limit=8)

            if not recent:
                ctk.CTkLabel(
                    self.activity_frame,
                    text="No repayments recorded yet.",
                    font=FONTS["body"],
                    text_color=COLORS["text_muted"],
                ).pack(pady=20)
            else:
                for i, r in enumerate(recent):
                    bg  = COLORS["bg_card"] if i % 2 == 0 else COLORS["bg_input"]
                    row = ctk.CTkFrame(self.activity_frame, fg_color=bg, height=38)
                    row.pack(fill="x")
                    row.pack_propagate(False)

                    loan = all_loans.get(r.loan_id)

                    for text, width, color in [
                        (r.receipt_number,                        170, COLORS["text_primary"]),
                        (loan.loan_number if loan else "—",        140, COLORS["text_secondary"]),
                        (f"UGX {float(r.amount):,.0f}",           130, COLORS["accent_green_dark"]),
                        (str(r.payment_date),                     100, COLORS["text_muted"]),
                    ]:
                        ctk.CTkLabel(
                            row, text=text,
                            font=FONTS["body_small"],
                            text_color=color,
                            width=width,
                        ).pack(side="left",
                               padx=(16 if width == 170 else 0, 0))

        except Exception as e:
            print(f"[Dashboard] Error loading stats: {e}")

    # ── Reminder badge (runs in background thread) ─────────────────────────────

    def _load_reminder_badge(self):
        def run():
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
                pass   # ReminderService not yet available — silently skip

        threading.Thread(target=run, daemon=True).start()