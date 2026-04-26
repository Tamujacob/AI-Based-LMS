"""
app/ui/screens/login_screen.py
Bingongold Credit branded login screen.
"""

import customtkinter as ctk
import os
from PIL import Image
from app.ui.styles.theme import COLORS, FONTS, primary_button_style, input_style


def _load_logo(width=220):
    search_paths = [
        "assets/images/logo.png",
        "./assets/images/logo.png",
        os.path.expanduser("~/Desktop/AI-Based-LMS/assets/images/logo.png"),
    ]
    for path in search_paths:
        if os.path.exists(path):
            try:
                img = Image.open(path)
                ratio = width / img.width
                new_h = int(img.height * ratio)
                img = img.resize((width, new_h), Image.LANCZOS)
                return ctk.CTkImage(light_image=img, dark_image=img,
                                    size=(width, new_h)), new_h
            except Exception:
                pass
    return None, 0


class LoginScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self._destroyed = False
        self._build_ui()

    def destroy(self):
        self._destroyed = True
        super().destroy()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_brand_panel()
        self._build_form_panel()

    def _build_brand_panel(self):
        brand = ctk.CTkFrame(self, fg_color=COLORS["accent_green"], corner_radius=0)
        brand.grid(row=0, column=0, sticky="nsew")
        brand.columnconfigure(0, weight=1)
        brand.rowconfigure(0, weight=1)

        inner = ctk.CTkFrame(brand, fg_color="transparent")
        inner.grid(row=0, column=0, padx=50, pady=60, sticky="nsew")
        inner.columnconfigure(0, weight=1)

        logo_img, logo_h = _load_logo(width=240)
        if logo_img:
            ctk.CTkLabel(inner, image=logo_img, text="",
                         fg_color="transparent").grid(row=0, column=0, pady=(0, 24))
        else:
            ctk.CTkLabel(inner, text="Bingongold Credit",
                         font=("Georgia", 28, "bold"),
                         text_color=COLORS["accent_gold"]).grid(
                row=0, column=0, pady=(0, 4))
            ctk.CTkLabel(inner, text="together as one",
                         font=("Georgia", 13, "italic"),
                         text_color="#CCFFCC").grid(
                row=1, column=0, pady=(0, 24))

        ctk.CTkFrame(inner, fg_color=COLORS["accent_gold"],
                     height=3, corner_radius=2).grid(
            row=2, column=0, sticky="ew", pady=(0, 24))

        features = [
            "Automated Loan Processing",
            "AI-Powered Risk Assessment",
            "Natural Language Chatbot",
            "Real-Time Repayment Tracking",
            "Secure Role-Based Access",
        ]
        for i, feat in enumerate(features):
            row_f = ctk.CTkFrame(inner, fg_color="transparent")
            row_f.grid(row=3+i, column=0, sticky="w", pady=4)
            ctk.CTkLabel(row_f, text="●", font=("Helvetica", 10),
                         text_color=COLORS["accent_gold"], width=20).pack(side="left")
            ctk.CTkLabel(row_f, text=feat, font=FONTS["body"],
                         text_color="#DDFFDD").pack(side="left", padx=(4, 0))

        ctk.CTkLabel(brand,
                     text="Ham Tower  ·  Wandegeya  ·  Kampala, Uganda",
                     font=FONTS["caption"],
                     text_color="#AADDAA").grid(row=1, column=0, pady=(0, 16))

    def _build_form_panel(self):
        form_bg = ctk.CTkFrame(self, fg_color="#FFFFFF", corner_radius=0)
        form_bg.grid(row=0, column=1, sticky="nsew")
        form_bg.columnconfigure(0, weight=1)
        form_bg.rowconfigure(0, weight=1)

        card = ctk.CTkFrame(form_bg, fg_color="#FFFFFF",
                             corner_radius=16,
                             border_width=1,
                             border_color=COLORS["border"],
                             width=380)
        card.grid(row=0, column=0, padx=70, pady=80, sticky="")
        card.columnconfigure(0, weight=1)

        logo_img, _ = _load_logo(width=160)
        if logo_img:
            ctk.CTkLabel(card, image=logo_img, text="",
                         fg_color="transparent").grid(
                row=0, column=0, pady=(28, 8))
        else:
            ctk.CTkLabel(card, text="Bingongold",
                         font=("Georgia", 18, "bold"),
                         text_color=COLORS["accent_green"]).grid(
                row=0, column=0, pady=(28, 8))

        ctk.CTkFrame(card, fg_color=COLORS["accent_green"],
                     height=4, corner_radius=2).grid(
            row=1, column=0, sticky="ew", padx=32, pady=(0, 20))

        ctk.CTkLabel(card, text="Welcome Back",
                     font=FONTS["title"],
                     text_color=COLORS["accent_green_dark"]).grid(
            row=2, column=0, padx=32, pady=(0, 4), sticky="w")

        ctk.CTkLabel(card, text="Sign in to Bingongold Credit LMS",
                     font=FONTS["body"],
                     text_color=COLORS["text_secondary"]).grid(
            row=3, column=0, padx=32, pady=(0, 24), sticky="w")

        ctk.CTkLabel(card, text="Username", font=FONTS["subheading"],
                     text_color=COLORS["text_secondary"],
                     anchor="w").grid(row=4, column=0, padx=32,
                                      pady=(0, 6), sticky="w")
        self.username_var = ctk.StringVar()
        self.username_entry = ctk.CTkEntry(
            card, textvariable=self.username_var,
            placeholder_text="Enter your username",
            **input_style())
        self.username_entry.grid(row=5, column=0, padx=32,
                                  pady=(0, 16), sticky="ew")

        ctk.CTkLabel(card, text="Password", font=FONTS["subheading"],
                     text_color=COLORS["text_secondary"],
                     anchor="w").grid(row=6, column=0, padx=32,
                                      pady=(0, 6), sticky="w")
        self.password_var = ctk.StringVar()
        self.password_entry = ctk.CTkEntry(
            card, textvariable=self.password_var,
            placeholder_text="Enter your password",
            show="●", **input_style())
        self.password_entry.grid(row=7, column=0, padx=32,
                                  pady=(0, 10), sticky="ew")

        self.error_label = ctk.CTkLabel(card, text="",
                                         font=FONTS["body_small"],
                                         text_color=COLORS["danger"],
                                         anchor="w")
        self.error_label.grid(row=8, column=0, padx=32, sticky="w")

        self.login_btn = ctk.CTkButton(
            card, text="Sign In",
            command=self._handle_login,
            **primary_button_style())
        self.login_btn.grid(row=9, column=0, padx=32,
                             pady=(16, 20), sticky="ew")

        ctk.CTkLabel(card,
                     text='"together as one"',
                     font=FONTS["tagline"],
                     text_color=COLORS["accent_green"]).grid(
            row=10, column=0, pady=(0, 28))

        self.username_entry.bind("<Return>", lambda e: self.password_entry.focus())
        self.password_entry.bind("<Return>", lambda e: self._handle_login())
        self.username_entry.focus()

    def _handle_login(self):
        username = self.username_var.get().strip()
        password = self.password_var.get()
        if not username or not password:
            self._show_error("Please enter both username and password.")
            return
        self.login_btn.configure(state="disabled", text="Signing in...")
        self.after(100, lambda: self._authenticate(username, password))

    def _authenticate(self, username: str, password: str):
        # ── KEY FIX: check if widget is still alive before updating ──
        if self._destroyed:
            return
        try:
            from app.core.services.auth_service import AuthService
            user = AuthService.authenticate(username, password)
            if self._destroyed:
                return
            if user == "inactive":
                self._show_error("This account has been deactivated. Contact your administrator.")
                if not self._destroyed:
                    self.login_btn.configure(state="normal", text="Sign In")
            elif user:
                self.master.login(user)
            else:
                self._show_error("Invalid username or password.")
                if not self._destroyed:
                    self.login_btn.configure(state="normal", text="Sign In")
        except Exception as e:
            if not self._destroyed:
                self._show_error(f"Error: {e}")
                self.login_btn.configure(state="normal", text="Sign In")

    def _show_error(self, message: str):
        if self._destroyed:
            return
        try:
            self.error_label.configure(text=message)
        except Exception:
            pass