"""
app/ui/components/sidebar.py
─────────────────────────────────────────────
Navigation sidebar used on every screen after login.
Shows nav items, current user info, and logout button.
"""

import customtkinter as ctk
from app.ui.styles.theme import COLORS, FONTS, SIDEBAR_WIDTH


NAV_ITEMS = [
    ("dashboard",   "📊",  "Dashboard"),
    ("clients",     "👥",  "Clients"),
    ("loans",       "💰",  "Loans"),
    ("repayments",  "💳",  "Repayments"),
    ("agent",       "🤖",  "AI Agent"),
    ("chatbot",     "💬",  "AI Chatbot"),
    ("reports",     "📄",  "Reports"),
    ("settings",    "⚙️",  "Settings"),
]


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, current_screen: str, on_navigate, current_user=None, **kwargs):
        super().__init__(
            master,
            width=SIDEBAR_WIDTH,
            fg_color=COLORS["bg_secondary"],
            corner_radius=0,
            **kwargs,
        )
        self.pack_propagate(False)
        self.current_screen = current_screen
        self.on_navigate = on_navigate
        self.current_user = current_user
        self._build()

    def _build(self):
        # ── Brand ──────────────────────────────────────────────────────────
        brand = ctk.CTkFrame(self, fg_color="transparent")
        brand.pack(fill="x", padx=16, pady=(20, 8))

        ctk.CTkLabel(
            brand,
            text="BINGONGOLD",
            font=("Georgia", 15, "bold"),
            text_color=COLORS["accent_gold"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            brand,
            text="CREDIT  •  LMS",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
        ).pack(anchor="w")

        # Divider
        ctk.CTkFrame(self, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=(8, 12)
        )

        # ── Nav Items ──────────────────────────────────────────────────────
        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.pack(fill="x", padx=8)

        for screen_name, icon, label in NAV_ITEMS:
            is_active = screen_name == self.current_screen
            btn = ctk.CTkButton(
                nav_frame,
                text=f"  {icon}   {label}",
                anchor="w",
                height=42,
                corner_radius=8,
                font=FONTS["nav"],
                fg_color=COLORS["accent_gold"] if is_active else "transparent",
                text_color=COLORS["text_on_accent"] if is_active else COLORS["text_secondary"],
                hover_color=COLORS["bg_hover"],
                command=lambda s=screen_name: self.on_navigate(s),
            )
            btn.pack(fill="x", pady=2)

        # ── Spacer ─────────────────────────────────────────────────────────
        ctk.CTkFrame(self, fg_color="transparent").pack(fill="both", expand=True)

        # ── User Info + Logout ─────────────────────────────────────────────
        ctk.CTkFrame(self, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=(0, 12)
        )

        user_frame = ctk.CTkFrame(self, fg_color="transparent")
        user_frame.pack(fill="x", padx=16, pady=(0, 8))

        if self.current_user:
            ctk.CTkLabel(
                user_frame,
                text=self.current_user.full_name,
                font=FONTS["body_small"],
                text_color=COLORS["text_primary"],
                anchor="w",
            ).pack(fill="x")
            ctk.CTkLabel(
                user_frame,
                text=self.current_user.role.value.replace("_", " ").title(),
                font=FONTS["caption"],
                text_color=COLORS["text_muted"],
                anchor="w",
            ).pack(fill="x")

        ctk.CTkButton(
            self,
            text="  🚪   Logout",
            anchor="w",
            height=38,
            corner_radius=8,
            font=FONTS["nav"],
            fg_color="transparent",
            text_color=COLORS["danger"],
            hover_color=COLORS["bg_hover"],
            command=lambda: self.on_navigate("logout"),
        ).pack(fill="x", padx=8, pady=(4, 16))