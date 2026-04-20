"""
app/ui/components/sidebar.py - Updated with colorful emoji icons
"""

import customtkinter as ctk
from PIL import Image
import os
from app.ui.styles.theme import COLORS, FONTS, SIDEBAR_WIDTH

NAV_ITEMS = [
    ("dashboard",  "🏠",  "Dashboard"),
    ("clients",    "👥",  "Clients"),
    ("loans",      "💰",  "Loans"),
    ("repayments", "💳",  "Repayments"),
    ("agent",      "🤖",  "AI Agent"),
    ("chatbot",    "💬",  "AI Chatbot"),
    ("reports",    "📊",  "Reports"),
    ("users",      "🔑",  "Users"),
    ("logs",       "📋",  "Activity Logs"),
    ("settings",   "⚙️",  "Settings"),
]


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, current_screen: str, on_navigate,
                 current_user=None, **kwargs):
        super().__init__(
            master, width=SIDEBAR_WIDTH,
            fg_color=COLORS["sidebar_bg"],
            corner_radius=0, **kwargs)
        self.pack_propagate(False)
        self.current_screen = current_screen
        self.on_navigate = on_navigate
        self.current_user = current_user
        self._build()

    def _build(self):
        # ── Logo section ─────────────────────────────────────────────────
        logo_frame = ctk.CTkFrame(self, fg_color=COLORS["accent_green_dark"],
                                   corner_radius=0)
        logo_frame.pack(fill="x")

        logo_loaded = False
        for possible_path in [
            "assets/images/logo.png",
            "./assets/images/logo.png",
            os.path.expanduser("~/Desktop/AI-Based-LMS/assets/images/logo.png"),
        ]:
            if os.path.exists(possible_path):
                try:
                    pil_img = Image.open(possible_path)
                    ratio = 190 / pil_img.width
                    new_h = int(pil_img.height * ratio)
                    pil_img = pil_img.resize((190, new_h), Image.LANCZOS)
                    ctk_img = ctk.CTkImage(light_image=pil_img,
                                           dark_image=pil_img,
                                           size=(190, new_h))
                    ctk.CTkLabel(logo_frame, image=ctk_img, text="",
                                 fg_color="transparent").pack(pady=12, padx=18)
                    logo_loaded = True
                    break
                except Exception:
                    pass

        if not logo_loaded:
            ctk.CTkLabel(logo_frame, text="Bingongold Credit",
                         font=("Georgia", 13, "bold"),
                         text_color=COLORS["accent_gold"]).pack(pady=(14, 2), padx=16)
            ctk.CTkLabel(logo_frame, text="together as one",
                         font=("Georgia", 10, "italic"),
                         text_color=COLORS["sidebar_muted"]).pack(pady=(0, 12), padx=16)

        # ── Gold divider ──────────────────────────────────────────────────
        ctk.CTkFrame(self, fg_color=COLORS["accent_gold"],
                     height=2, corner_radius=0).pack(fill="x")
        ctk.CTkFrame(self, fg_color="transparent", height=6).pack()

        # ── Scrollable nav area ───────────────────────────────────────────
        nav_scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=COLORS["sidebar_hover"])
        nav_scroll.pack(fill="both", expand=True, padx=8)

        for screen_name, icon, label in NAV_ITEMS:
            # Only show Users and Logs for manager/admin
            if screen_name in ("users", "logs") and self.current_user:
                if self.current_user.role.value == "loan_officer":
                    continue

            is_active = screen_name == self.current_screen

            # Outer container for each nav row
            row_frame = ctk.CTkFrame(
                nav_scroll,
                fg_color=COLORS["accent_gold"] if is_active else "transparent",
                corner_radius=8,
                cursor="hand2",
            )
            row_frame.pack(fill="x", pady=2)

            # Emoji icon label
            icon_lbl = ctk.CTkLabel(
                row_frame,
                text=icon,
                font=("Segoe UI Emoji", 18),
                text_color=COLORS["text_on_gold"] if is_active else COLORS["sidebar_text"],
                width=38,
                anchor="center",
            )
            icon_lbl.pack(side="left", padx=(8, 0), pady=8)

            # Nav text label
            text_lbl = ctk.CTkLabel(
                row_frame,
                text=label,
                font=FONTS["nav"],
                text_color=COLORS["text_on_gold"] if is_active else COLORS["sidebar_text"],
                anchor="w",
            )
            text_lbl.pack(side="left", fill="x", expand=True, padx=(6, 8), pady=8)

            # Bind clicks and hover on entire row, icon, and label
            for widget in (row_frame, icon_lbl, text_lbl):
                widget.bind("<Button-1>", lambda e, s=screen_name: self.on_navigate(s))
                widget.bind("<Enter>", lambda e, f=row_frame, a=is_active: f.configure(
                    fg_color=COLORS["accent_gold"] if a else COLORS["sidebar_hover"]))
                widget.bind("<Leave>", lambda e, f=row_frame, a=is_active: f.configure(
                    fg_color=COLORS["accent_gold"] if a else "transparent"))

        # ── Divider ───────────────────────────────────────────────────────
        ctk.CTkFrame(self, fg_color=COLORS["accent_gold"],
                     height=1, corner_radius=0).pack(fill="x", padx=16, pady=(4, 0))

        # ── User info ─────────────────────────────────────────────────────
        if self.current_user:
            user_frame = ctk.CTkFrame(self, fg_color="transparent")
            user_frame.pack(fill="x", padx=16, pady=(8, 4))
            ctk.CTkLabel(user_frame, text=self.current_user.full_name,
                         font=FONTS["body_small"],
                         text_color=COLORS["sidebar_text"],
                         anchor="w").pack(fill="x")
            ctk.CTkLabel(user_frame,
                         text=self.current_user.role.value.replace("_", " ").title(),
                         font=FONTS["caption"],
                         text_color=COLORS["sidebar_muted"],
                         anchor="w").pack(fill="x")

        # ── Logout row ────────────────────────────────────────────────────
        logout_frame = ctk.CTkFrame(self, fg_color="transparent",
                                     corner_radius=8, cursor="hand2")
        logout_frame.pack(fill="x", padx=10, pady=(4, 14))

        logout_icon = ctk.CTkLabel(
            logout_frame,
            text="🚪",
            font=("Segoe UI Emoji", 18),
            text_color=COLORS["accent_gold"],
            width=38,
            anchor="center",
        )
        logout_icon.pack(side="left", padx=(8, 0), pady=8)

        logout_lbl = ctk.CTkLabel(
            logout_frame,
            text="Logout",
            font=FONTS["nav"],
            text_color=COLORS["accent_gold"],
            anchor="w",
        )
        logout_lbl.pack(side="left", fill="x", expand=True, padx=(6, 8), pady=8)

        for widget in (logout_frame, logout_icon, logout_lbl):
            widget.bind("<Button-1>", lambda e: self.on_navigate("logout"))
            widget.bind("<Enter>", lambda e: logout_frame.configure(
                fg_color=COLORS["sidebar_hover"]))
            widget.bind("<Leave>", lambda e: logout_frame.configure(
                fg_color="transparent"))