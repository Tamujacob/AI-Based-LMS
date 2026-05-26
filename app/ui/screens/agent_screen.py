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

v2 layout changes:
  - Right column is ONE CTkScrollableFrame — single scrollbar
  - Output box is tall (fixed height) so it dominates the view
  - Reminder rows are compact single-line strips
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
        self._search_popup = None
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

        self._build_assess_card(left, row=0)
        self._simple_card(
            left, row=1,
            title="Scan Full Portfolio",
            desc="Analyse all active loans and get a prioritised action report.",
            btn_text="Scan Portfolio",
            btn_cmd=self._scan_portfolio,
        )
        self._simple_card(
            left, row=2,
            title="Overdue Alerts & Collections",
            desc="Generate a collections action plan for all overdue loans.",
            btn_text="Check Overdue",
            btn_cmd=self._check_overdue,
        )
        self._build_credit_score_card(left, row=3)
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

    # ── Assess loan card ───────────────────────────────────────────────────────

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

    # ── Credit score card ──────────────────────────────────────────────────────

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

    # ── Simple card ────────────────────────────────────────────────────────────

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

    # ── Right panel — single scrollable column ─────────────────────────────────

    def _build_right(self, parent):
        """
        Single CTkScrollableFrame for the entire right column.
        Contains: output header + output box (tall) + reminders header + reminder rows.
        One scrollbar, no nested scroll areas.
        """
        self._right_scroll = ctk.CTkScrollableFrame(
            parent,
            fg_color="transparent",
            scrollbar_button_color=COLORS["accent_green"],
            scrollbar_button_hover_color=COLORS["accent_green_dark"],
        )
        self._right_scroll.grid(row=1, column=1, sticky="nsew",
                                padx=(8, 24), pady=(0, 24))
        self._right_scroll.columnconfigure(0, weight=1)

        # ── Output header ──────────────────────────────────────────────────
        out_hdr = ctk.CTkFrame(self._right_scroll, fg_color="transparent")
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

        # ── Output box — fixed tall height ─────────────────────────────────
        # height=340 gives ~17 lines of output visible without scrolling
        self.output_box = ctk.CTkTextbox(
            self._right_scroll,
            fg_color=COLORS["bg_card"],
            text_color=COLORS["text_primary"],
            font=("Courier", 11), wrap="word",
            corner_radius=10, border_width=1,
            border_color=COLORS["border"],
            height=340,
        )
        self.output_box.grid(row=1, column=0, sticky="ew", pady=(0, 20))
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

        # ── Reminders header ───────────────────────────────────────────────
        rem_hdr = ctk.CTkFrame(self._right_scroll, fg_color="transparent")
        rem_hdr.grid(row=2, column=0, sticky="ew", pady=(0, 6))
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

        # ── Reminders container — CTk horizontal scroll ────────────────────
        # CTkScrollableFrame with orientation="horizontal" gives a styled
        # CTk scrollbar and renders all CTk child widgets correctly.
        # Vertical scrolling is handled by the outer _right_scroll.
        rem_border = ctk.CTkFrame(
            self._right_scroll,
            fg_color=COLORS["bg_card"],
            corner_radius=10, border_width=1,
            border_color=COLORS["border"],
        )
        rem_border.grid(row=3, column=0, sticky="ew")
        rem_border.columnconfigure(0, weight=1)

        self.reminders_frame = ctk.CTkScrollableFrame(
            rem_border,
            fg_color=COLORS["bg_card"],
            corner_radius=0,
            orientation="horizontal",
            scrollbar_button_color=COLORS["accent_green"],
            scrollbar_button_hover_color=COLORS["accent_green_dark"],
        )
        self.reminders_frame.pack(fill="both", expand=True)

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
        existing = getattr(self, popup_attr, None)
        if existing:
            try:
                existing.destroy()
            except Exception:
                pass
        setattr(self, popup_attr, None)

        if not clients:
            return

        anchor_widget.update_idletasks()
        x = anchor_widget.winfo_rootx()
        y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 2
        w = anchor_widget.winfo_width() + 80

        import tkinter as tk
        popup = tk.Toplevel(self)
        popup.wm_overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg=COLORS["border"])
        setattr(self, popup_attr, popup)

        border = tk.Frame(popup, bg=COLORS["border"])
        border.pack(fill="both", expand=True, padx=1, pady=1)

        shown = clients[:8]
        for i, client in enumerate(shown):
            bg = COLORS["bg_card"] if i % 2 == 0 else COLORS["bg_input"]

            row = tk.Frame(border, bg=bg, cursor="hand2")
            row.pack(fill="x")

            left = tk.Frame(row, bg=bg)
            left.pack(side="left", fill="both", expand=True, padx=(10, 4), pady=6)

            tk.Label(left, text=client.full_name,
                     bg=bg, fg=COLORS["text_primary"],
                     font=("Helvetica", 10, "bold"), anchor="w").pack(fill="x")

            details = []
            if client.nin:
                details.append(f"NIN: {client.nin}")
            if client.phone_number:
                details.append(f"Tel: {client.phone_number}")
            if client.occupation:
                details.append(client.occupation)
            tk.Label(left,
                     text="   ".join(details) if details else "—",
                     bg=bg, fg=COLORS["text_muted"],
                     font=("Helvetica", 8), anchor="w").pack(fill="x")

            tk.Button(row, text="Select →",
                      bg=COLORS["accent_green"], fg="#FFFFFF",
                      relief="flat", bd=0,
                      font=("Helvetica", 9, "bold"),
                      padx=10, pady=4, cursor="hand2",
                      command=lambda c=client, pa=popup_attr: (
                          on_select(c),
                          setattr(self, pa, None),
                          popup.destroy(),
                      )).pack(side="right", padx=8, pady=6)

            if i < len(shown) - 1:
                tk.Frame(border, bg=COLORS["border"], height=1).pack(fill="x")

            for widget in [row, left] + list(left.winfo_children()):
                widget.bind("<Button-1>",
                            lambda e, c=client, pa=popup_attr: (
                                on_select(c),
                                setattr(self, pa, None),
                                popup.destroy(),
                            ))
                widget.bind("<Enter>",
                            lambda e, r=row: r.configure(bg="#C8EAC8"))
                widget.bind("<Leave>",
                            lambda e, r=row, b=bg: r.configure(bg=b))

        popup.update_idletasks()
        popup.geometry(f"{w}x{popup.winfo_reqheight()}+{x}+{y}")

    def _on_client_popup_select(self, client):
        self.client_search_var.set(client.full_name)
        self.selected_client_label.configure(
            text=f"✓  {client.full_name}  |  NIN: {client.nin or '—'}  |  {client.phone_number or '—'}"
        )
        threading.Thread(
            target=self._auto_fill_loan_number,
            args=(client.id,),
            daemon=True,
        ).start()

    def _auto_fill_loan_number(self, client_id: int):
        try:
            from app.core.services.loan_service import LoanService
            loans  = LoanService.get_loans_by_client(client_id)
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
                cid   = client_id
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

    # ── Portfolio health ───────────────────────────────────────────────────────

    def _portfolio_health(self):
        self._set_output("Building portfolio health summary...")

        def run():
            try:
                from app.core.services.loan_service import LoanService
                from datetime import date

                counts    = LoanService.count_by_status()
                portfolio = LoanService.total_portfolio_value()
                overdue   = LoanService.get_overdue_loans()
                interest  = LoanService.total_interest_earned()

                total_loans  = sum(counts.values())
                active       = counts.get("active", 0)
                completed    = counts.get("completed", 0)
                defaulted    = counts.get("defaulted", 0)
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

    # ── Maturity forecast ──────────────────────────────────────────────────────

    def _maturity_forecast(self):
        self._set_output("Loading loan maturity forecast...")

        def run():
            try:
                from app.core.services.loan_service import LoanService
                from app.core.services.client_service import ClientService
                from datetime import date

                all_loans = LoanService.get_all_loans(status="active")
                today     = date.today()
                buckets   = {"30 days": [], "60 days": [], "90 days": []}

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

                lines = [f"LOAN MATURITY FORECAST — {today}", "=" * 44]
                for bucket, loans in buckets.items():
                    lines.append(f"\nDue within {bucket} ({len(loans)} loans):")
                    if not loans:
                        lines.append("  None")
                        continue
                    for days_left, loan in sorted(loans, key=lambda x: x[0]):
                        client = ClientService.get_client_by_id(loan.client_id)
                        name   = client.full_name    if client else "—"
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
            ).pack(pady=12, padx=16)
            return

        urgency_colors = {
            "overdue":  COLORS.get("danger",       "#E53E3E"),
            "urgent":   COLORS.get("warning",      "#D69E2E"),
            "standard": COLORS.get("accent_green", "#276749"),
            "gentle":   COLORS.get("text_muted",   "#718096"),
        }

        # One wide inner frame — the horizontal scrollable frame scrolls this
        # left/right. All rows fill="x" inside this fixed-width container.
        # Total width = sum of all column widths + buttons
        TOTAL_W = 10 + 110 + 140 + 90 + 90 + 120 + 110 + 64 + 58 + 30
        inner = ctk.CTkFrame(
            self.reminders_frame,
            fg_color=COLORS["bg_card"],
            corner_radius=0,
            width=TOTAL_W,
        )
        inner.pack(side="left", fill="y")
        inner.pack_propagate(False)
        inner.configure(width=TOTAL_W)

        # ── Column header ──────────────────────────────────────────────────
        hdr = ctk.CTkFrame(
            inner,
            fg_color=COLORS["accent_green"],
            corner_radius=0, height=28,
        )
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        for col_text, width in [
            ("Loan No.",  110),
            ("Client",    140),
            ("Due Date",   90),
            ("Status",     90),
            ("Balance",   120),
            ("Phone",     110),
            ("Actions",   122),
        ]:
            ctk.CTkLabel(
                hdr, text=col_text,
                font=FONTS["badge"],
                text_color="#FFFFFF",
                width=width, anchor="w",
            ).pack(side="left",
                   padx=(10 if col_text == "Loan No." else 4, 0))

        # ── One compact row per reminder ───────────────────────────────────
        for i, r in enumerate(reminders[:30]):
            color = urgency_colors.get(r.urgency, COLORS["text_secondary"])
            bg    = COLORS["bg_card"] if i % 2 == 0 else COLORS["bg_input"]

            row = ctk.CTkFrame(
                inner,
                fg_color=bg,
                corner_radius=0,
                height=36,
            )
            row.pack(fill="x")
            row.pack_propagate(False)

            # Left accent bar
            ctk.CTkFrame(
                row, fg_color=color, width=4, corner_radius=0,
            ).pack(side="left", fill="y")

            # Loan number
            ctk.CTkLabel(
                row, text=r.loan_number,
                font=FONTS["caption"], text_color=color,
                width=110, anchor="w",
            ).pack(side="left", padx=(6, 0))

            # Client name
            name = (r.client_name[:17] + "…") \
                if len(r.client_name) > 18 else r.client_name
            ctk.CTkLabel(
                row, text=name,
                font=FONTS["caption"], text_color=COLORS["text_primary"],
                width=140, anchor="w",
            ).pack(side="left", padx=(4, 0))

            # Due date
            due_str = str(r.due_date) \
                if hasattr(r, "due_date") and r.due_date else "—"
            ctk.CTkLabel(
                row, text=due_str,
                font=FONTS["caption"], text_color=COLORS["text_muted"],
                width=90, anchor="w",
            ).pack(side="left", padx=(4, 0))

            # Days overdue / until
            days_text = (
                f"{abs(r.days_until)}d overdue"
                if r.days_until < 0
                else f"in {r.days_until}d"
            )
            ctk.CTkLabel(
                row, text=days_text,
                font=FONTS["caption"], text_color=color,
                width=90, anchor="w",
            ).pack(side="left", padx=(4, 0))

            # Balance
            bal_str = (
                f"UGX {float(r.outstanding_balance):,.0f}"
                if hasattr(r, "outstanding_balance") and r.outstanding_balance
                else "—"
            )
            ctk.CTkLabel(
                row, text=bal_str,
                font=FONTS["caption"], text_color=COLORS["text_muted"],
                width=120, anchor="w",
            ).pack(side="left", padx=(4, 0))

            # Phone
            phone_str = r.phone if hasattr(r, "phone") and r.phone else "—"
            ctk.CTkLabel(
                row, text=phone_str,
                font=FONTS["caption"], text_color=COLORS["text_muted"],
                width=110, anchor="w",
            ).pack(side="left", padx=(4, 0))

            # Buttons
            ctk.CTkButton(
                row, text="📋 Copy",
                width=64, height=26,
                fg_color=COLORS["bg_card"],
                hover_color=COLORS["accent_green"],
                text_color=COLORS["text_secondary"],
                font=FONTS["caption"], corner_radius=4,
                border_width=1, border_color=COLORS["border"],
                command=lambda msg=r.message: self._copy_reminder(msg),
            ).pack(side="left", padx=(4, 0), pady=5)

            ctk.CTkButton(
                row, text="Assess",
                width=58, height=26,
                fg_color=COLORS["bg_card"],
                hover_color=COLORS["accent_green"],
                text_color=COLORS["text_secondary"],
                font=FONTS["caption"], corner_radius=4,
                border_width=1, border_color=COLORS["border"],
                command=lambda ln=r.loan_number: self._quick_assess(ln),
            ).pack(side="left", padx=(4, 6), pady=5)

    def _copy_reminder(self, message: str):
        self.clipboard_clear()
        self.clipboard_append(message)
        self._set_output(
            "WhatsApp message copied to clipboard!\n\n"
            "─" * 44 + "\n"
            + message
        )

    def _quick_assess(self, loan_number: str):
        """
        Full overdue analysis for a loan from the reminders panel.
        Shows repayment history, money disbursed vs collected,
        outstanding balance, interest at risk, recovery recommendations,
        and a risk re-rating based on actual payment behaviour.
        """
        self.loan_number_entry.delete(0, "end")
        self.loan_number_entry.insert(0, loan_number)
        self._set_output(
            f"Running overdue analysis for {loan_number}...\n\nPlease wait.")

        def run():
            try:
                from app.core.services.loan_service import LoanService
                from app.core.services.client_service import ClientService
                from app.core.services.repayment_service import RepaymentService
                from app.core.agents.local_scorer import LocalScorer
                from datetime import date

                # ── Load data ──────────────────────────────────────────────
                loans = LoanService.get_all_loans()
                loan  = next(
                    (l for l in loans
                     if l.loan_number.upper() == loan_number.upper()), None)
                if not loan:
                    self._set_output(f"Loan '{loan_number}' not found.")
                    return

                client     = ClientService.get_client_by_id(loan.client_id)
                repayments = RepaymentService.get_repayments_for_loan(loan.id)
                balance    = RepaymentService.get_outstanding_balance(loan.id)
                today      = date.today()

                name  = client.full_name    if client else "—"
                phone = client.phone_number if client else "—"
                occ   = client.occupation   if client else "—"

                principal       = float(loan.principal_amount or 0)
                total_interest  = float(loan.total_interest or 0)
                total_repayable = float(loan.total_repayable or 0)
                monthly_inst    = float(loan.monthly_installment or 0)
                duration        = int(loan.duration_months or 0)
                due_date        = loan.due_date
                disb_date       = loan.disbursement_date or loan.approval_date

                # ── Repayment analysis ─────────────────────────────────────
                total_paid   = sum(float(r.amount) for r in repayments)
                num_payments = len(repayments)
                days_overdue = (today - due_date).days if due_date else 0

                if disb_date and monthly_inst > 0:
                    months_elapsed = max(
                        1, round((today - disb_date).days / 30))
                    expected_paid = min(
                        months_elapsed * monthly_inst, total_repayable)
                    payment_gap = max(0, expected_paid - total_paid)
                else:
                    months_elapsed = duration
                    expected_paid  = total_repayable
                    payment_gap    = max(0, total_repayable - total_paid)

                consistency = (
                    total_paid / total_repayable
                    if total_repayable > 0 else 0.0)

                # Interest accruing on outstanding balance
                months_overdue   = max(1, days_overdue // 30)
                interest_at_risk = float(balance) * 0.10 * months_overdue

                # ── Risk re-rating based on actual behaviour ───────────────
                monthly_income = 0.0
                if client and client.monthly_income:
                    try:
                        monthly_income = float(
                            str(client.monthly_income).replace(",", ""))
                    except Exception:
                        pass

                score = LocalScorer.score(
                    principal           = principal,
                    duration_months     = duration,
                    loan_type           = loan.loan_type.value
                                         if loan.loan_type else "Business Loan",
                    occupation          = occ,
                    monthly_income      = monthly_income,
                    # Only flag as default if genuinely unpaid AND overdue
                    previous_defaults   = 1 if (days_overdue > 90
                                                and float(balance) > 0) else 0,
                    payment_consistency = consistency,
                )

                # ── Recovery recommendation ────────────────────────────────
                if float(balance) <= 0:
                    recovery = (
                        "✅ FULLY RECOVERED — No action required.\n"
                        "  • Loan has been repaid in full.\n"
                        "  • Loan status should be marked as Completed.\n"
                        "  • Consider offering this client a follow-up loan\n"
                        "    given their strong repayment record."
                    )
                elif days_overdue <= 30:
                    recovery = (
                        "CONTACT IMMEDIATELY — phone call + WhatsApp.\n"
                        "  • Offer a 7-day grace period if client shows willingness.\n"
                        "  • Request part payment to demonstrate commitment."
                    )
                elif days_overdue <= 90:
                    recovery = (
                        "ESCALATE TO MANAGEMENT — schedule a physical visit.\n"
                        "  • Issue a formal demand letter.\n"
                        "  • Discuss restructuring: extend duration to reduce monthly load.\n"
                        "  • Engage guarantor or co-signatory if applicable."
                    )
                else:
                    recovery = (
                        "CRITICAL — CONSIDER DEFAULT PROCEEDINGS.\n"
                        "  • Engage legal team or debt collector.\n"
                        "  • Evaluate collateral recovery options.\n"
                        "  • Document all contact attempts for legal record.\n"
                        "  • Offer final settlement discount for lump-sum payment."
                    )

                # ── Repayment history lines ────────────────────────────────
                rep_lines = []
                if repayments:
                    for r in sorted(repayments,
                                    key=lambda x: x.payment_date or today):
                        rep_lines.append(
                            f"  {r.payment_date}   "
                            f"UGX {float(r.amount):>12,.0f}   "
                            f"{r.payment_method.value if r.payment_method else '—'}"
                        )
                else:
                    rep_lines.append("  No payments recorded.")

                # ── Build output ───────────────────────────────────────────
                risk_icon = {"LOW": "🟢", "MEDIUM": "🟡",
                             "HIGH": "🔴"}.get(score.rating, "⚪")

                lines = [
                    f"OVERDUE LOAN ANALYSIS — {loan_number}",
                    "=" * 52,
                    f"Client:           {name}",
                    f"Phone:            {phone}",
                    f"Occupation:       {occ}",
                    f"Loan Type:        {loan.loan_type.value if loan.loan_type else '—'}",
                    "",
                    "─" * 52,
                    "LOAN FINANCIALS",
                    "─" * 52,
                    f"Principal:        UGX {principal:>14,.0f}",
                    f"Total Interest:   UGX {total_interest:>14,.0f}",
                    f"Total Repayable:  UGX {total_repayable:>14,.0f}",
                    f"Monthly Install:  UGX {monthly_inst:>14,.0f}",
                    f"Duration:         {duration} months",
                    f"Due Date:         {due_date}",
                    f"Days Overdue:     {days_overdue} days",
                    "",
                    "─" * 52,
                    "REPAYMENT STATUS",
                    "─" * 52,
                    f"Total Paid:       UGX {total_paid:>14,.0f}  ({num_payments} payment(s))",
                    f"Expected by Now:  UGX {expected_paid:>14,.0f}",
                    f"Payment Gap:      UGX {payment_gap:>14,.0f}",
                    f"Outstanding Bal:  UGX {float(balance):>14,.0f}",
                    f"Recovery Rate:    {consistency:.0%} of total repayable",
                    f"Interest at Risk: UGX {interest_at_risk:>14,.0f}  "
                    f"({months_overdue} month(s) at 10%/mo)",
                    "",
                    "REPAYMENT HISTORY:",
                ] + rep_lines + [
                    "",
                    "─" * 52,
                    "RISK RE-ASSESSMENT (based on actual behaviour)",
                    "─" * 52,
                    f"{risk_icon} Risk Rating:   {score.rating}  "
                    f"({score.confidence}% confidence)",
                    f"Model:            {score.model_used}",
                    "",
                    "Reasoning:",
                ] + [f"  • {r}" for r in score.reasoning] + [
                    "",
                    "─" * 52,
                    "RECOVERY RECOMMENDATION",
                    "─" * 52,
                    recovery,
                    "=" * 52,
                ]

                self._set_output("\n".join(lines))

            except Exception as e:
                self._set_output(f"Error running overdue analysis: {e}")

        threading.Thread(target=run, daemon=True).start()