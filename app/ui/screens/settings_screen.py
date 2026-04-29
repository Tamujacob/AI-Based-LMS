"""
app/ui/screens/settings_screen.py
─────────────────────────────────────────────
System settings — user account management,
password changes, and system info.
Updated: Claude API replaced with Groq API.
"""

import customtkinter as ctk
from app.ui.styles.theme import COLORS, FONTS, primary_button_style, input_style, danger_button_style
from app.ui.components.sidebar import Sidebar


class SettingsScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master = master
        self.current_user = master.current_user
        self._build()

    def _navigate(self, screen):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        Sidebar(self, "settings", self._navigate, self.current_user).grid(
            row=0, column=0, sticky="nsew"
        )

        main = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_primary"],
                                      scrollbar_button_color=COLORS["bg_hover"])
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)

        ctk.CTkLabel(main, text="Settings", font=FONTS["title"],
                     text_color=COLORS["text_primary"]).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=32, pady=(28, 24))

        self._build_change_password(main)
        self._build_user_management(main)
        self._build_system_info(main)

    # ── Change Password ────────────────────────────────────────────────────────

    def _build_change_password(self, parent):
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=12)
        card.grid(row=1, column=0, sticky="nsew", padx=(32, 12), pady=(0, 16))
        card.columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="Change Password", font=FONTS["subheading"],
                     text_color=COLORS["text_primary"]).pack(
            anchor="w", padx=20, pady=(20, 16))

        self.old_pw     = ctk.StringVar()
        self.new_pw     = ctk.StringVar()
        self.confirm_pw = ctk.StringVar()

        for label, var in [
            ("Current Password",     self.old_pw),
            ("New Password",         self.new_pw),
            ("Confirm New Password", self.confirm_pw),
        ]:
            ctk.CTkLabel(card, text=label, font=FONTS["body_small"],
                         text_color=COLORS["text_secondary"], anchor="w").pack(
                fill="x", padx=20, pady=(4, 2))
            ctk.CTkEntry(card, textvariable=var, show="•",
                         **input_style()).pack(fill="x", padx=20)

        self.pw_error = ctk.CTkLabel(card, text="", font=FONTS["body_small"],
                                      text_color=COLORS["danger"])
        self.pw_error.pack(padx=20, pady=(8, 0))

        ctk.CTkButton(card, text="Update Password",
                      command=self._change_password,
                      **primary_button_style()).pack(
            fill="x", padx=20, pady=(12, 20))

    def _change_password(self):
        from app.core.services.auth_service import AuthService
        import bcrypt

        old     = self.old_pw.get()
        new     = self.new_pw.get()
        confirm = self.confirm_pw.get()

        if not old or not new or not confirm:
            self.pw_error.configure(text="All fields are required.")
            return
        if new != confirm:
            self.pw_error.configure(text="New passwords do not match.")
            return
        if len(new) < 6:
            self.pw_error.configure(text="Password must be at least 6 characters.")
            return
        if not bcrypt.checkpw(old.encode(),
                               self.current_user.password_hash.encode()):
            self.pw_error.configure(text="Current password is incorrect.")
            return

        AuthService.change_password(self.current_user.id, new)
        self.pw_error.configure(
            text="✔ Password updated successfully.",
            text_color=COLORS["success"])
        self.old_pw.set("")
        self.new_pw.set("")
        self.confirm_pw.set("")

    # ── User Management (Admin only) ───────────────────────────────────────────

    def _build_user_management(self, parent):
        if not (self.current_user and self.current_user.is_admin):
            return

        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=12)
        card.grid(row=1, column=1, sticky="nsew", padx=(12, 32), pady=(0, 16))
        card.columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="Create New User", font=FONTS["subheading"],
                     text_color=COLORS["text_primary"]).pack(
            anchor="w", padx=20, pady=(20, 16))

        self.new_fullname = ctk.StringVar()
        self.new_username = ctk.StringVar()
        self.new_password = ctk.StringVar()
        self.new_role     = ctk.StringVar(value="loan_officer")

        for label, var in [
            ("Full Name", self.new_fullname),
            ("Username",  self.new_username),
            ("Password",  self.new_password),
        ]:
            ctk.CTkLabel(card, text=label, font=FONTS["body_small"],
                         text_color=COLORS["text_secondary"], anchor="w").pack(
                fill="x", padx=20, pady=(4, 2))
            ctk.CTkEntry(card, textvariable=var,
                         show="•" if "Password" in label else "",
                         **input_style()).pack(fill="x", padx=20)

        ctk.CTkLabel(card, text="Role", font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"], anchor="w").pack(
            fill="x", padx=20, pady=(10, 2))
        ctk.CTkOptionMenu(card, variable=self.new_role,
                          values=["loan_officer", "manager", "admin"],
                          fg_color=COLORS["bg_input"],
                          button_color=COLORS["bg_hover"],
                          text_color=COLORS["text_primary"],
                          font=FONTS["body_small"]).pack(fill="x", padx=20)

        self.user_error = ctk.CTkLabel(card, text="", font=FONTS["body_small"],
                                        text_color=COLORS["danger"])
        self.user_error.pack(padx=20, pady=(8, 0))

        ctk.CTkButton(card, text="Create User",
                      command=self._create_user,
                      **primary_button_style()).pack(
            fill="x", padx=20, pady=(12, 20))

    def _create_user(self):
        from app.core.services.auth_service import AuthService
        try:
            AuthService.create_user(
                full_name=self.new_fullname.get().strip(),
                username =self.new_username.get().strip(),
                password =self.new_password.get(),
                role     =self.new_role.get(),
            )
            self.user_error.configure(
                text="✔ User created successfully.",
                text_color=COLORS["success"])
            self.new_fullname.set("")
            self.new_username.set("")
            self.new_password.set("")
        except Exception as e:
            self.user_error.configure(text=str(e),
                                       text_color=COLORS["danger"])

    # ── System Information ─────────────────────────────────────────────────────

    def _build_system_info(self, parent):
        # ── Import only what exists in settings.py now ──
        from app.config.settings import (
            APP_NAME, APP_VERSION, DATABASE_URL,
            GROQ_API_KEY, GROQ_MODEL,
        )

        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=12)
        card.grid(row=2, column=0, columnspan=2, sticky="ew",
                  padx=32, pady=(0, 32))
        card.columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="System Information", font=FONTS["subheading"],
                     text_color=COLORS["text_primary"]).pack(
            anchor="w", padx=20, pady=(20, 12))

        # Mask API key — show first 8 chars then ***
        masked_key = (
            f"{GROQ_API_KEY[:8]}{'*' * 16}" if GROQ_API_KEY else "Not configured"
        )

        # DB connection — show only host/db, hide password
        db_display = (
            DATABASE_URL.split("@")[-1]
            if "@" in DATABASE_URL
            else DATABASE_URL
        )

        info_rows = [
            ("Application",  APP_NAME),
            ("Version",      APP_VERSION),
            ("AI Provider",  "Groq (Free Tier)"),
            ("AI Model",     GROQ_MODEL),
            ("Groq API Key", masked_key),
            ("Database",     db_display),
            ("Institution",  "Bingongold Credit, Ham Tower, Wandegeya, Kampala"),
            ("Developer",    "Tamukedde Jacob  |  24/BIT/BU/R/0010  |  Bugema University"),
        ]

        for label, value in info_rows:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=3)
            ctk.CTkLabel(row, text=label,
                         font=FONTS["body_small"],
                         text_color=COLORS["text_muted"],
                         width=130, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value,
                         font=FONTS["body_small"],
                         text_color=COLORS["text_primary"],
                         anchor="w").pack(side="left")

        # ── Groq API status check button ───────────────────────────────────
        ctk.CTkFrame(card, fg_color=COLORS["border"],
                     height=1).pack(fill="x", padx=20, pady=(16, 8))

        self.api_status_label = ctk.CTkLabel(
            card, text="",
            font=FONTS["body_small"],
            text_color=COLORS["text_muted"])
        self.api_status_label.pack(anchor="w", padx=20)

        ctk.CTkButton(
            card,
            text="Test Groq API Connection",
            height=38,
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["accent_green_dark"],
            text_color="#FFFFFF",
            font=FONTS["button"],
            corner_radius=8,
            command=self._test_groq_connection,
        ).pack(fill="x", padx=20, pady=(8, 20))

    def _test_groq_connection(self):
        """Send a tiny test message to Groq and report success or failure."""
        import threading
        self.api_status_label.configure(
            text="Testing connection...",
            text_color=COLORS["text_muted"])
        threading.Thread(target=self._run_groq_test, daemon=True).start()

    def _run_groq_test(self):
        try:
            from app.config.settings import GROQ_API_KEY, GROQ_MODEL
            from groq import Groq

            if not GROQ_API_KEY:
                self.after(0, lambda: self.api_status_label.configure(
                    text="✗  GROQ_API_KEY is not set in your .env file.",
                    text_color=COLORS["danger"]))
                return

            client = Groq(api_key=GROQ_API_KEY)
            client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user",
                            "content": "Reply with: OK"}],
                max_tokens=5,
            )
            self.after(0, lambda: self.api_status_label.configure(
                text=f"✔  Groq API connected successfully — model: {GROQ_MODEL}",
                text_color=COLORS["success"]))

        except Exception as e:
            msg = str(e)[:80]
            self.after(0, lambda: self.api_status_label.configure(
                text=f"✗  Connection failed: {msg}",
                text_color=COLORS["danger"]))