"""
app/ui/components/stat_card.py — Bingongold Credit branded KPI card
White card, green accent bar, dark text
"""

import customtkinter as ctk
from app.ui.styles.theme import COLORS, FONTS, CARD_CORNER_RADIUS


class StatCard(ctk.CTkFrame):
    def __init__(self, master, icon: str, label: str, value: str,
                 accent: str = None, **kwargs):
        super().__init__(
            master,
            fg_color=COLORS["bg_card"],
            corner_radius=CARD_CORNER_RADIUS,
            border_width=1,
            border_color=COLORS["border"],
            **kwargs,
        )
        self.accent = accent or COLORS["accent_green"]
        self._build(icon, label, value)

    def _build(self, icon, label, value):
        # Top accent bar
        ctk.CTkFrame(self, fg_color=self.accent,
                     height=5, corner_radius=0).pack(fill="x")

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=18, pady=14)

        # Icon circle + label row
        top = ctk.CTkFrame(content, fg_color="transparent")
        top.pack(fill="x")

        # Colored icon badge
        icon_bg = ctk.CTkFrame(top, fg_color=self.accent,
                                width=32, height=32, corner_radius=16)
        icon_bg.pack(side="left")
        icon_bg.pack_propagate(False)
        ctk.CTkLabel(icon_bg, text=icon[:1],
                     font=("Helvetica", 14, "bold"),
                     text_color="#FFFFFF").pack(expand=True)

        ctk.CTkLabel(
            top, text=label,
            font=FONTS["body_small"],
            text_color=COLORS["text_secondary"],
        ).pack(side="left", padx=(10, 0))

        # Value
        self.value_label = ctk.CTkLabel(
            content, text=value,
            font=FONTS["title"],
            text_color=COLORS["accent_green_dark"],
            anchor="w",
        )
        self.value_label.pack(fill="x", pady=(8, 0))

    def update_value(self, new_value: str):
        self.value_label.configure(text=new_value)
