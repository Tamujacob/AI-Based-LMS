"""
app/ui/components/stat_card.py
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
            **kwargs,
        )
        self.accent = accent or COLORS["accent_gold"]
        self._icon = icon
        self._label = label
        self._value = value
        self._build(icon, label, value)

    def _build(self, icon, label, value):
        # Top accent bar
        ctk.CTkFrame(
            self,
            fg_color=self.accent,
            height=4,
            corner_radius=2,
        ).pack(fill="x")

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=16)

        # Icon + label row
        top = ctk.CTkFrame(content, fg_color="transparent")
        top.pack(fill="x")

        ctk.CTkLabel(
            top,
            text=icon,
            font=("Helvetica", 24),
            text_color=self.accent,
        ).pack(side="left")

        ctk.CTkLabel(
            top,
            text=label,
            font=FONTS["body_small"],
            text_color=COLORS["text_secondary"],
        ).pack(side="left", padx=(10, 0))

        # Value label — store reference so we can update it
        self.value_label = ctk.CTkLabel(
            content,
            text=value,
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        self.value_label.pack(fill="x", pady=(8, 0))

    def update_value(self, new_value: str):
        """Update the displayed value without rebuilding the card."""
        self.value_label.configure(text=new_value)