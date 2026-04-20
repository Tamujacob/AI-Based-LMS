"""
app/ui/screens/users_screen.py
User management — view, add, activate/deactivate users.
Accessible by Manager and Admin only.
"""

import customtkinter as ctk
from app.ui.styles.theme import COLORS, FONTS, primary_button_style, input_style, danger_button_style
from app.ui.components.sidebar import Sidebar
from app.ui.components.data_table import DataTable


class UsersScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master = master
        self.current_user = master.current_user
        self.selected_user = None
        self._build()
        self._load_users()

    def _navigate(self, screen):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        Sidebar(self, "users", self._navigate, self.current_user).grid(
            row=0, column=0, sticky="nsew")

        main = ctk.CTkFrame(self, fg_color=COLORS["bg_primary"])
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        self._build_list_panel(main)
        self._build_form_panel(main)

    def _build_list_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        panel.grid(row=0, column=0, sticky="nsew", padx=(24, 8), pady=24)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(2, weight=1)

        # Header
        hdr = ctk.CTkFrame(panel, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        hdr.columnconfigure(1, weight=1)
        ctk.CTkLabel(hdr, text="System Users",
                     font=FONTS["title"],
                     text_color=COLORS["accent_green_dark"]).grid(
            row=0, column=0, sticky="w")
        ctk.CTkButton(hdr, text="+ Add User", width=120,
                      command=self._new_user_form,
                      **primary_button_style()).grid(row=0, column=2, sticky="e")

        # Search
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._load_users())
        ctk.CTkEntry(panel, textvariable=self.search_var,
                     placeholder_text="Search by name or username...",
                     **input_style()).grid(row=1, column=0, sticky="ew",
                                          pady=(0, 12))

        # Table
        self.table = DataTable(
            panel,
            columns=[
                ("full_name", "Full Name",  160),
                ("username",  "Username",   120),
                ("role",      "Role",        110),
                ("status",    "Status",       80),
                ("last_login","Last Login",  120),
            ],
            on_select=self._on_user_selected,
        )
        self.table.grid(row=2, column=0, sticky="nsew")

    def _build_form_panel(self, parent):
        self.form_panel = ctk.CTkScrollableFrame(
            parent, fg_color=COLORS["bg_card"],
            corner_radius=12,
            border_width=1, border_color=COLORS["border"],
            scrollbar_button_color=COLORS["border"])
        self.form_panel.grid(row=0, column=1, sticky="nsew",
                              padx=(8, 24), pady=24)
        self.form_panel.columnconfigure(0, weight=1)
        self._show_empty_state()

    def _show_empty_state(self):
        for w in self.form_panel.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.form_panel,
                     text="Select a user\nor click + Add User",
                     font=FONTS["body"],
                     text_color=COLORS["text_muted"],
                     justify="center").pack(expand=True, pady=80)

    def _on_user_selected(self, row):
        from app.core.services.auth_service import AuthService
        users = AuthService.get_all_users()
        # Also get inactive users
        from app.database.connection import get_db
        from app.core.models.user import User
        with get_db() as db:
            user = db.query(User).filter_by(id=row["id"]).first()
            if user:
                db.expunge(user)
        self.selected_user = user
        if user:
            self._render_user_detail(user)

    def _render_user_detail(self, user):
        for w in self.form_panel.winfo_children():
            w.destroy()

        # Header
        ctk.CTkLabel(self.form_panel, text="User Details",
                     font=FONTS["subtitle"],
                     text_color=COLORS["accent_green_dark"]).pack(
            anchor="w", padx=20, pady=(20, 4))

        status_color = COLORS["accent_green"] if user.is_active else COLORS["danger"]
        status_text = "ACTIVE" if user.is_active else "INACTIVE"
        ctk.CTkLabel(self.form_panel, text=status_text,
                     font=FONTS["badge"], text_color=status_color).pack(
            anchor="w", padx=20)

        ctk.CTkFrame(self.form_panel, fg_color=COLORS["border"],
                     height=1).pack(fill="x", padx=20, pady=12)

        details = [
            ("Full Name",   user.full_name),
            ("Username",    user.username),
            ("Email",       user.email or "—"),
            ("Role",        user.role.value.replace("_", " ").title()),
            ("Status",      "Active" if user.is_active else "Inactive"),
            ("Created",     str(user.created_at.date()) if user.created_at else "—"),
            ("Last Login",  str(user.last_login.date()) if user.last_login else "Never"),
        ]
        for label, value in details:
            row = ctk.CTkFrame(self.form_panel, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=3)
            ctk.CTkLabel(row, text=label, font=FONTS["body_small"],
                         text_color=COLORS["text_muted"],
                         width=120, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value, font=FONTS["body_small"],
                         text_color=COLORS["text_primary"],
                         anchor="w").pack(side="left")

        ctk.CTkFrame(self.form_panel, fg_color=COLORS["border"],
                     height=1).pack(fill="x", padx=20, pady=12)

        # Action buttons
        btn_frame = ctk.CTkFrame(self.form_panel, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 8))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        if user.is_active:
            ctk.CTkButton(btn_frame, text="Deactivate Account",
                          fg_color=COLORS["warning"],
                          hover_color="#B8860B",
                          text_color=COLORS["text_on_gold"],
                          font=FONTS["button"],
                          corner_radius=8, height=38,
                          command=lambda: self._toggle_user(user.id, False)).grid(
                row=0, column=0, padx=(0, 4), sticky="ew")
        else:
            ctk.CTkButton(btn_frame, text="Activate Account",
                          fg_color=COLORS["accent_green"],
                          hover_color=COLORS["accent_green_dark"],
                          text_color="#FFFFFF",
                          font=FONTS["button"],
                          corner_radius=8, height=38,
                          command=lambda: self._toggle_user(user.id, True)).grid(
                row=0, column=0, padx=(0, 4), sticky="ew")

        ctk.CTkButton(btn_frame, text="Reset Password",
                      **primary_button_style(),
                      command=lambda: self._reset_password_form(user)).grid(
            row=0, column=1, padx=(4, 0), sticky="ew")

        # Logout / Force logout note
        ctk.CTkFrame(self.form_panel, fg_color=COLORS["border"],
                     height=1).pack(fill="x", padx=20, pady=12)

        ctk.CTkLabel(self.form_panel,
                     text="Account Management",
                     font=FONTS["subheading"],
                     text_color=COLORS["text_secondary"]).pack(
            anchor="w", padx=20, pady=(0, 8))

        ctk.CTkLabel(self.form_panel,
                     text=(
                         "To log out a user remotely, deactivate their account.\n"
                         "They will be unable to log in until reactivated.\n"
                         "Use this when a staff member is on leave or suspended."
                     ),
                     font=FONTS["body_small"],
                     text_color=COLORS["text_muted"],
                     justify="left",
                     wraplength=260).pack(anchor="w", padx=20)

    def _new_user_form(self):
        self.selected_user = None
        for w in self.form_panel.winfo_children():
            w.destroy()

        ctk.CTkLabel(self.form_panel, text="Create New User",
                     font=FONTS["subtitle"],
                     text_color=COLORS["accent_green_dark"]).pack(
            anchor="w", padx=20, pady=(20, 16))

        self.form_vars = {}
        fields = [
            ("full_name", "Full Name *",    False),
            ("username",  "Username *",     False),
            ("email",     "Email",          False),
            ("password",  "Password *",     True),
        ]
        for key, label, is_password in fields:
            ctk.CTkLabel(self.form_panel, text=label,
                         font=FONTS["body_small"],
                         text_color=COLORS["text_secondary"],
                         anchor="w").pack(fill="x", padx=20, pady=(8, 2))
            var = ctk.StringVar()
            self.form_vars[key] = var
            entry = ctk.CTkEntry(self.form_panel, textvariable=var,
                                  show="●" if is_password else "",
                                  **input_style())
            entry.pack(fill="x", padx=20)

        ctk.CTkLabel(self.form_panel, text="Role *",
                     font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"],
                     anchor="w").pack(fill="x", padx=20, pady=(10, 2))
        self.role_var = ctk.StringVar(value="loan_officer")
        ctk.CTkOptionMenu(self.form_panel, variable=self.role_var,
                          values=["loan_officer", "manager", "admin"],
                          fg_color=COLORS["bg_input"],
                          button_color=COLORS["accent_green"],
                          text_color=COLORS["text_primary"],
                          font=FONTS["body_small"]).pack(fill="x", padx=20)

        self.form_error = ctk.CTkLabel(self.form_panel, text="",
                                        font=FONTS["body_small"],
                                        text_color=COLORS["danger"])
        self.form_error.pack(padx=20, pady=(8, 0))

        ctk.CTkButton(self.form_panel, text="Create User",
                      command=self._create_user,
                      **primary_button_style()).pack(
            fill="x", padx=20, pady=(12, 20))

    def _create_user(self):
        from app.core.services.auth_service import AuthService
        try:
            AuthService.create_user(
                full_name=self.form_vars["full_name"].get().strip(),
                username=self.form_vars["username"].get().strip(),
                password=self.form_vars["password"].get(),
                role=self.role_var.get(),
                email=self.form_vars["email"].get().strip() or None,
            )
            self.form_error.configure(
                text="User created successfully.",
                text_color=COLORS["accent_green"])
            self._load_users()
        except Exception as e:
            self.form_error.configure(text=str(e),
                                       text_color=COLORS["danger"])

    def _toggle_user(self, user_id: int, activate: bool):
        from app.database.connection import get_db
        from app.core.models.user import User
        with get_db() as db:
            user = db.query(User).filter_by(id=user_id).first()
            if user:
                user.is_active = activate
                db.commit()
        self._load_users()
        self._show_empty_state()

    def _reset_password_form(self, user):
        for w in self.form_panel.winfo_children():
            w.destroy()

        ctk.CTkLabel(self.form_panel,
                     text=f"Reset Password\n{user.full_name}",
                     font=FONTS["subtitle"],
                     text_color=COLORS["accent_green_dark"],
                     justify="left").pack(anchor="w", padx=20, pady=(20, 16))

        self.new_pw_var = ctk.StringVar()
        ctk.CTkLabel(self.form_panel, text="New Password",
                     font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"],
                     anchor="w").pack(fill="x", padx=20)
        ctk.CTkEntry(self.form_panel, textvariable=self.new_pw_var,
                     show="●", **input_style()).pack(fill="x", padx=20, pady=(4, 0))

        self.pw_error = ctk.CTkLabel(self.form_panel, text="",
                                      font=FONTS["body_small"],
                                      text_color=COLORS["danger"])
        self.pw_error.pack(padx=20, pady=(8, 0))

        ctk.CTkButton(self.form_panel, text="Update Password",
                      command=lambda: self._do_reset(user.id),
                      **primary_button_style()).pack(
            fill="x", padx=20, pady=(12, 8))
        ctk.CTkButton(self.form_panel, text="Cancel",
                      fg_color="transparent",
                      border_color=COLORS["border"], border_width=1,
                      text_color=COLORS["text_secondary"],
                      hover_color=COLORS["bg_input"],
                      font=FONTS["button"], corner_radius=8, height=40,
                      command=lambda: self._on_user_selected({"id": user.id})).pack(
            fill="x", padx=20, pady=(0, 20))

    def _do_reset(self, user_id):
        from app.core.services.auth_service import AuthService
        pw = self.new_pw_var.get()
        if len(pw) < 6:
            self.pw_error.configure(text="Password must be at least 6 characters.")
            return
        AuthService.change_password(user_id, pw)
        self.pw_error.configure(text="Password updated.", text_color=COLORS["accent_green"])

    def _load_users(self, *args):
        from app.database.connection import get_db
        from app.core.models.user import User
        search = self.search_var.get().strip() if hasattr(self, "search_var") else None
        with get_db() as db:
            q = db.query(User)
            if search:
                term = f"%{search}%"
                q = q.filter(User.full_name.ilike(term) | User.username.ilike(term))
            users = q.order_by(User.full_name).all()
            for u in users:
                db.expunge(u)

        rows = [{
            "id":         u.id,
            "full_name":  u.full_name,
            "username":   u.username,
            "role":       u.role.value.replace("_", " ").title(),
            "status":     "Active" if u.is_active else "Inactive",
            "last_login": str(u.last_login.date()) if u.last_login else "Never",
        } for u in users]

        if hasattr(self, "table"):
            self.table.update_rows(rows)