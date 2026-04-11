"""
app/ui/screens/login_screen.py
─────────────────────────────────────────────
Authentication screen. Deep navy + gold branding.
Clean, professional financial institution aesthetic.
"""

import customtkinter as ctk
from app.ui.styles.theme import COLORS, FONTS, primary_button_style, input_style


class LoginScreen(ctk.CTkFrame):
    """Login screen shown at app launch."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self._build_ui()

    def _build_ui(self):
        # ── Two-column layout ──────────────────────────────────────────────
        self.columnconfigure(0, weight=1)  # Left brand panel
        self.columnconfigure(1, weight=1)  # Right login form
        self.rowconfigure(0, weight=1)

        self._build_brand_panel()
        self._build_form_panel()

    # ── Left Brand Panel ───────────────────────────────────────────────────
    def _build_brand_panel(self):
        brand = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=0)
        brand.grid(row=0, column=0, sticky="nsew")
        brand.columnconfigure(0, weight=1)
        brand.rowconfigure(0, weight=1)

        inner = ctk.CTkFrame(brand, fg_color="transparent")
        inner.grid(row=0, column=0, padx=60, pady=60, sticky="nsew")
        inner.columnconfigure(0, weight=1)

        # Gold accent bar
        bar = ctk.CTkFrame(inner, fg_color=COLORS["accent_gold"], height=4, corner_radius=2)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 30))

        # Institution name
        ctk.CTkLabel(
            inner,
            text="BINGONGOLD",
            font=("Georgia", 36, "bold"),
            text_color=COLORS["accent_gold"],
        ).grid(row=1, column=0, sticky="w")

        ctk.CTkLabel(
            inner,
            text="CREDIT",
            font=("Georgia", 36),
            text_color=COLORS["text_primary"],
        ).grid(row=2, column=0, sticky="w")

        ctk.CTkLabel(
            inner,
            text="Loans Management System",
            font=FONTS["subheading"],
            text_color=COLORS["text_secondary"],
        ).grid(row=3, column=0, sticky="w", pady=(4, 40))

        # Decorative divider
        div = ctk.CTkFrame(inner, fg_color=COLORS["border"], height=1)
        div.grid(row=4, column=0, sticky="ew", pady=(0, 30))

        # Feature bullets
        features = [
            "✦  Automated Interest Calculations",
            "✦  AI-Powered Risk Assessment",
            "✦  Natural Language Chatbot",
            "✦  Real-Time Repayment Tracking",
            "✦  Secure Role-Based Access",
        ]
        for i, feat in enumerate(features):
            ctk.CTkLabel(
                inner,
                text=feat,
                font=FONTS["body"],
                text_color=COLORS["text_secondary"],
                anchor="w",
            ).grid(row=5 + i, column=0, sticky="w", pady=4)

        # Version tag at bottom
        ctk.CTkLabel(
            brand,
            text="Ham Tower · Wandegeya · Kampala",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
        ).grid(row=1, column=0, pady=(0, 20))

    # ── Right Form Panel ───────────────────────────────────────────────────
    def _build_form_panel(self):
        form_bg = ctk.CTkFrame(self, fg_color=COLORS["bg_primary"], corner_radius=0)
        form_bg.grid(row=0, column=1, sticky="nsew")
        form_bg.columnconfigure(0, weight=1)
        form_bg.rowconfigure(0, weight=1)

        card = ctk.CTkFrame(form_bg, fg_color=COLORS["bg_card"], corner_radius=16, width=400)
        card.grid(row=0, column=0, padx=80, pady=80, sticky="")
        card.columnconfigure(0, weight=1)

        # Header
        ctk.CTkLabel(
            card,
            text="Welcome Back",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
        ).grid(row=0, column=0, padx=40, pady=(40, 4), sticky="w")

        ctk.CTkLabel(
            card,
            text="Sign in to your account",
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
        ).grid(row=1, column=0, padx=40, pady=(0, 30), sticky="w")

        # Username
        ctk.CTkLabel(
            card, text="Username",
            font=FONTS["subheading"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).grid(row=2, column=0, padx=40, pady=(0, 6), sticky="w")

        self.username_var = ctk.StringVar()
        self.username_entry = ctk.CTkEntry(
            card,
            textvariable=self.username_var,
            placeholder_text="Enter your username",
            **input_style(),
        )
        self.username_entry.grid(row=3, column=0, padx=40, pady=(0, 20), sticky="ew")

        # Password
        ctk.CTkLabel(
            card, text="Password",
            font=FONTS["subheading"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).grid(row=4, column=0, padx=40, pady=(0, 6), sticky="w")

        self.password_var = ctk.StringVar()
        self.password_entry = ctk.CTkEntry(
            card,
            textvariable=self.password_var,
            placeholder_text="Enter your password",
            show="•",
            **input_style(),
        )
        self.password_entry.grid(row=5, column=0, padx=40, pady=(0, 10), sticky="ew")

        # Error label (hidden by default)
        self.error_label = ctk.CTkLabel(
            card,
            text="",
            font=FONTS["body_small"],
            text_color=COLORS["danger"],
            anchor="w",
        )
        self.error_label.grid(row=6, column=0, padx=40, sticky="w")

        # Login button
        self.login_btn = ctk.CTkButton(
            card,
            text="Sign In",
            command=self._handle_login,
            **primary_button_style(),
        )
        self.login_btn.grid(row=7, column=0, padx=40, pady=(20, 40), sticky="ew")

        # Bind Enter key
        self.username_entry.bind("<Return>", lambda e: self.password_entry.focus())
        self.password_entry.bind("<Return>", lambda e: self._handle_login())
        self.username_entry.focus()

    # ── Login Logic ────────────────────────────────────────────────────────
    def _handle_login(self):
        username = self.username_var.get().strip()
        password = self.password_var.get()

        if not username or not password:
            self._show_error("Please enter both username and password.")
            return

        self.login_btn.configure(state="disabled", text="Signing in...")
        self.after(100, lambda: self._authenticate(username, password))

    def _authenticate(self, username: str, password: str):
        try:
            from app.core.services.auth_service import AuthService
            user = AuthService.authenticate(username, password)
            if user:
                self.master.login(user)
            else:
                self._show_error("Invalid username or password.")
                self.login_btn.configure(state="normal", text="Sign In")
        except Exception as e:
            self._show_error(f"Connection error: {e}")
            self.login_btn.configure(state="normal", text="Sign In")

    def _show_error(self, message: str):
        self.error_label.configure(text=message)