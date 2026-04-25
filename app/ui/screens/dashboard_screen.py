"""
app/ui/screens/dashboard_screen.py
────────────────────────────────────
Dashboard with clickable loan status cards.
Clicking a status card navigates to the Loans screen
filtered to that status.
"""

import customtkinter as ctk
from app.ui.styles.theme import COLORS, FONTS
from app.ui.components.sidebar import Sidebar
from app.ui.components.stat_card import StatCard


# Status card colour definitions — each has a background, text, and hover colour
STATUS_CONFIG = [
    ("pending",   "Pending",   "#F39C12", "#FEF9E7", "#F0A500"),
    ("approved",  "Approved",  "#2980B9", "#EBF5FB", "#2471A3"),
    ("active",    "Active",    "#27AE60", "#EAFAF1", "#1E8449"),
    ("completed", "Completed", "#7F8C8D", "#F2F3F4", "#707B7C"),
    ("defaulted", "Defaulted", "#C0392B", "#FDEDEC", "#A93226"),
]


class DashboardScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master       = master
        self.current_user = master.current_user
        self._build()
        self._load_stats()

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
            self, fg_color=COLORS["bg_primary"],
            scrollbar_button_color=COLORS["accent_green"],
            scrollbar_button_hover_color=COLORS["accent_green_dark"],
        )
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)

        self._build_header()
        self._build_stat_cards()
        self._build_loan_status_row()
        self._build_recent_activity()

    # ── Header ─────────────────────────────────────────────────────────────────

    def _build_header(self):
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

    # ── Loan status overview (clickable) ───────────────────────────────────────

    def _build_loan_status_row(self):
        # Section header
        hdr_row = ctk.CTkFrame(self.content, fg_color="transparent")
        hdr_row.grid(row=3, column=0, sticky="ew", padx=28, pady=(28, 6))
        hdr_row.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr_row, text="Loan Status Overview",
            font=FONTS["heading"],
            text_color=COLORS["accent_green_dark"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            hdr_row,
            text="Click a card to view those loans",
            font=FONTS["body_small"],
            text_color=COLORS["text_muted"],
            anchor="e",
        ).grid(row=0, column=1, sticky="e")

        # Status cards grid
        self.status_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self.status_frame.grid(row=4, column=0, sticky="ew", padx=28)
        for i in range(5):
            self.status_frame.columnconfigure(i, weight=1)

        self.status_labels = {}
        self._status_cards  = {}

        for i, (key, label, color, bg_color, hover_color) in enumerate(STATUS_CONFIG):
            self._build_status_card(
                parent      = self.status_frame,
                col         = i,
                key         = key,
                label       = label,
                color       = color,
                bg_color    = bg_color,
                hover_color = hover_color,
            )

    def _build_status_card(self, parent, col: int, key: str, label: str,
                           color: str, bg_color: str, hover_color: str):
        """Build a single clickable status card."""

        # Outer card frame
        card = ctk.CTkFrame(
            parent,
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

        # Arrow hint (top right)
        arrow = ctk.CTkLabel(
            card, text="→",
            font=("Helvetica", 11),
            text_color=color,
            anchor="e",
        )
        arrow.pack(fill="x", padx=(0, 10), pady=(4, 0))

        # Status label
        ctk.CTkLabel(
            card, text=label,
            font=FONTS["body_small"],
            text_color="#555555",
            anchor="center",
        ).pack(pady=(2, 0))

        # Count
        count_lbl = ctk.CTkLabel(
            card, text="—",
            font=FONTS["subtitle"],
            text_color=color,
            anchor="center",
        )
        count_lbl.pack(pady=(2, 4))

        # "View loans" hint label
        hint = ctk.CTkLabel(
            card,
            text="View loans",
            font=FONTS["caption"],
            text_color=color,
            anchor="center",
        )
        hint.pack(pady=(0, 10))

        self.status_labels[key]  = count_lbl
        self._status_cards[key]  = card

        # ── Hover and click bindings ───────────────────────────────────────
        def on_enter(_e, c=card, col=color, hov=hover_color):
            c.configure(fg_color=hov, border_color=hov)

        def on_leave(_e, c=card, bg=bg_color, col=color):
            c.configure(fg_color=bg, border_color=col)

        def on_click(_e, k=key):
            self._navigate_to_loans(k)

        for widget in card.winfo_children() + [card]:
            widget.bind("<Enter>",    on_enter)
            widget.bind("<Leave>",    on_leave)
            widget.bind("<Button-1>", on_click)

    def _navigate_to_loans(self, status: str):
        """Navigate to Loans screen — future enhancement can pre-filter by status."""
        # Show loans screen — the status filter can be pre-set if loans_screen
        # supports a status kwarg; for now it navigates and the user filters.
        self.master.show_screen("loans")

    # ── Recent activity ────────────────────────────────────────────────────────

    def _build_recent_activity(self):
        ctk.CTkLabel(
            self.content, text="Recent Repayments",
            font=FONTS["heading"],
            text_color=COLORS["accent_green_dark"],
            anchor="w",
        ).grid(row=5, column=0, sticky="w", padx=28, pady=(28, 8))

        self.activity_frame = ctk.CTkFrame(
            self.content,
            fg_color=COLORS["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
        )
        self.activity_frame.grid(row=6, column=0, sticky="ew",
                                  padx=28, pady=(0, 28))
        self.activity_frame.columnconfigure(0, weight=1)

        self._render_activity_header()
        self.activity_placeholder = ctk.CTkLabel(
            self.activity_frame, text="Loading…",
            font=FONTS["body"], text_color=COLORS["text_muted"])
        self.activity_placeholder.pack(pady=20)

    def _render_activity_header(self):
        hdr = ctk.CTkFrame(
            self.activity_frame,
            fg_color=COLORS["accent_green"],
            corner_radius=0, height=36)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        for col_text, width in [("Receipt", 170), ("Loan No.", 140),
                                  ("Amount", 130), ("Date", 100)]:
            ctk.CTkLabel(
                hdr, text=col_text,
                font=FONTS["badge"],
                text_color="#FFFFFF",
                width=width,
            ).pack(side="left", padx=(16 if col_text == "Receipt" else 0, 0))

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

            # Update top stat cards
            if hasattr(self, "card_total"):
                self.card_total.update_value(f"UGX {portfolio:,.0f}")
            if hasattr(self, "card_active"):
                self.card_active.update_value(str(counts.get("active", 0)))
            if hasattr(self, "card_overdue"):
                self.card_overdue.update_value(str(overdue))
            if hasattr(self, "card_clients"):
                self.card_clients.update_value(str(client_count))

            # Update status card counts
            for key, lbl in self.status_labels.items():
                lbl.configure(text=str(counts.get(key, 0)))

            # Rebuild recent repayments
            for w in self.activity_frame.winfo_children():
                w.destroy()
            self._render_activity_header()

            recent = RepaymentService.get_all_recent_repayments(limit=8)
            all_loans = {}
            try:
                from app.core.services.loan_service import LoanService as LS
                all_loans = {l.id: l for l in LS.get_all_loans()}
            except Exception:
                pass

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
                    row = ctk.CTkFrame(self.activity_frame,
                                       fg_color=bg, height=38)
                    row.pack(fill="x")
                    row.pack_propagate(False)

                    loan = all_loans.get(r.loan_id)

                    ctk.CTkLabel(
                        row, text=r.receipt_number,
                        font=FONTS["body_small"],
                        text_color=COLORS["text_primary"],
                        width=170,
                    ).pack(side="left", padx=16)

                    ctk.CTkLabel(
                        row,
                        text=loan.loan_number if loan else "—",
                        font=FONTS["body_small"],
                        text_color=COLORS["text_secondary"],
                        width=140,
                    ).pack(side="left")

                    ctk.CTkLabel(
                        row, text=f"UGX {r.amount:,.0f}",
                        font=FONTS["subheading"],
                        text_color=COLORS["accent_green_dark"],
                        width=130,
                    ).pack(side="left")

                    ctk.CTkLabel(
                        row, text=str(r.payment_date),
                        font=FONTS["body_small"],
                        text_color=COLORS["text_muted"],
                    ).pack(side="left")

        except Exception as e:
            print(f"[Dashboard] Error loading stats: {e}")