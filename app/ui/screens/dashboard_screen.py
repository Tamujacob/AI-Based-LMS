"""
app/ui/screens/dashboard_screen.py
─────────────────────────────────────────────
Main dashboard — stat cards, loan status summary,
and recent activity feed.
"""

import customtkinter as ctk
from app.ui.styles.theme import COLORS, FONTS
from app.ui.components.sidebar import Sidebar
from app.ui.components.stat_card import StatCard


class DashboardScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master = master
        self.current_user = master.current_user
        self._build()
        self._load_stats()

    def _navigate(self, screen: str):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = Sidebar(
            self,
            current_screen="dashboard",
            on_navigate=self._navigate,
            current_user=self.current_user,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # Main content
        self.content = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["bg_primary"],
            scrollbar_button_color=COLORS["bg_hover"],
        )
        self.content.grid(row=0, column=1, sticky="nsew", padx=0)
        self.content.columnconfigure(0, weight=1)

        self._build_header()
        self._build_stat_cards()
        self._build_loan_status_row()
        self._build_recent_activity()

    def _build_header(self):
        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=32, pady=(28, 0))
        header.columnconfigure(1, weight=1)

        name = self.current_user.full_name if self.current_user else "User"
        ctk.CTkLabel(
            header,
            text=f"Good day, {name} 👋",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text="Here's what's happening at Bingongold Credit today.",
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        # Refresh button
        ctk.CTkButton(
            header,
            text="↻  Refresh",
            width=110,
            height=34,
            font=FONTS["body_small"],
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"],
            corner_radius=8,
            command=self._load_stats,
        ).grid(row=0, column=2, sticky="e")

    def _build_stat_cards(self):
        cards_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        cards_frame.grid(row=1, column=0, sticky="ew", padx=32, pady=(24, 0))
        for i in range(4):
            cards_frame.columnconfigure(i, weight=1)

        self.card_total = StatCard(
            cards_frame, "💰", "Total Portfolio",
            "Loading...", accent=COLORS["accent_gold"]
        )
        self.card_total.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        self.card_active = StatCard(
            cards_frame, "✅", "Active Loans",
            "Loading...", accent=COLORS["success"]
        )
        self.card_active.grid(row=0, column=1, padx=8, sticky="ew")

        self.card_overdue = StatCard(
            cards_frame, "⚠️", "Overdue Loans",
            "Loading...", accent=COLORS["danger"]
        )
        self.card_overdue.grid(row=0, column=2, padx=8, sticky="ew")

        self.card_clients = StatCard(
            cards_frame, "👥", "Total Clients",
            "Loading...", accent=COLORS["info"]
        )
        self.card_clients.grid(row=0, column=3, padx=(8, 0), sticky="ew")

    def _build_loan_status_row(self):
        ctk.CTkLabel(
            self.content,
            text="Loan Status Breakdown",
            font=FONTS["heading"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).grid(row=2, column=0, sticky="w", padx=32, pady=(28, 8))

        self.status_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self.status_frame.grid(row=3, column=0, sticky="ew", padx=32)
        for i in range(5):
            self.status_frame.columnconfigure(i, weight=1)

        statuses = [
            ("pending",   "🕐 Pending",   COLORS["warning"]),
            ("approved",  "✔ Approved",   COLORS["info"]),
            ("active",    "▶ Active",     COLORS["success"]),
            ("completed", "✓ Completed",  COLORS["text_muted"]),
            ("defaulted", "✗ Defaulted",  COLORS["danger"]),
        ]
        self.status_labels = {}
        for i, (key, label, color) in enumerate(statuses):
            card = ctk.CTkFrame(self.content.master if False else self.status_frame,
                                fg_color=COLORS["bg_card"], corner_radius=10)
            card.grid(row=0, column=i, padx=4, sticky="ew")

            ctk.CTkLabel(card, text=label, font=FONTS["body_small"],
                         text_color=color).pack(pady=(12, 2))
            lbl = ctk.CTkLabel(card, text="—", font=FONTS["subtitle"],
                               text_color=COLORS["text_primary"])
            lbl.pack(pady=(0, 12))
            self.status_labels[key] = lbl

    def _build_recent_activity(self):
        ctk.CTkLabel(
            self.content,
            text="Recent Repayments",
            font=FONTS["heading"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).grid(row=4, column=0, sticky="w", padx=32, pady=(28, 8))

        self.activity_frame = ctk.CTkFrame(
            self.content,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
        )
        self.activity_frame.grid(row=5, column=0, sticky="ew", padx=32, pady=(0, 32))
        self.activity_frame.columnconfigure(0, weight=1)
        self.activity_placeholder = ctk.CTkLabel(
            self.activity_frame,
            text="Loading recent activity...",
            font=FONTS["body"],
            text_color=COLORS["text_muted"],
        )
        self.activity_placeholder.pack(pady=24)

    def _load_stats(self):
        """Pull stats from services and update the UI."""
        try:
            from app.core.services.loan_service import LoanService
            from app.core.services.client_service import ClientService
            from app.core.services.repayment_service import RepaymentService

            # Stat cards
            portfolio = LoanService.total_portfolio_value()
            counts = LoanService.count_by_status()
            active_count = counts.get("active", 0)
            overdue = len(LoanService.get_overdue_loans())
            client_count = ClientService.count_clients()

            self._refresh_card(self.card_total, f"UGX {portfolio:,.0f}")
            self._refresh_card(self.card_active, str(active_count))
            self._refresh_card(self.card_overdue, str(overdue))
            self._refresh_card(self.card_clients, str(client_count))

            # Status labels
            for key, lbl in self.status_labels.items():
                lbl.configure(text=str(counts.get(key, 0)))

            # Recent repayments
            for widget in self.activity_frame.winfo_children():
                widget.destroy()

            recent = RepaymentService.get_all_recent_repayments(limit=8)
            if not recent:
                ctk.CTkLabel(
                    self.activity_frame,
                    text="No repayments recorded yet.",
                    font=FONTS["body"],
                    text_color=COLORS["text_muted"],
                ).pack(pady=24)
            else:
                for r in recent:
                    row = ctk.CTkFrame(self.activity_frame, fg_color="transparent")
                    row.pack(fill="x", padx=20, pady=4)
                    ctk.CTkLabel(
                        row,
                        text=f"Receipt {r.receipt_number}",
                        font=FONTS["body_small"],
                        text_color=COLORS["text_primary"],
                        anchor="w",
                    ).pack(side="left")
                    ctk.CTkLabel(
                        row,
                        text=f"UGX {r.amount:,.0f}",
                        font=FONTS["subheading"],
                        text_color=COLORS["success"],
                        anchor="e",
                    ).pack(side="right")
                    ctk.CTkLabel(
                        row,
                        text=str(r.payment_date),
                        font=FONTS["caption"],
                        text_color=COLORS["text_muted"],
                        anchor="e",
                    ).pack(side="right", padx=16)

        except Exception as e:
            print(f"[Dashboard] Error loading stats: {e}")

    def _refresh_card(self, card, new_value: str):
        """Update the value label inside a StatCard."""
        if hasattr(card, 'value_label'):
            card.value_label.configure(text=new_value)