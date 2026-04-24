"""
app/ui/components/sidebar.py
─────────────────────────────
Sidebar navigation using real Feather Icons SVGs from assets/icons/.

Requirements:
    pip install cairosvg pillow

Icon files expected in assets/icons/:
    home.svg            → Dashboard
    users.svg           → Clients
    dollar-sign.svg     → Loans
    credit-card.svg     → Repayments
    cpu.svg             → AI Agent
    message-circle.svg  → AI Chatbot
    bar-chart-2.svg     → Reports
    key.svg             → Users
    clipboard.svg       → Activity Logs
    settings.svg        → Settings
    log-out.svg         → Logout
"""

import os
import io
import customtkinter as ctk
from PIL import Image
from app.ui.styles.theme import COLORS, FONTS, SIDEBAR_WIDTH

# ── Nav item definitions ───────────────────────────────────────────────────────
# (screen_name, icon_filename, display_label)
NAV_ITEMS = [
    ("dashboard",  "home.svg",           "Dashboard"),
    ("clients",    "users.svg",          "Clients"),
    ("loans",      "dollar-sign.svg",    "Loans"),
    ("repayments", "credit-card.svg",    "Repayments"),
    ("agent",      "cpu.svg",            "AI Agent"),
    ("chatbot",    "message-circle.svg", "AI Chatbot"),
    ("reports",    "bar-chart-2.svg",    "Reports"),
    ("users",      "key.svg",            "Users"),
    ("logs",       "clipboard.svg",      "Activity Logs"),
    ("settings",   "settings.svg",       "Settings"),
]

ICON_DIR  = "assets/icons"
ICON_SIZE = 20   # rendered size in sidebar (px)


# ── Icon loader ────────────────────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> tuple:
    """Convert #RRGGBB to (R, G, B) integers."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _load_icon(filename: str, color_hex: str, size: int = ICON_SIZE):
    """
    Load an SVG or PNG icon from assets/icons/, tint it to color_hex,
    and return a CTkImage ready to use. Returns None if loading fails.

    Rendering strategy:
      1. SVG  → cairosvg renders to PNG in memory (best quality)
      2. PNG  → Pillow loads directly
      3. Fallback → returns None (sidebar shows a text letter instead)
    """
    path = os.path.join(ICON_DIR, filename)
    if not os.path.exists(path):
        return None

    render_size = size * 2   # render at 2× for HiDPI sharpness

    try:
        ext = os.path.splitext(filename)[1].lower()

        if ext == ".svg":
            try:
                import cairosvg
                png_bytes = cairosvg.svg2png(
                    url=path,
                    output_width=render_size,
                    output_height=render_size,
                )
                img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
            except ImportError:
                # cairosvg not installed — try loading as PNG with same name
                png_path = path.replace(".svg", ".png")
                if os.path.exists(png_path):
                    img = Image.open(png_path).convert("RGBA").resize(
                        (render_size, render_size), Image.LANCZOS)
                else:
                    return None

        elif ext in (".png", ".jpg", ".jpeg"):
            img = Image.open(path).convert("RGBA").resize(
                (render_size, render_size), Image.LANCZOS)
        else:
            return None

        # ── Tint: replace RGB channels with target colour ──────────────────
        # Alpha channel is preserved so the icon shape stays intact.
        r_t, g_t, b_t = _hex_to_rgb(color_hex)
        r, g, b, a    = img.split()
        tinted = Image.merge("RGBA", (
            Image.new("L", img.size, r_t),
            Image.new("L", img.size, g_t),
            Image.new("L", img.size, b_t),
            a,
        ))

        return ctk.CTkImage(
            light_image=tinted,
            dark_image=tinted,
            size=(size, size),
        )

    except Exception as e:
        print(f"[Sidebar] Could not load icon '{filename}': {e}")
        return None


# ── Sidebar component ──────────────────────────────────────────────────────────

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
        self.on_navigate    = on_navigate
        self.current_user   = current_user

        # Pre-load all icon variants once at build time
        self._icons_inactive       = {}
        self._icons_active         = {}
        self._icon_logout_inactive = None
        self._icon_logout_active   = None
        self._preload_icons()

        self._build()

    # ── Icon preloading ────────────────────────────────────────────────────────

    def _preload_icons(self):
        """Load and tint all icons once. Active = gold text, inactive = sidebar text."""
        inactive_hex = COLORS.get("sidebar_text", "#C8E6C9")
        active_hex   = COLORS.get("text_on_gold", "#1A2E1A")
        gold_hex     = COLORS.get("accent_gold",  "#D4A820")

        all_files = [item[1] for item in NAV_ITEMS] + ["log-out.svg"]
        for filename in all_files:
            self._icons_inactive[filename] = _load_icon(filename, inactive_hex)
            self._icons_active[filename]   = _load_icon(filename, active_hex)

        # Logout icon uses gold when inactive, active-text when hovered
        self._icon_logout_inactive = _load_icon("log-out.svg", gold_hex)
        self._icon_logout_active   = _load_icon("log-out.svg", active_hex)

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self):

        # ── Logo ──────────────────────────────────────────────────────────
        logo_frame = ctk.CTkFrame(
            self, fg_color=COLORS["accent_green_dark"], corner_radius=0)
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
                    ratio   = 190 / pil_img.width
                    new_h   = int(pil_img.height * ratio)
                    pil_img = pil_img.resize((190, new_h), Image.LANCZOS)
                    ctk_img = ctk.CTkImage(
                        light_image=pil_img,
                        dark_image=pil_img,
                        size=(190, new_h),
                    )
                    ctk.CTkLabel(
                        logo_frame, image=ctk_img,
                        text="", fg_color="transparent",
                    ).pack(pady=12, padx=18)
                    logo_loaded = True
                    break
                except Exception:
                    pass

        if not logo_loaded:
            ctk.CTkLabel(
                logo_frame, text="Bingongold Credit",
                font=("Georgia", 13, "bold"),
                text_color=COLORS["accent_gold"],
            ).pack(pady=(14, 2), padx=16)
            ctk.CTkLabel(
                logo_frame, text="together as one",
                font=("Georgia", 10, "italic"),
                text_color=COLORS["sidebar_muted"],
            ).pack(pady=(0, 12), padx=16)

        # ── Gold divider ──────────────────────────────────────────────────
        ctk.CTkFrame(
            self, fg_color=COLORS["accent_gold"],
            height=2, corner_radius=0,
        ).pack(fill="x")
        ctk.CTkFrame(self, fg_color="transparent", height=6).pack()

        # ── Scrollable nav ────────────────────────────────────────────────
        nav_scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=COLORS["sidebar_hover"],
        )
        nav_scroll.pack(fill="both", expand=True, padx=8)

        for screen_name, icon_file, label in NAV_ITEMS:
            # Restrict Users and Logs to admin / manager only
            if screen_name in ("users", "logs") and self.current_user:
                if self.current_user.role.value == "loan_officer":
                    continue

            is_active  = screen_name == self.current_screen
            icon_image = (
                self._icons_active.get(icon_file)
                if is_active else
                self._icons_inactive.get(icon_file)
            )

            self._nav_row(
                parent      = nav_scroll,
                screen_name = screen_name,
                icon_image  = icon_image,
                icon_file   = icon_file,
                label       = label,
                is_active   = is_active,
            )

        # ── Bottom divider ────────────────────────────────────────────────
        ctk.CTkFrame(
            self, fg_color=COLORS["accent_gold"],
            height=1, corner_radius=0,
        ).pack(fill="x", padx=16, pady=(4, 0))

        # ── Current user info ─────────────────────────────────────────────
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

        # ── Logout row ────────────────────────────────────────────────────
        logout_frame = ctk.CTkFrame(
            self, fg_color="transparent",
            corner_radius=8, cursor="hand2",
        )
        logout_frame.pack(fill="x", padx=10, pady=(4, 14))

        # Use real icon or fallback to arrow text
        if self._icon_logout_inactive:
            logout_icon_lbl = ctk.CTkLabel(
                logout_frame,
                image=self._icon_logout_inactive,
                text="",
                width=38,
                anchor="center",
            )
        else:
            logout_icon_lbl = ctk.CTkLabel(
                logout_frame,
                text="→",
                font=FONTS["nav"],
                text_color=COLORS["accent_gold"],
                width=38,
                anchor="center",
            )
        logout_icon_lbl.pack(side="left", padx=(8, 0), pady=8)

        logout_lbl = ctk.CTkLabel(
            logout_frame,
            text="Logout",
            font=FONTS["nav"],
            text_color=COLORS["accent_gold"],
            anchor="w",
        )
        logout_lbl.pack(side="left", fill="x", expand=True, padx=(6, 8), pady=8)

        for widget in (logout_frame, logout_icon_lbl, logout_lbl):
            widget.bind("<Button-1>", lambda e: self.on_navigate("logout"))
            widget.bind("<Enter>",    lambda e: logout_frame.configure(
                fg_color=COLORS["sidebar_hover"]))
            widget.bind("<Leave>",    lambda e: logout_frame.configure(
                fg_color="transparent"))

    # ── Nav row builder ────────────────────────────────────────────────────────

    def _nav_row(self, parent, screen_name: str, icon_image,
                 icon_file: str, label: str, is_active: bool):
        """Build a single navigation row with icon + label."""

        row = ctk.CTkFrame(
            parent,
            fg_color=COLORS["accent_gold"] if is_active else "transparent",
            corner_radius=8,
            cursor="hand2",
        )
        row.pack(fill="x", pady=2)

        # ── Icon ───────────────────────────────────────────────────────────
        if icon_image:
            icon_lbl = ctk.CTkLabel(
                row,
                image=icon_image,
                text="",
                width=38,
                anchor="center",
            )
        else:
            # Fallback: first letter of label in the correct colour
            icon_lbl = ctk.CTkLabel(
                row,
                text=label[0],
                font=FONTS["nav"],
                text_color=(
                    COLORS["text_on_gold"] if is_active
                    else COLORS["sidebar_text"]
                ),
                width=38,
                anchor="center",
            )
        icon_lbl.pack(side="left", padx=(8, 0), pady=8)

        # ── Label ──────────────────────────────────────────────────────────
        text_lbl = ctk.CTkLabel(
            row,
            text=label,
            font=FONTS["nav"],
            text_color=(
                COLORS["text_on_gold"] if is_active
                else COLORS["sidebar_text"]
            ),
            anchor="w",
        )
        text_lbl.pack(side="left", fill="x", expand=True, padx=(6, 8), pady=8)

        # ── Hover bindings — swap icon tint on enter / leave ───────────────
        active_icon   = self._icons_active.get(icon_file)
        inactive_icon = self._icons_inactive.get(icon_file)

        def on_enter(_e):
            if not is_active:
                row.configure(fg_color=COLORS["sidebar_hover"])
                if active_icon:
                    try:
                        icon_lbl.configure(image=active_icon)
                    except Exception:
                        pass

        def on_leave(_e):
            if not is_active:
                row.configure(fg_color="transparent")
                if inactive_icon:
                    try:
                        icon_lbl.configure(image=inactive_icon)
                    except Exception:
                        pass

        for widget in (row, icon_lbl, text_lbl):
            widget.bind("<Button-1>", lambda e, s=screen_name: self.on_navigate(s))
            widget.bind("<Enter>",    on_enter)
            widget.bind("<Leave>",    on_leave)