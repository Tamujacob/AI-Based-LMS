"""
app/ui/screens/clients_screen.py
Client management — searchable table, add/edit client form with
visible placeholders and DatePicker on date of birth.
"""

import customtkinter as ctk
from datetime import date, datetime
from app.ui.styles.theme import (COLORS, FONTS, primary_button_style,
                                  danger_button_style, input_style)
from app.ui.components.sidebar import Sidebar
from app.ui.components.data_table import DataTable
from app.ui.components.date_picker import DatePicker


class ClientsScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master = master
        self.current_user = master.current_user
        self.selected_client = None
        self._build()
        self._load_clients()

    def _navigate(self, screen):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        Sidebar(self, "clients", self._navigate, self.current_user).grid(
            row=0, column=0, sticky="nsew")
        main = ctk.CTkFrame(self, fg_color=COLORS["bg_primary"])
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)
        self._build_list_panel(main)
        self._build_form_panel(main)

    # ── Left: Client List ──────────────────────────────────────────────────
    def _build_list_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        panel.grid(row=0, column=0, sticky="nsew", padx=(24, 8), pady=24)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(2, weight=1)

        ctk.CTkLabel(panel, text="Clients", font=FONTS["title"],
                     text_color=COLORS["text_primary"]).grid(
            row=0, column=0, sticky="w", pady=(0, 16))

        search_row = ctk.CTkFrame(panel, fg_color="transparent")
        search_row.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        search_row.columnconfigure(0, weight=1)

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._load_clients())
        ctk.CTkEntry(search_row, textvariable=self.search_var,
                     placeholder_text="🔍  Search by name, NIN or phone...",
                     **input_style()).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(search_row, text="+ Add Client", width=130,
                      command=self._new_client_form,
                      **primary_button_style()).grid(row=0, column=1, padx=(8, 0))

        self.table = DataTable(
            panel,
            columns=[
                ("full_name",    "Full Name",  200),
                ("nin",          "NIN",        120),
                ("phone_number", "Phone",      110),
                ("occupation",   "Occupation", 130),
            ],
            on_select=self._on_client_selected)
        self.table.grid(row=2, column=0, sticky="nsew")

    # ── Right: Form Panel ──────────────────────────────────────────────────
    def _build_form_panel(self, parent):
        self.form_panel = ctk.CTkScrollableFrame(
            parent, fg_color=COLORS["bg_card"], corner_radius=12,
            scrollbar_button_color=COLORS["bg_hover"])
        self.form_panel.grid(row=0, column=1, sticky="nsew",
                              padx=(8, 24), pady=24)
        self.form_panel.columnconfigure(0, weight=1)
        self._show_empty_form_state()

    def _show_empty_form_state(self):
        for w in self.form_panel.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.form_panel,
                     text="Select a client\nor click + Add Client",
                     font=FONTS["body"], text_color=COLORS["text_muted"],
                     justify="center").pack(expand=True, pady=80)

    def _new_client_form(self):
        self.selected_client = None
        self._render_form(data={})

    def _on_client_selected(self, row):
        from app.core.services.client_service import ClientService
        client = ClientService.get_client_by_id(row["id"])
        self.selected_client = client
        if client:
            self._render_form(data={
                "full_name":                 client.full_name or "",
                "nin":                       client.nin or "",
                "phone_number":              client.phone_number or "",
                "alt_phone_number":          client.alt_phone_number or "",
                "email":                     client.email or "",
                "date_of_birth":             str(client.date_of_birth) if client.date_of_birth else "",
                "gender":                    client.gender or "",
                "district":                  client.district or "",
                "village":                   client.village or "",
                "physical_address":          client.physical_address or "",
                "occupation":                client.occupation or "",
                "employer_name":             client.employer_name or "",
                "monthly_income":            str(client.monthly_income) if client.monthly_income else "",
                "next_of_kin_name":          client.next_of_kin_name or "",
                "next_of_kin_phone":         client.next_of_kin_phone or "",
                "next_of_kin_relationship":  client.next_of_kin_relationship or "",
                "notes":                     client.notes or "",
            })

    # ── Form renderer ──────────────────────────────────────────────────────
    def _render_form(self, data: dict):
        for w in self.form_panel.winfo_children():
            w.destroy()

        is_edit = self.selected_client is not None
        ctk.CTkLabel(self.form_panel,
                     text="Edit Client" if is_edit else "New Client",
                     font=FONTS["subtitle"],
                     text_color=COLORS["text_primary"]).pack(
            anchor="w", padx=20, pady=(20, 4))

        # Store entry widget references for reading on save
        self._entries = {}

        # ── Personal Information ───────────────────────────────────────
        self._section("Personal Information")

        self._entry_field("full_name",    "Full Name *",       "e.g.  John Mukasa",          data)
        self._entry_field("nin",          "National ID (NIN)", "e.g.  CM12345678AB",          data)
        self._entry_field("gender",       "Gender",            "Male  or  Female",            data)

        # Date of Birth — DatePicker
        self._label("Date of Birth")
        dob_str = data.get("date_of_birth", "")
        try:
            dob_initial = datetime.strptime(dob_str, "%Y-%m-%d").date() if dob_str else date(2000, 1, 1)
        except ValueError:
            dob_initial = date(2000, 1, 1)
        dob_row = ctk.CTkFrame(self.form_panel, fg_color="transparent")
        dob_row.pack(fill="x", padx=20)
        dob_row.columnconfigure(0, weight=1)
        self.dob_picker = DatePicker(dob_row, initial_date=dob_initial)
        self.dob_picker.grid(row=0, column=0, sticky="ew")

        # ── Contact Details ────────────────────────────────────────────
        self._section("Contact Details")

        self._entry_field("phone_number",     "Phone Number *",  "e.g.  0701234567",   data)
        self._entry_field("alt_phone_number", "Alt. Phone",      "e.g.  0771234567",   data)
        self._entry_field("email",            "Email",           "e.g.  john@mail.com",data)

        # ── Location ───────────────────────────────────────────────────
        self._section("Location")

        self._entry_field("district", "District",        "e.g.  Kampala",    data)
        self._entry_field("village",  "Village / Parish","e.g.  Wandegeya",  data)

        self._label("Physical Address")
        addr_widget = ctk.CTkTextbox(
            self.form_panel, height=60,
            fg_color=COLORS["bg_input"],
            text_color=COLORS["text_primary"],
            font=FONTS["body"])
        addr_widget.pack(fill="x", padx=20)
        if data.get("physical_address"):
            addr_widget.insert("1.0", data["physical_address"])
        else:
            addr_widget.insert("1.0", "e.g.  Plot 5, Kampala Road, Kampala")
            addr_widget.configure(text_color=COLORS["text_muted"])
            addr_widget.bind("<FocusIn>",  lambda e: self._clear_hint(addr_widget,  "e.g.  Plot 5, Kampala Road, Kampala"))
            addr_widget.bind("<FocusOut>", lambda e: self._restore_hint(addr_widget,"e.g.  Plot 5, Kampala Road, Kampala"))
        self._entries["physical_address_widget"] = addr_widget

        # ── Employment ─────────────────────────────────────────────────
        self._section("Employment")

        self._entry_field("occupation",    "Occupation",              "e.g.  Teacher, Trader, Farmer", data)
        self._entry_field("employer_name", "Employer / Business Name","e.g.  Kampala City Council",    data)
        self._entry_field("monthly_income","Monthly Income (UGX)",    "e.g.  500000",                  data)

        # ── Next of Kin ────────────────────────────────────────────────
        self._section("Next of Kin")

        self._entry_field("next_of_kin_name",         "Full Name",         "e.g.  Mary Mukasa",      data)
        self._entry_field("next_of_kin_phone",        "Phone Number",      "e.g.  0712345678",       data)
        self._entry_field("next_of_kin_relationship", "Relationship",      "e.g.  Spouse, Parent",   data)

        # ── Notes ──────────────────────────────────────────────────────
        self._section("Additional Notes")

        self._label("Notes")
        notes_widget = ctk.CTkTextbox(
            self.form_panel, height=70,
            fg_color=COLORS["bg_input"],
            text_color=COLORS["text_primary"],
            font=FONTS["body"])
        notes_widget.pack(fill="x", padx=20)
        if data.get("notes"):
            notes_widget.insert("1.0", data["notes"])
        else:
            notes_widget.insert("1.0", "Any additional information about the client...")
            notes_widget.configure(text_color=COLORS["text_muted"])
            notes_widget.bind("<FocusIn>",  lambda e: self._clear_hint(notes_widget,  "Any additional information about the client..."))
            notes_widget.bind("<FocusOut>", lambda e: self._restore_hint(notes_widget,"Any additional information about the client..."))
        self._entries["notes_widget"] = notes_widget

        # ── Error + buttons ────────────────────────────────────────────
        self.form_error = ctk.CTkLabel(
            self.form_panel, text="",
            font=FONTS["body_small"], text_color=COLORS["danger"])
        self.form_error.pack(padx=20, pady=(10, 0))

        btn_row = ctk.CTkFrame(self.form_panel, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(10, 24))
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)

        ctk.CTkButton(btn_row, text="💾  Save Client",
                      command=self._save_client,
                      **primary_button_style()).grid(
            row=0, column=0, padx=(0, 4), sticky="ew")
        if is_edit:
            ctk.CTkButton(btn_row, text="🗑  Delete",
                          command=self._delete_client,
                          **danger_button_style()).grid(
                row=0, column=1, padx=(4, 0), sticky="ew")

    # ── Helpers ───────────────────────────────────────────────────────────
    def _section(self, text: str):
        """Styled section divider."""
        ctk.CTkFrame(self.form_panel, fg_color=COLORS["border"],
                     height=1).pack(fill="x", padx=20, pady=(14, 0))
        ctk.CTkLabel(self.form_panel, text=text,
                     font=FONTS["subheading"],
                     text_color=COLORS["accent_green_dark"],
                     anchor="w").pack(fill="x", padx=20, pady=(6, 4))

    def _label(self, text: str):
        ctk.CTkLabel(self.form_panel, text=text,
                     font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"],
                     anchor="w").pack(fill="x", padx=20, pady=(8, 2))

    def _entry_field(self, key: str, label: str, placeholder: str, data: dict):
        """
        Render a label + CTkEntry.
        If data[key] has a value, set it via StringVar (placeholder hidden).
        If data[key] is empty, bind NO StringVar so CustomTkinter shows the
        placeholder text natively.
        """
        self._label(label)
        existing = data.get(key, "")
        if existing:
            # Pre-fill with existing value
            var = ctk.StringVar(value=existing)
            entry = ctk.CTkEntry(self.form_panel, textvariable=var,
                                 placeholder_text=placeholder, **input_style())
            self._entries[key + "_var"] = var
        else:
            # No StringVar — placeholder will be visible
            entry = ctk.CTkEntry(self.form_panel,
                                 placeholder_text=placeholder, **input_style())
        entry.pack(fill="x", padx=20)
        self._entries[key] = entry

    def _clear_hint(self, widget, hint: str):
        """Clear textbox hint text on focus."""
        if widget.get("1.0", "end").strip() == hint:
            widget.delete("1.0", "end")
            widget.configure(text_color=COLORS["text_primary"])

    def _restore_hint(self, widget, hint: str):
        """Restore textbox hint text if left empty."""
        if not widget.get("1.0", "end").strip():
            widget.insert("1.0", hint)
            widget.configure(text_color=COLORS["text_muted"])

    # ── Save ──────────────────────────────────────────────────────────────
    def _save_client(self):
        from app.core.services.client_service import ClientService

        def _get(key):
            """Read value from entry widget or its StringVar."""
            if key + "_var" in self._entries:
                return self._entries[key + "_var"].get().strip()
            widget = self._entries.get(key)
            if widget:
                return widget.get().strip()
            return ""

        def _get_textbox(key):
            widget = self._entries.get(key + "_widget")
            if not widget:
                return ""
            val = widget.get("1.0", "end").strip()
            # Don't save hint text
            hints = {
                "physical_address": "e.g.  Plot 5, Kampala Road, Kampala",
                "notes": "Any additional information about the client...",
            }
            return "" if val == hints.get(key, "") else val

        data = {
            "full_name":                 _get("full_name"),
            "nin":                       _get("nin"),
            "phone_number":              _get("phone_number"),
            "alt_phone_number":          _get("alt_phone_number"),
            "email":                     _get("email"),
            "date_of_birth":             self.dob_picker.get(),
            "gender":                    _get("gender"),
            "district":                  _get("district"),
            "village":                   _get("village"),
            "physical_address":          _get_textbox("physical_address"),
            "occupation":                _get("occupation"),
            "employer_name":             _get("employer_name"),
            "monthly_income":            _get("monthly_income"),
            "next_of_kin_name":          _get("next_of_kin_name"),
            "next_of_kin_phone":         _get("next_of_kin_phone"),
            "next_of_kin_relationship":  _get("next_of_kin_relationship"),
            "notes":                     _get_textbox("notes"),
        }

        if not data["full_name"]:
            self.form_error.configure(text="⚠  Full name is required.")
            return
        if not data["phone_number"]:
            self.form_error.configure(text="⚠  Phone number is required.")
            return

        try:
            if self.selected_client:
                ClientService.update_client(self.selected_client.id, data)
            else:
                ClientService.create_client(data)
            self.form_error.configure(text="")
            self._load_clients()
            self._show_empty_form_state()
        except Exception as e:
            self.form_error.configure(text=f"⚠  {e}")

    # ── Delete ────────────────────────────────────────────────────────────
    def _delete_client(self):
        if self.selected_client:
            from app.core.services.client_service import ClientService
            ClientService.delete_client(self.selected_client.id)
            self.selected_client = None
            self._load_clients()
            self._show_empty_form_state()

    # ── Load table ────────────────────────────────────────────────────────
    def _load_clients(self, *args):
        from app.core.services.client_service import ClientService
        search  = self.search_var.get().strip() if hasattr(self, "search_var") else None
        clients = ClientService.get_all_clients(search=search or None)
        rows = [{
            "id":           c.id,
            "full_name":    c.full_name,
            "nin":          c.nin or "—",
            "phone_number": c.phone_number,
            "occupation":   c.occupation or "—",
        } for c in clients]
        if hasattr(self, "table"):
            self.table.update_rows(rows)