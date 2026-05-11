"""
app/ui/screens/agent_screen.py
──────────────────────────────────────────────────────────────
AI Agent screen — redesigned.

Changes from original:
  1. Assess Loan — search by loan number, NIN, or client name
     with a live popup showing matching clients to select from
  2. AI Output box — fills the full right column height
  3. Payment Reminders — moved to bottom, full detail cards
     showing: client name, loan number, due date, days overdue,
     outstanding balance, phone number, and WhatsApp message
  4. New card: Portfolio Health Summary — quick stats
  5. New card: Loan Maturity Forecast — loans expiring soon
"""

import threading
import customtkinter as ctk
from app.ui.styles.theme import COLORS, FONTS, primary_button_style, input_style
from app.ui.components.sidebar import Sidebar


class AgentScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master       = master
        self.current_user = master.current_user
        self._search_popup = None   # active client search popup window
        self._build()
        self._load_model_status()
        self._load_reminders()

    def refresh(self):
        threading.Thread(target=self._load_reminders, daemon=True).start()
        self._load_model_status()

    def _navigate(self, screen):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    # ── Layout ─────────────────────────────────────────────────────────────────

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        Sidebar(self, "agent", self._navigate, self.current_user).grid(
            row=0, column=0, sticky="nsew")

        main = ctk.CTkFrame(self, fg_color=COLORS["bg_primary"])
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)   # left actions
        main.columnconfigure(1, weight=2)   # right output — wider
        main.rowconfigure(1, weight=1)

        self._build_header(main)
        self._build_left(main)
        self._build_right(main)

    # ── Header ─────────────────────────────────────────────────────────────────

    def _build_header(self, parent):
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew",
                 padx=24, pady=(20, 8))
        hdr.columnconfigure(1, weight=1)

        ctk.CTkLabel(
            hdr, text="AI Agent",
            font=FONTS["title"],
            text_color=COLORS["accent_green_dark"],
        ).grid(row=0, column=0, sticky="w")

        self.model_status_label = ctk.CTkLabel(
            hdr, text="Checking model...",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
        )
        self.model_status_label.grid(row=1, column=0, sticky="w")

        ctk.CTkButton(
            hdr, text="Retrain Local Model",
            width=160, height=34,
            fg_color=COLORS["accent_gold"],
            hover_color=COLORS["accent_gold_dark"],
            text_color=COLORS["text_on_gold"],
            font=FONTS["button"], corner_radius=8,
            command=self._retrain_model,
        ).grid(row=0, column=2, sticky="e")

    # ── Left panel ─────────────────────────────────────────────────────────────

    def _build_left(self, parent):
        left = ctk.CTkScrollableFrame(
            parent, fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
        )
        left.grid(row=1, column=0, sticky="nsew",
                  padx=(24, 8), pady=(0, 24))
        left.columnconfigure(0, weight=1)

        # ── 1. Assess Single Loan ─────────────────────────────────────────
        self._build_assess_card(left, row=0)

        # ── 2. Scan Portfolio ─────────────────────────────────────────────
        self._simple_card(
            left, row=1,
            title="Scan Full Portfolio",
            desc="Analyse all active loans and get a prioritised action report.",
            btn_text="Scan Portfolio",
            btn_cmd=self._scan_portfolio,
        )

        # ── 3. Overdue Alerts ─────────────────────────────────────────────
        self._simple_card(
            left, row=2,
            title="Overdue Alerts & Collections",
            desc="Generate a collections action plan for all overdue loans.",
            btn_text="Check Overdue",
            btn_cmd=self._check_overdue,
        )

        # ── 4. Credit Score ───────────────────────────────────────────────
        self._build_credit_score_card(left, row=3)

        # ── 5. Portfolio Health Summary (NEW) ─────────────────────────────
        self._simple_card(
            left, row=4,
            title="Portfolio Health Summary",
            desc=(
                "Quick breakdown: active vs overdue vs completed loans, "
                "total disbursed, total collected, and default rate."
            ),
            btn_text="Get Health Summary",
            btn_cmd=self._portfolio_health,
        )

        # ── 6. Loan Maturity Forecast (NEW) ───────────────────────────────
        self._simple_card(
            left, row=5,
            title="Loan Maturity Forecast",
            desc=(
                "List loans due to mature in the next 30 / 60 / 90 days "
                "so the team can plan collection follow-ups in advance."
            ),
            btn_text="View Maturity Forecast",
            btn_cmd=self._maturity_forecast,
        )

    # ── Assess loan card (with client search popup) ────────────────────────────

    def _build_assess_card(self, parent, row):
        card = ctk.CTkFrame(
            parent, fg_color=COLORS["bg_card"],
            corner_radius=10, border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(row=row, column=0, sticky="ew", pady=8)
        card.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card, text="Assess Single Loan",
            font=FONTS["subheading"],
            text_color=COLORS["accent_green_dark"],
            anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 2))

        ctk.CTkLabel(
            card,
            text=(
                "Search by loan number, client name, or NIN.\n"
                "Type a name to see matching clients."
            ),
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="w", wraplength=300, justify="left",
        ).pack(fill="x", padx=16, pady=(0, 8))

        # Loan number entry
        ctk.CTkLabel(
            card, text="Loan Number",
            font=FONTS["body_small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 2))

        self.loan_number_entry = ctk.CTkEntry(
            card, placeholder_text="e.g. BG-2025-12345",
            **input_style(),
        )
        self.loan_number_entry.pack(fill="x", padx=16, pady=(0, 8))

        # Client name / NIN search with popup
        ctk.CTkLabel(
            card, text="Search by Client Name or NIN",
            font=FONTS["body_small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 2))

        search_frame = ctk.CTkFrame(card, fg_color="transparent")
        search_frame.pack(fill="x", padx=16, pady=(0, 4))
        search_frame.columnconfigure(0, weight=1)

        self.client_search_var = ctk.StringVar()
        self.client_search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self.client_search_var,
            placeholder_text="Type name or NIN to search...",
            **input_style(),
        )
        self.client_search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.client_search_entry.bind(
            "<KeyRelease>", self._on_client_search_key)
        self.client_search_entry.bind(
            "<FocusOut>", lambda e: self.after(200, self._close_search_popup))

        ctk.CTkButton(
            search_frame, text="Search",
            width=72, height=36,
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["accent_green"],
            text_color=COLORS["text_primary"],
            font=FONTS["body_small"], corner_radius=8,
            command=self._trigger_client_search,
        ).grid(row=0, column=1)

        # Selected client indicator
        self.selected_client_label = ctk.CTkLabel(
            card, text="",
            font=FONTS["caption"],
            text_color=COLORS["accent_green_dark"],
            anchor="w",
        )
        self.selected_client_label.pack(fill="x", padx=16, pady=(0, 4))

        self._selected_loan_id = None

        ctk.CTkButton(
            card, text="Assess Loan",
            height=36,
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["accent_green_dark"],
            text_color="#FFFFFF",
            font=FONTS["button"], corner_radius=8,
            command=self._assess_loan,
        ).pack(fill="x", padx=16, pady=(4, 16))

    # ── Credit score card with popup ───────────────────────────────────────────

    def _build_credit_score_card(self, parent, row):
        card = ctk.CTkFrame(
            parent, fg_color=COLORS["bg_card"],
            corner_radius=10, border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(row=row, column=0, sticky="ew", pady=8)
        card.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card, text="Client Credit Score",
            font=FONTS["subheading"],
            text_color=COLORS["accent_green_dark"],
            anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 2))

        ctk.CTkLabel(
            card,
            text="Calculate the internal credit score (0–100) for a client.",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="w", wraplength=300,
        ).pack(fill="x", padx=16, pady=(0, 8))

        self.credit_client_var = ctk.StringVar()
        self.credit_client_entry = ctk.CTkEntry(
            card,
            textvariable=self.credit_client_var,
            placeholder_text="Type client name or NIN...",
            **input_style(),
        )
        self.credit_client_entry.pack(fill="x", padx=16, pady=(0, 8))
        self.credit_client_entry.bind(
            "<KeyRelease>", self._on_credit_search_key)
        self.credit_client_entry.bind(
            "<FocusOut>",
            lambda e: self.after(200, self._close_credit_popup))

        self._credit_selected_client_id = None
        self.credit_selected_label = ctk.CTkLabel(
            card, text="",
            font=FONTS["caption"],
            text_color=COLORS["accent_green_dark"],
            anchor="w",
        )
        self.credit_selected_label.pack(fill="x", padx=16)

        ctk.CTkButton(
            card, text="Get Credit Score",
            height=36,
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["accent_green_dark"],
            text_color="#FFFFFF",
            font=FONTS["button"], corner_radius=8,
            command=self._get_credit_score,
        ).pack(fill="x", padx=16, pady=(8, 16))

    # ── Simple card (no entry) ─────────────────────────────────────────────────

    def _simple_card(self, parent, row, title, desc, btn_text, btn_cmd):
        card = ctk.CTkFrame(
            parent, fg_color=COLORS["bg_card"],
            corner_radius=10, border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(row=row, column=0, sticky="ew", pady=8)
        card.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card, text=title, font=FONTS["subheading"],
            text_color=COLORS["accent_green_dark"], anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 2))

        ctk.CTkLabel(
            card, text=desc, font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="w", wraplength=300, justify="left",
        ).pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkButton(
            card, text=btn_text, height=36,
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["accent_green_dark"],
            text_color="#FFFFFF", font=FONTS["button"], corner_radius=8,
            command=btn_cmd,
        ).pack(fill="x", padx=16, pady=(0, 16))

    # ── Right panel ────────────────────────────────────────────────────────────

    def _build_right(self, parent):
        right = ctk.CTkFrame(parent, fg_color="transparent")
        right.grid(row=1, column=1, sticky="nsew",
                   padx=(8, 24), pady=(0, 24))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=3)   # output box gets most space
        right.rowconfigure(3, weight=2)   # reminders get remaining space

        # ── Output label + copy button ─────────────────────────────────────
        out_hdr = ctk.CTkFrame(right, fg_color="transparent")
        out_hdr.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        out_hdr.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            out_hdr, text="AI Output",
            font=FONTS["subheading"],
            text_color=COLORS["accent_green_dark"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            out_hdr, text="Copy Output",
            width=100, height=28,
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_secondary"],
            font=FONTS["caption"], corner_radius=6,
            command=self._copy_output,
        ).grid(row=0, column=1, sticky="e")

        ctk.CTkButton(
            out_hdr, text="Clear",
            width=60, height=28,
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_secondary"],
            font=FONTS["caption"], corner_radius=6,
            command=self._clear_output,
        ).grid(row=0, column=2, sticky="e", padx=(6, 0))

        # ── Output box — full height ───────────────────────────────────────
        self.output_box = ctk.CTkTextbox(
            right,
            fg_color=COLORS["bg_card"],
            text_color=COLORS["text_primary"],
            font=("Courier", 11), wrap="word",
            corner_radius=10, border_width=1,
            border_color=COLORS["border"],
        )
        self.output_box.grid(row=1, column=0, sticky="nsew")
        self.output_box.insert(
            "end",
            "Click any action on the left to run an AI analysis.\n\n"
            "Results will appear here.\n\n"
            "Tips:\n"
            "  • Search by client name or NIN for loan assessment\n"
            "  • Select a client from the popup to auto-find their loan\n"
            "  • Use Copy Output to save results to clipboard",
        )
        self.output_box.configure(state="disabled")

        # ── Reminders section ──────────────────────────────────────────────
        rem_hdr = ctk.CTkFrame(right, fg_color="transparent")
        rem_hdr.grid(row=2, column=0, sticky="ew", pady=(16, 6))
        rem_hdr.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            rem_hdr, text="Payment Reminders",
            font=FONTS["subheading"],
            text_color=COLORS["accent_green_dark"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            rem_hdr, text="Refresh",
            width=80, height=28,
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_secondary"],
            font=FONTS["caption"], corner_radius=6,
            command=self._load_reminders,
        ).grid(row=0, column=1, sticky="e")

        self.reminders_frame = ctk.CTkScrollableFrame(
            right,
            fg_color=COLORS["bg_card"],
            corner_radius=10, border_width=1,
            border_color=COLORS["border"],
            scrollbar_button_color=COLORS["border"],
        )
        self.reminders_frame.grid(row=3, column=0, sticky="nsew")
        self.reminders_frame.columnconfigure(0, weight=1)

    # ══════════════════════════════════════════════════════════════════════════
    # Client search popup
    # ══════════════════════════════════════════════════════════════════════════

    def _on_client_search_key(self, event=None):
        term = self.client_search_var.get().strip()
        if len(term) >= 2:
            threading.Thread(
                target=self._fetch_and_show_popup,
                args=(term, self.client_search_entry, self._on_client_popup_select),
                daemon=True,
            ).start()
        else:
            self._close_search_popup()

    def _on_credit_search_key(self, event=None):
        term = self.credit_client_var.get().strip()
        if len(term) >= 2:
            threading.Thread(
                target=self._fetch_and_show_credit_popup,
                args=(term,),
                daemon=True,
            ).start()
        else:
            self._close_credit_popup()

    def _trigger_client_search(self):
        term = self.client_search_var.get().strip()
        if term:
            threading.Thread(
                target=self._fetch_and_show_popup,
                args=(term, self.client_search_entry, self._on_client_popup_select),
                daemon=True,
            ).start()

    def _fetch_and_show_popup(self, term, anchor_widget, on_select):
        try:
            from app.core.services.client_service import ClientService
            clients = ClientService.get_all_clients(search=term)
            self.after(0, lambda: self._show_client_popup(
                clients, anchor_widget, on_select, popup_attr="_search_popup"))
        except Exception:
            pass

    def _fetch_and_show_credit_popup(self, term):
        try:
            from app.core.services.client_service import ClientService
            clients = ClientService.get_all_clients(search=term)
            self.after(0, lambda: self._show_client_popup(
                clients, self.credit_client_entry,
                self._on_credit_popup_select, popup_attr="_credit_popup"))
        except Exception:
            pass

    def _show_client_popup(self, clients, anchor_widget, on_select,
                           popup_attr="_search_popup"):
        # Close any existing popup of this type
        existing = getattr(self, popup_attr, None)
        if existing:
            try:
                existing.destroy()
            except Exception:
                pass
        setattr(self, popup_attr, None)

        if not clients:
            return

        # Get anchor position
        anchor_widget.update_idletasks()
        x = anchor_widget.winfo_rootx()
        y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 2
        w = anchor_widget.winfo_width() + 80

        popup = ctk.CTkToplevel(self)
        popup.wm_overrideredirect(True)
        popup.geometry(f"{w}x{min(len(clients), 6) * 52 + 8}+{x}+{y}")
        popup.attributes("-topmost", True)
        popup.configure(fg_color=COLORS["bg_card"])
        setattr(self, popup_attr, popup)

        scroll = ctk.CTkScrollableFrame(
            popup,
            fg_color=COLORS["bg_card"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"],
            scrollbar_button_color=COLORS["border"],
        )
        scroll.pack(fill="both", expand=True, padx=2, pady=2)
        scroll.columnconfigure(0, weight=1)

        for i, client in enumerate(clients[:10]):
            row = ctk.CTkFrame(
                scroll,
                fg_color="transparent",
                corner_radius=6,
            )
            row.pack(fill="x", padx=4, pady=2)

            # Hover effect
            def _enter(e, r=row):
                r.configure(fg_color=COLORS["bg_input"])
            def _leave(e, r=row):
                r.configure(fg_color="transparent")
            row.bind("<Enter>", _enter)
            row.bind("<Leave>", _leave)

            # Name + NIN line
            name_line = ctk.CTkFrame(row, fg_color="transparent")
            name_line.pack(fill="x", padx=8, pady=(6, 0))

            ctk.CTkLabel(
                name_line,
                text=client.full_name,
                font=FONTS["body_small"],
                text_color=COLORS["text_primary"],
                anchor="w",
            ).pack(side="left")

            if client.nin:
                ctk.CTkLabel(
                    name_line,
                    text=f"  NIN: {client.nin}",
                    font=FONTS["caption"],
                    text_color=COLORS["text_muted"],
                    anchor="w",
                ).pack(side="left")

            # Phone line
            detail_line = ctk.CTkFrame(row, fg_color="transparent")
            detail_line.pack(fill="x", padx=8, pady=(0, 6))

            if client.phone_number:
                ctk.CTkLabel(
                    detail_line,
                    text=f"📞 {client.phone_number}",
                    font=FONTS["caption"],
                    text_color=COLORS["text_muted"],
                    anchor="w",
                ).pack(side="left")

            if client.occupation:
                ctk.CTkLabel(
                    detail_line,
                    text=f"  •  {client.occupation}",
                    font=FONTS["caption"],
                    text_color=COLORS["text_muted"],
                    anchor="w",
                ).pack(side="left")

            # Bind click to entire row and all children
            def _select(e, c=client, pa=popup_attr):
                on_select(c)
                try:
                    getattr(self, pa).destroy()
                except Exception:
                    pass
                setattr(self, pa, None)

            for widget in [row, name_line, detail_line] + \
                          row.winfo_children() + \
                          name_line.winfo_children() + \
                          detail_line.winfo_children():
                try:
                    widget.bind("<Button-1>", _select)
                except Exception:
                    pass

            # Divider between rows
            if i < len(clients) - 1:
                ctk.CTkFrame(
                    scroll, fg_color=COLORS["border"], height=1,
                ).pack(fill="x", padx=8)

    def _on_client_popup_select(self, client):
        """Called when a client is selected in the assess-loan popup."""
        self.client_search_var.set(client.full_name)
        self.selected_client_label.configure(
            text=f"✓  {client.full_name}  |  NIN: {client.nin or '—'}  |  {client.phone_number or '—'}"
        )

        # Auto-find their most recent active loan
        threading.Thread(
            target=self._auto_fill_loan_number,
            args=(client.id,),
            daemon=True,
        ).start()

    def _auto_fill_loan_number(self, client_id: int):
        try:
            from app.core.services.loan_service import LoanService
            loans = LoanService.get_loans_by_client(client_id)
            active = [l for l in loans if l.status.value == "active"]
            target = active[0] if active else (loans[0] if loans else None)
            if target:
                self.after(0, lambda: self.loan_number_entry.delete(0, "end"))
                self.after(0, lambda: self.loan_number_entry.insert(
                    0, target.loan_number))
                self.after(0, lambda: self.selected_client_label.configure(
                    text=(
                        f"✓  {target.loan_number}  loaded  "
                        f"({target.status.value.title()})  —  "
                        f"{target.loan_type.value}"
                    )
                ))
        except Exception:
            pass

    def _on_credit_popup_select(self, client):
        self.credit_client_var.set(client.full_name)
        self._credit_selected_client_id = client.id
        self.credit_selected_label.configure(
            text=f"✓  {client.full_name}  |  NIN: {client.nin or '—'}"
        )

    def _close_search_popup(self):
        if self._search_popup:
            try:
                self._search_popup.destroy()
            except Exception:
                pass
            self._search_popup = None

    def _close_credit_popup(self):
        if hasattr(self, "_credit_popup") and self._credit_popup:
            try:
                self._credit_popup.destroy()
            except Exception:
                pass
            self._credit_popup = None

    # ══════════════════════════════════════════════════════════════════════════
    # Actions
    # ══════════════════════════════════════════════════════════════════════════

    def _set_output(self, text: str):
        self.after(0, lambda: self._do_set_output(text))

    def _do_set_output(self, text: str):
        self.output_box.configure(state="normal")
        self.output_box.delete("1.0", "end")
        self.output_box.insert("end", text)
        self.output_box.configure(state="disabled")

    def _append_output(self, text: str):
        self.output_box.configure(state="normal")
        self.output_box.insert("end", text + "\n")
        self.output_box.configure(state="disabled")

    def _copy_output(self):
        text = self.output_box.get("1.0", "end").strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)

    def _clear_output(self):
        self._do_set_output("Output cleared. Click an action to run a new analysis.")

    # ── Assess loan ────────────────────────────────────────────────────────────

    def _assess_loan(self):
        loan_num = self.loan_number_entry.get().strip()
        if not loan_num:
            self._set_output(
                "Please enter a loan number, or search by client name / NIN "
                "and select a client from the dropdown to auto-fill it.")
            return
        self._set_output(f"Running risk assessment for {loan_num}...\n\nPlease wait.")

        def run():
            from app.core.services.loan_service import LoanService
            from app.core.agents.ai_core import AICore
            loans = LoanService.get_all_loans()
            loan  = next(
                (l for l in loans
                 if l.loan_number.upper() == loan_num.upper()), None)
            if not loan:
                self._set_output(f"Loan '{loan_num}' not found in the system.")
                return
            AICore.assess_single_loan(loan.id, callback=self._set_output)

        threading.Thread(target=run, daemon=True).start()

    # ── Scan portfolio ─────────────────────────────────────────────────────────

    def _scan_portfolio(self):
        self._set_output("Scanning portfolio... please wait.")
        threading.Thread(
            target=lambda: __import__(
                "app.core.agents.ai_core", fromlist=["AICore"]
            ).AICore.scan_portfolio(callback=self._set_output),
            daemon=True,
        ).start()

    # ── Overdue alerts ─────────────────────────────────────────────────────────

    def _check_overdue(self):
        self._set_output("Checking overdue loans... please wait.")
        threading.Thread(
            target=lambda: __import__(
                "app.core.agents.ai_core", fromlist=["AICore"]
            ).AICore.overdue_alerts(callback=self._set_output),
            daemon=True,
        ).start()

    # ── Credit score ───────────────────────────────────────────────────────────

    def _get_credit_score(self):
        # Use selected client id if available, otherwise search by text
        client_id = getattr(self, "_credit_selected_client_id", None)
        term      = self.credit_client_var.get().strip()

        if not term and not client_id:
            self._set_output("Please enter a client name or NIN first.")
            return

        self._set_output("Calculating credit score... please wait.")

        def run():
            from app.core.services.client_service import ClientService
            from app.core.agents.credit_scorer import CreditScorer

            if client_id:
                client = ClientService.get_client_by_id(client_id)
                if not client:
                    self._set_output("Selected client no longer found.")
                    return
                cid = client_id
                cname = client.full_name
            else:
                clients = ClientService.get_all_clients(search=term)
                if not clients:
                    self._set_output(f"No client found matching '{term}'.")
                    return
                cid   = clients[0].id
                cname = clients[0].full_name

            result = CreditScorer.score_client(cid)
            output = (
                f"CLIENT CREDIT SCORE\n"
                f"{'='*44}\n"
                f"Client:  {result.client_name}\n"
                f"Score:   {result.score}/100  [{result.band}]\n\n"
                f"{result.summary}\n\n"
                f"Factors:\n"
                + "\n".join(f"  • {f}" for f in result.factors)
            )
            self._set_output(output)

        threading.Thread(target=run, daemon=True).start()

    # ── Portfolio health summary (NEW) ─────────────────────────────────────────

    def _portfolio_health(self):
        self._set_output("Building portfolio health summary...")

        def run():
            try:
                from app.core.services.loan_service import LoanService
                from app.core.services.repayment_service import RepaymentService
                from datetime import date

                counts    = LoanService.count_by_status()
                portfolio = LoanService.total_portfolio_value()
                overdue   = LoanService.get_overdue_loans()
                interest  = LoanService.total_interest_earned()

                total_loans = sum(counts.values())
                active      = counts.get("active", 0)
                completed   = counts.get("completed", 0)
                defaulted   = counts.get("defaulted", 0)
                default_rate = (defaulted / total_loans * 100) if total_loans else 0

                lines = [
                    f"PORTFOLIO HEALTH SUMMARY — {date.today()}",
                    "=" * 44,
                    f"Total Loans:        {total_loans}",
                    f"Active:             {active}",
                    f"Completed:          {completed}",
                    f"Defaulted:          {defaulted}",
                    f"Overdue:            {len(overdue)}",
                    f"Pending:            {counts.get('pending', 0)}",
                    "",
                    f"Active Portfolio:   UGX {float(portfolio):,.0f}",
                    f"Interest Earned:    UGX {float(interest):,.0f}",
                    f"Default Rate:       {default_rate:.1f}%",
                    "",
                    "─" * 44,
                ]

                if overdue:
                    lines.append(f"TOP OVERDUE LOANS ({len(overdue)} total):")
                    for loan in sorted(
                        overdue,
                        key=lambda l: (date.today() - l.due_date).days
                        if l.due_date else 0,
                        reverse=True,
                    )[:5]:
                        days = (date.today() - loan.due_date).days \
                               if loan.due_date else 0
                        lines.append(
                            f"  {loan.loan_number}  "
                            f"UGX {float(loan.principal_amount):,.0f}  "
                            f"{days}d overdue"
                        )

                self._set_output("\n".join(lines))
            except Exception as e:
                self._set_output(f"Error building summary: {e}")

        threading.Thread(target=run, daemon=True).start()

    # ── Loan maturity forecast (NEW) ───────────────────────────────────────────

    def _maturity_forecast(self):
        self._set_output("Loading loan maturity forecast...")

        def run():
            try:
                from app.core.services.loan_service import LoanService
                from app.core.services.client_service import ClientService
                from datetime import date, timedelta

                all_loans = LoanService.get_all_loans(status="active")
                today     = date.today()

                buckets = {"30 days": [], "60 days": [], "90 days": []}
                for loan in all_loans:
                    if not loan.due_date:
                        continue
                    days_left = (loan.due_date - today).days
                    if days_left < 0:
                        continue
                    if days_left <= 30:
                        buckets["30 days"].append((days_left, loan))
                    elif days_left <= 60:
                        buckets["60 days"].append((days_left, loan))
                    elif days_left <= 90:
                        buckets["90 days"].append((days_left, loan))

                lines = [
                    f"LOAN MATURITY FORECAST — {today}",
                    "=" * 44,
                ]
                for bucket, loans in buckets.items():
                    lines.append(f"\nDue within {bucket} ({len(loans)} loans):")
                    if not loans:
                        lines.append("  None")
                        continue
                    for days_left, loan in sorted(loans, key=lambda x: x[0]):
                        client = ClientService.get_client_by_id(loan.client_id)
                        name   = client.full_name if client else "—"
                        phone  = client.phone_number if client else "—"
                        lines.append(
                            f"  {loan.loan_number}  {name[:18]:<18}  "
                            f"UGX {float(loan.principal_amount):,.0f}  "
                            f"due {loan.due_date}  ({days_left}d)  "
                            f"📞 {phone}"
                        )

                self._set_output("\n".join(lines))
            except Exception as e:
                self._set_output(f"Error loading forecast: {e}")

        threading.Thread(target=run, daemon=True).start()

    # ── Retrain model ──────────────────────────────────────────────────────────

    def _retrain_model(self):
        self._set_output("Starting model training...\n")

        def run():
            from app.core.agents.model_trainer import ModelTrainer

            def progress(msg):
                self.after(0, lambda m=msg: self._append_output(m))

            result = ModelTrainer.train(progress_callback=progress)
            self._set_output(
                f"{'✓ SUCCESS' if result['success'] else '✗ FAILED'}\n\n"
                f"{result['message']}"
            )
            self._load_model_status()

        threading.Thread(target=run, daemon=True).start()

    # ── Model status ───────────────────────────────────────────────────────────

    def _load_model_status(self):
        try:
            from app.core.agents.local_scorer import LocalScorer
            status = LocalScorer.model_status()
            self.after(0, lambda: self.model_status_label.configure(text=status))
        except Exception:
            pass

    # ── Reminders ──────────────────────────────────────────────────────────────

    def _load_reminders(self):
        def run():
            try:
                from app.core.agents.reminder_service import ReminderService
                from app.core.services.repayment_service import RepaymentService
                reminders = ReminderService.get_all_due_reminders()
                self.after(0, lambda: self._render_reminders(reminders))
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()

    def _render_reminders(self, reminders):
        for w in self.reminders_frame.winfo_children():
            w.destroy()

        if not reminders:
            ctk.CTkLabel(
                self.reminders_frame,
                text="No upcoming or overdue payments.",
                font=FONTS["body_small"],
                text_color=COLORS["text_muted"],
            ).pack(pady=16)
            return

        urgency_colors = {
            "overdue":  COLORS.get("danger",       "#E53E3E"),
            "urgent":   COLORS.get("warning",      "#D69E2E"),
            "standard": COLORS.get("accent_green", "#276749"),
            "gentle":   COLORS.get("text_muted",   "#718096"),
        }

        for r in reminders[:20]:
            color = urgency_colors.get(r.urgency, COLORS["text_secondary"])

            # ── Reminder card ────────────────────────────────────────────
            card = ctk.CTkFrame(
                self.reminders_frame,
                fg_color=COLORS["bg_input"],
                corner_radius=8,
            )
            card.pack(fill="x", padx=8, pady=4)
            card.columnconfigure(1, weight=1)

            # Left accent bar (color-coded by urgency)
            accent = ctk.CTkFrame(
                card, fg_color=color, width=4, corner_radius=0)
            accent.grid(row=0, column=0, rowspan=3, sticky="ns",
                        padx=(0, 10), pady=0)

            # Loan number + days overdue badge
            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.grid(row=0, column=1, sticky="ew",
                         padx=(0, 10), pady=(8, 2))
            top_row.columnconfigure(0, weight=1)

            ctk.CTkLabel(
                top_row,
                text=r.loan_number,
                font=FONTS.get("badge", FONTS["subheading"]),
                text_color=color,
                anchor="w",
            ).grid(row=0, column=0, sticky="w")

            days_text = (
                f"{abs(r.days_until)}d overdue"
                if r.days_until < 0
                else f"due in {r.days_until}d"
            )
            ctk.CTkLabel(
                top_row,
                text=days_text,
                font=FONTS["caption"],
                text_color=color,
                fg_color=COLORS["bg_card"],
                corner_radius=6,
                padx=8, pady=2,
            ).grid(row=0, column=1, sticky="e")

            # Client name
            ctk.CTkLabel(
                card,
                text=r.client_name,
                font=FONTS["body_small"],
                text_color=COLORS["text_primary"],
                anchor="w",
            ).grid(row=1, column=1, sticky="w", padx=(0, 10))

            # Detail row: due date + phone + amount
            detail_parts = []
            if hasattr(r, "due_date") and r.due_date:
                detail_parts.append(f"Due: {r.due_date}")
            if hasattr(r, "phone") and r.phone:
                detail_parts.append(f"📞 {r.phone}")
            if hasattr(r, "outstanding_balance") and r.outstanding_balance:
                detail_parts.append(
                    f"Balance: UGX {float(r.outstanding_balance):,.0f}")

            if detail_parts:
                ctk.CTkLabel(
                    card,
                    text="  ·  ".join(detail_parts),
                    font=FONTS["caption"],
                    text_color=COLORS["text_muted"],
                    anchor="w",
                    wraplength=420,
                ).grid(row=2, column=1, sticky="w",
                       padx=(0, 10), pady=(0, 4))

            # Action buttons row
            btn_row = ctk.CTkFrame(card, fg_color="transparent")
            btn_row.grid(row=3, column=1, sticky="ew",
                         padx=(0, 10), pady=(2, 8))

            ctk.CTkButton(
                btn_row, text="Copy WhatsApp Message",
                height=26,
                fg_color=COLORS["bg_card"],
                hover_color=COLORS["border"],
                text_color=COLORS["accent_green_dark"],
                font=FONTS["caption"], corner_radius=6,
                border_width=1, border_color=COLORS["border"],
                command=lambda msg=r.message: self._copy_reminder(msg),
            ).pack(side="left", padx=(0, 6))

            ctk.CTkButton(
                btn_row, text="Assess Loan",
                height=26,
                fg_color=COLORS["bg_card"],
                hover_color=COLORS["border"],
                text_color=COLORS["text_secondary"],
                font=FONTS["caption"], corner_radius=6,
                border_width=1, border_color=COLORS["border"],
                command=lambda ln=r.loan_number: self._quick_assess(ln),
            ).pack(side="left")

    def _copy_reminder(self, message: str):
        self.clipboard_clear()
        self.clipboard_append(message)
        self._set_output(
            "WhatsApp message copied to clipboard!\n\n"
            "─" * 44 + "\n"
            + message
        )

    def _quick_assess(self, loan_number: str):
        """Quickly load a loan number from reminder into the assess entry."""
        self.loan_number_entry.delete(0, "end")
        self.loan_number_entry.insert(0, loan_number)
        self._assess_loan()