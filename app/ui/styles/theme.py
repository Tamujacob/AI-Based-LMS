"""
app/ui/styles/theme.py
─────────────────────────────────────────────
Centralised design system for Bingongold LMS.
Deep navy + gold — professional financial aesthetic.
All colors, fonts, and widget configs live here.
"""

import customtkinter as ctk

# ── Color Palette ─────────────────────────────────────────────────────────────
# Dark theme (default)
COLORS = {
    # Backgrounds
    "bg_primary":       "#0D1B2A",   # Deep navy — main background
    "bg_secondary":     "#112235",   # Slightly lighter — sidebar
    "bg_card":          "#152C40",   # Card / panel backgrounds
    "bg_input":         "#1A3550",   # Input field background
    "bg_hover":         "#1F3D5C",   # Hover state
    "bg_selected":      "#1B4F72",   # Selected row

    # Gold accent (brand color — Bingongold)
    "accent_gold":      "#D4A017",   # Primary gold
    "accent_gold_dark": "#B8860B",   # Darker gold (pressed states)
    "accent_gold_light":"#F0C040",   # Light gold (hover)

    # Semantic
    "success":          "#27AE60",
    "warning":          "#F39C12",
    "danger":           "#E74C3C",
    "info":             "#2E86C1",

    # Risk colors
    "risk_low":         "#27AE60",
    "risk_medium":      "#F39C12",
    "risk_high":        "#E74C3C",

    # Text
    "text_primary":     "#ECF0F1",   # Almost white
    "text_secondary":   "#95A5A6",   # Muted grey
    "text_muted":       "#6C7A89",   # Dimmed
    "text_on_accent":   "#0D1B2A",   # Dark text on gold buttons

    # Borders
    "border":           "#1E3A52",
    "border_focus":     "#D4A017",

    # Status badge backgrounds
    "status_pending_bg":   "#2C3E50",
    "status_approved_bg":  "#1A5276",
    "status_active_bg":    "#1E8449",
    "status_completed_bg": "#17202A",
    "status_defaulted_bg": "#922B21",
    "status_rejected_bg":  "#6E2C00",
}

# ── Typography ────────────────────────────────────────────────────────────────
FONTS = {
    "display":      ("Georgia", 28, "bold"),
    "title":        ("Georgia", 20, "bold"),
    "subtitle":     ("Georgia", 16, "bold"),
    "heading":      ("Helvetica", 14, "bold"),
    "subheading":   ("Helvetica", 12, "bold"),
    "body":         ("Helvetica", 12),
    "body_small":   ("Helvetica", 11),
    "caption":      ("Helvetica", 10),
    "mono":         ("Courier", 11),
    "button":       ("Helvetica", 12, "bold"),
    "nav":          ("Helvetica", 13),
    "badge":        ("Helvetica", 10, "bold"),
}

# ── Dimensions ────────────────────────────────────────────────────────────────
SIDEBAR_WIDTH = 220
HEADER_HEIGHT = 60
CARD_CORNER_RADIUS = 12
BUTTON_CORNER_RADIUS = 8
INPUT_CORNER_RADIUS = 8

# ── CustomTkinter Configuration ───────────────────────────────────────────────
def configure_theme():
    """Apply the Bingongold theme to CustomTkinter."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")


# ── Widget Style Presets ──────────────────────────────────────────────────────

def primary_button_style() -> dict:
    """Gold primary action button."""
    return {
        "fg_color": COLORS["accent_gold"],
        "hover_color": COLORS["accent_gold_light"],
        "text_color": COLORS["text_on_accent"],
        "font": FONTS["button"],
        "corner_radius": BUTTON_CORNER_RADIUS,
        "height": 40,
    }


def secondary_button_style() -> dict:
    """Outlined secondary button."""
    return {
        "fg_color": "transparent",
        "border_color": COLORS["accent_gold"],
        "border_width": 1,
        "hover_color": COLORS["bg_hover"],
        "text_color": COLORS["accent_gold"],
        "font": FONTS["button"],
        "corner_radius": BUTTON_CORNER_RADIUS,
        "height": 40,
    }


def danger_button_style() -> dict:
    """Red destructive action button."""
    return {
        "fg_color": COLORS["danger"],
        "hover_color": "#C0392B",
        "text_color": COLORS["text_primary"],
        "font": FONTS["button"],
        "corner_radius": BUTTON_CORNER_RADIUS,
        "height": 40,
    }


def input_style() -> dict:
    """Standard text input field."""
    return {
        "fg_color": COLORS["bg_input"],
        "border_color": COLORS["border"],
        "text_color": COLORS["text_primary"],
        "font": FONTS["body"],
        "corner_radius": INPUT_CORNER_RADIUS,
        "height": 40,
        "border_width": 1,
    }


def card_style() -> dict:
    """Standard card / panel."""
    return {
        "fg_color": COLORS["bg_card"],
        "corner_radius": CARD_CORNER_RADIUS,
    }


def status_color(status: str) -> str:
    """Return the background color for a given loan status."""
    mapping = {
        "pending":   COLORS["status_pending_bg"],
        "approved":  COLORS["status_approved_bg"],
        "active":    COLORS["status_active_bg"],
        "completed": COLORS["status_completed_bg"],
        "defaulted": COLORS["status_defaulted_bg"],
        "rejected":  COLORS["status_rejected_bg"],
    }
    return mapping.get(status.lower(), COLORS["bg_card"])


def risk_color(risk: str) -> str:
    """Return the color for a risk level."""
    mapping = {
        "LOW":    COLORS["risk_low"],
        "MEDIUM": COLORS["risk_medium"],
        "HIGH":   COLORS["risk_high"],
    }
    return mapping.get(risk.upper(), COLORS["text_secondary"])