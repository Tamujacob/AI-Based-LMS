"""
app/ui/styles/theme.py
Bingongold Credit brand theme — Green, Gold, White
"""

import customtkinter as ctk

COLORS = {
    # Backgrounds
    "bg_primary":       "#F4F6F4",   # Light grey-green — main background
    "bg_secondary":     "#1A5C1E",   # Dark green — sidebar
    "bg_card":          "#FFFFFF",   # White cards
    "bg_input":         "#F0F7F0",   # Very light green input
    "bg_hover":         "#2E8B32",   # Mid green hover
    "bg_selected":      "#34A038",   # Selected row

    # Brand colors
    "accent_gold":      "#D4A820",   # Primary gold (from logo)
    "accent_gold_dark": "#B8900A",   # Darker gold
    "accent_gold_light":"#F0C840",   # Light gold hover
    "accent_green":     "#34A038",   # Primary brand green
    "accent_green_dark":"#1A5C1E",   # Dark green
    "accent_green_light":"#4DC452",  # Light green

    # Semantic
    "success":          "#34A038",
    "warning":          "#D4A820",
    "danger":           "#C0392B",
    "info":             "#1A6B8A",

    # Risk colors
    "risk_low":         "#34A038",
    "risk_medium":      "#D4A820",
    "risk_high":        "#C0392B",

    # Text
    "text_primary":     "#1A2E1A",   # Very dark green-black
    "text_secondary":   "#4A6B4A",   # Medium green-grey
    "text_muted":       "#7A9A7A",   # Muted green
    "text_on_green":    "#FFFFFF",   # White on green backgrounds
    "text_on_gold":     "#1A2E1A",   # Dark on gold
    "text_on_accent":   "#FFFFFF",   # White on green buttons

    # Borders
    "border":           "#C8DFC8",
    "border_focus":     "#34A038",

    # Status badge backgrounds
    "status_pending_bg":   "#FFF8E8",
    "status_approved_bg":  "#E8F4E8",
    "status_active_bg":    "#34A038",
    "status_completed_bg": "#F0F0F0",
    "status_defaulted_bg": "#FDECEA",
    "status_rejected_bg":  "#FFF0F0",

    # Sidebar specific
    "sidebar_bg":       "#1A5C1E",
    "sidebar_text":     "#FFFFFF",
    "sidebar_muted":    "#A8D0A8",
    "sidebar_active":   "#D4A820",
    "sidebar_hover":    "#2E8B32",
}

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
    "tagline":      ("Georgia", 11, "italic"),
}

SIDEBAR_WIDTH = 230
HEADER_HEIGHT = 60
CARD_CORNER_RADIUS = 10
BUTTON_CORNER_RADIUS = 8
INPUT_CORNER_RADIUS = 8


def configure_theme():
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("green")


def primary_button_style() -> dict:
    return {
        "fg_color": COLORS["accent_green"],
        "hover_color": COLORS["accent_green_dark"],
        "text_color": COLORS["text_on_green"],
        "font": FONTS["button"],
        "corner_radius": BUTTON_CORNER_RADIUS,
        "height": 40,
    }


def gold_button_style() -> dict:
    return {
        "fg_color": COLORS["accent_gold"],
        "hover_color": COLORS["accent_gold_dark"],
        "text_color": COLORS["text_on_gold"],
        "font": FONTS["button"],
        "corner_radius": BUTTON_CORNER_RADIUS,
        "height": 40,
    }


def secondary_button_style() -> dict:
    return {
        "fg_color": "transparent",
        "border_color": COLORS["accent_green"],
        "border_width": 1,
        "hover_color": COLORS["bg_input"],
        "text_color": COLORS["accent_green"],
        "font": FONTS["button"],
        "corner_radius": BUTTON_CORNER_RADIUS,
        "height": 40,
    }


def danger_button_style() -> dict:
    return {
        "fg_color": COLORS["danger"],
        "hover_color": "#A93226",
        "text_color": "#FFFFFF",
        "font": FONTS["button"],
        "corner_radius": BUTTON_CORNER_RADIUS,
        "height": 40,
    }


def input_style() -> dict:
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
    return {
        "fg_color": COLORS["bg_card"],
        "corner_radius": CARD_CORNER_RADIUS,
    }


def status_color(status: str) -> str:
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
    mapping = {
        "LOW":    COLORS["risk_low"],
        "MEDIUM": COLORS["risk_medium"],
        "HIGH":   COLORS["risk_high"],
    }
    return mapping.get(risk.upper(), COLORS["text_secondary"])