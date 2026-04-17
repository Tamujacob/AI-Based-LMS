"""
app/ui/components/sidebar.py - Bingongold Credit branded sidebar
Green background, white text, gold active state, with logo
"""

import customtkinter as ctk
from PIL import Image
import os
from app.ui.styles.theme import COLORS, FONTS, SIDEBAR_WIDTH

NAV_ITEMS = [
    ("dashboard",   "D",  "Dashboard"),
    ("clients",     "C",  "Clients"),
    ("loans",       "L",  "Loans"),
    ("repayments",  "R",  "Repayments"),
    ("agent",       "A",  "AI Agent"),
    ("chatbot",     "CH", "AI Chatbot"),
    ("reports",     "P",  "Reports"),
    ("settings",    "S",  "Settings"),
]


# Unicode icons that work reliably
ICONS = {
    "dashboard":   "  \u25A0",
    "clients":     "  \u25CF",
    "loans":       "  \u25B6",
    "repayments":  "  \u25C6",
    "agent":       "  \u2605",
    "chatbot":     "  \u25BA",
    "reports":     "  \u25A3",
    "settings":    "  \u25C7",
}

class Sidebar(ctk.CTkFrame):
    def __init__(self, master, current_screen: str, on_navigate,
                 current_user=None, **kwargs):
        super().__init__(
            master,
            width=SIDEBAR_WIDTH,
            fg_color=COLORS["sidebar_bg"],
            corner_radius=0,
            **kwargs,
        )
        self.pack_propagate(False)
        self.current_screen = current_screen
        self.on_navigate = on_navigate
        self.current_user = current_user
        self._build()

    def _build(self):
        # ── Logo section ──────────────────────────────────────────────
        logo_frame = ctk.CTkFrame(self, fg_color=COLORS["accent_green_dark"],
                                   corner_radius=0)
        logo_frame.pack(fill="x")

        # Try to load actual logo image
        logo_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../../../../assets/images/logo.png"
        )
        logo_loaded = False
        for possible_path in [
            "assets/images/logo.png",
            "./assets/images/logo.png",
            os.path.expanduser("~/Desktop/AI-Based-LMS/assets/images/logo.png"),
        ]:
            if os.path.exists(possible_path):
                try:
                    pil_img = Image.open(possible_path)
                    # Resize to fit sidebar
                    ratio = 190 / pil_img.width
                    new_h = int(pil_img.height * ratio)
                    pil_img = pil_img.resize((190, new_h), Image.LANCZOS)
                    ctk_img = ctk.CTkImage(light_image=pil_img,
                                           dark_image=pil_img,
                                           size=(190, new_h))
                    ctk.CTkLabel(logo_frame, image=ctk_img, text="",
                                 fg_color="transparent").pack(pady=14, padx=18)
                    logo_loaded = True
                    break
                except Exception:
                    pass

        if not logo_loaded:
            # Text fallback with brand styling
            ctk.CTkLabel(
                logo_frame,
                text="Bingongold Credit",
                font=("Georgia", 14, "bold"),
                text_color=COLORS["accent_gold"],
            ).pack(pady=(16, 2), padx=16)
            ctk.CTkLabel(
                logo_frame,
                text="together as one",
                font=("Georgia", 10, "italic"),
                text_color=COLORS["sidebar_muted"],
            ).pack(pady=(0, 14), padx=16)

        # Gold divider line
        ctk.CTkFrame(self, fg_color=COLORS["accent_gold"],
                     height=2, corner_radius=0).pack(fill="x")

        # Small spacer
        ctk.CTkFrame(self, fg_color="transparent", height=8).pack()

        # ── Navigation ────────────────────────────────────────────────
        nav_labels = {
            "dashboard":   "  Dashboard",
            "clients":     "  Clients",
            "loans":       "  Loans",
            "repayments":  "  Repayments",
            "agent":       "  AI Agent",
            "chatbot":     "  AI Chatbot",
            "reports":     "  Reports",
            "settings":    "  Settings",
        }

        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.pack(fill="x", padx=10)

        for screen_name, _, label in NAV_ITEMS:
            is_active = screen_name == self.current_screen
            btn = ctk.CTkButton(
                nav_frame,
                text=nav_labels[screen_name],
                anchor="w",
                height=44,
                corner_radius=8,
                font=FONTS["nav"],
                fg_color=COLORS["accent_gold"] if is_active else "transparent",
                text_color=COLORS["text_on_gold"] if is_active else COLORS["sidebar_text"],
                hover_color=COLORS["sidebar_hover"],
                border_width=0,
                command=lambda s=screen_name: self.on_navigate(s),
            )
            btn.pack(fill="x", pady=2)

        # ── Spacer ────────────────────────────────────────────────────
        ctk.CTkFrame(self, fg_color="transparent").pack(fill="both", expand=True)

        # Gold divider
        ctk.CTkFrame(self, fg_color=COLORS["accent_gold"],
                     height=1, corner_radius=0).pack(fill="x", padx=16)

        # ── User info ─────────────────────────────────────────────────
        if self.current_user:
            user_frame = ctk.CTkFrame(self, fg_color="transparent")
            user_frame.pack(fill="x", padx=16, pady=(8, 4))
            ctk.CTkLabel(
                user_frame,
                text=self.current_user.full_name,
                font=FONTS["body_small"],
                text_color=COLORS["sidebar_text"],
                anchor="w",
            ).pack(fill="x")
            ctk.CTkLabel(
                user_frame,
                text=self.current_user.role.value.replace("_", " ").title(),
                font=FONTS["caption"],
                text_color=COLORS["sidebar_muted"],
                anchor="w",
            ).pack(fill="x")

        # ── Logout ────────────────────────────────────────────────────
        ctk.CTkButton(
            self,
            text="  Logout",
            anchor="w",
            height=38,
            corner_radius=8,
            font=FONTS["nav"],
            fg_color="transparent",
            text_color=COLORS["accent_gold"],
            hover_color=COLORS["sidebar_hover"],
            command=lambda: self.on_navigate("logout"),
        ).pack(fill="x", padx=10, pady=(4, 16))
