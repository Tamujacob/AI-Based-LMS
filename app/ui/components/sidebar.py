"""
app/ui/components/sidebar.py
─────────────────────────────
Sidebar navigation using colourful PNG icons from assets/icons/.

Icons are loaded AS-IS (no colour tinting) so they keep their
original vivid colours. Active item gets a gold background.
Inactive items show the icon at reduced opacity for a polished look.

Run generate_icons.py once to create the PNG files.
"""

import os
import customtkinter as ctk
from PIL import Image, ImageEnhance
from app.ui.styles.theme import COLORS, FONTS, SIDEBAR_WIDTH

# ── Nav item definitions ───────────────────────────────────────────────────────
NAV_ITEMS = [
    ("dashboard",  "home.png",           "Dashboard"),
    ("clients",    "users.png",          "Clients"),
    ("loans",      "dollar-sign.png",    "Loans"),
    ("repayments", "credit-card.png",    "Repayments"),
    ("agent",      "cpu.png",            "AI Agent"),
    ("chatbot",    "message-circle.png", "AI Chatbot"),
    ("reports",    "bar-chart-2.png",    "Reports"),
    ("users",      "key.png",            "Users"),
    ("logs",       "clipboard.png",      "Activity Logs"),
    ("settings",   "settings.png",       "Settings"),
]

ICON_DIR  = "assets/icons"
ICON_SIZE = 22          # display size in sidebar
RENDER_SZ = ICON_SIZE * 2   # load at 2× for sharpness


# ── Icon loader ────────────────────────────────────────────────────────────────

def _load_icon_raw(filename: str, size: int = RENDER_SZ,
                   opacity: float = 1.0) -> ctk.CTkImage | None:
    """
    Load a PNG icon keeping its original colours.
    opacity: 1.0 = full colour, 0.55 = dimmed for inactive state.
    Returns a CTkImage or None if file not found.
    """
    path = os.path.join(ICON_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        img = Image.open(path).convert("RGBA").resize(
            (size, size), Image.LANCZOS)

        if opacity < 1.0:
            # Reduce alpha channel to create dimmed effect
            r, g, b, a = img.split()
            a = a.point(lambda p: int(p * opacity))
            img = Image.merge("RGBA", (r, g, b, a))

        return ctk.CTkImage(
            light_image=img,
            dark_image=img,
            size=(ICON_SIZE, ICON_SIZE),
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

        # Pre-load icon variants
        self._icons_full   = {}   # full colour (active / hover)
        self._icons_dim    = {}   # dimmed (inactive)
        self._logout_full  = None
        self._logout_dim   = None
        self._preload_icons()

        self._build()

    # ── Icon preloading ────────────────────────────────────────────────────────

    def _preload_icons(self):
        all_files = [item[1] for item in NAV_ITEMS] + ["log-out.png"]
        for filename in all_files:
            self._icons_full[filename] = _load_icon_raw(filename, opacity=1.0)
            self._icons_dim[filename]  = _load_icon_raw(filename, opacity=0.55)

        self._logout_full = self._icons_full.get("log-out.png")
        self._logout_dim  = self._icons_dim.get("log-out.png")

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
        ctk.CTkFrame(self, fg_color="transparent", height=4).pack()

        # ── Scrollable nav ────────────────────────────────────────────────
        nav_scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=COLORS["sidebar_hover"],
        )
        nav_scroll.pack(fill="both", expand=True, padx=6)

        for screen_name, icon_file, label in NAV_ITEMS:
            if screen_name in ("users", "logs") and self.current_user:
                if self.current_user.role.value == "loan_officer":
                    continue

            is_active = screen_name == self.current_screen
            self._nav_row(
                parent      = nav_scroll,
                screen_name = screen_name,
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
            user_frame.pack(fill="x", padx=16, pady=(8, 2))
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
        logout_frame.pack(fill="x", padx=8, pady=(4, 12))

        if self._logout_dim:
            logout_icon_lbl = ctk.CTkLabel(
                logout_frame,
                image=self._logout_dim,
                text="",
                width=36,
                anchor="center",
            )
        else:
            logout_icon_lbl = ctk.CTkLabel(
                logout_frame,
                text="→",
                font=FONTS["nav"],
                text_color=COLORS["accent_gold"],
                width=36,
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

        def logout_enter(_e):
            logout_frame.configure(fg_color=COLORS["sidebar_hover"])
            if self._logout_full:
                logout_icon_lbl.configure(image=self._logout_full)

        def logout_leave(_e):
            logout_frame.configure(fg_color="transparent")
            if self._logout_dim:
                logout_icon_lbl.configure(image=self._logout_dim)

        for widget in (logout_frame, logout_icon_lbl, logout_lbl):
            widget.bind("<Button-1>", lambda e: self.on_navigate("logout"))
            widget.bind("<Enter>",    logout_enter)
            widget.bind("<Leave>",    logout_leave)

    # ── Nav row builder ────────────────────────────────────────────────────────

    def _nav_row(self, parent, screen_name: str,
                 icon_file: str, label: str, is_active: bool):
        """Build one navigation row — full-colour icon, no tinting."""

        active_bg   = COLORS["accent_gold"]
        inactive_bg = "transparent"
        hover_bg    = COLORS["sidebar_hover"]

        row = ctk.CTkFrame(
            parent,
            fg_color=active_bg if is_active else inactive_bg,
            corner_radius=8,
            cursor="hand2",
        )
        row.pack(fill="x", pady=2)

        # Choose icon variant
        icon_img = (self._icons_full.get(icon_file)
                    if is_active else
                    self._icons_dim.get(icon_file))

        if icon_img:
            icon_lbl = ctk.CTkLabel(
                row, image=icon_img, text="",
                width=36, anchor="center",
            )
        else:
            icon_lbl = ctk.CTkLabel(
                row,
                text=label[0],
                font=FONTS["nav"],
                text_color=(COLORS["text_on_gold"] if is_active
                            else COLORS["sidebar_text"]),
                width=36, anchor="center",
            )
        icon_lbl.pack(side="left", padx=(8, 0), pady=7)

        text_lbl = ctk.CTkLabel(
            row,
            text=label,
            font=FONTS["nav"],
            text_color=(COLORS["text_on_gold"] if is_active
                        else COLORS["sidebar_text"]),
            anchor="w",
        )
        text_lbl.pack(side="left", fill="x", expand=True, padx=(6, 8), pady=7)

        # ── Hover: show full-colour icon on enter, dim on leave ────────────
        full_icon = self._icons_full.get(icon_file)
        dim_icon  = self._icons_dim.get(icon_file)

        def on_enter(_e):
            if not is_active:
                row.configure(fg_color=hover_bg)
                if full_icon:
                    icon_lbl.configure(image=full_icon)

        def on_leave(_e):
            if not is_active:
                row.configure(fg_color=inactive_bg)
                if dim_icon:
                    icon_lbl.configure(image=dim_icon)

        for widget in (row, icon_lbl, text_lbl):
            widget.bind("<Button-1>",
                        lambda e, s=screen_name: self.on_navigate(s))
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)