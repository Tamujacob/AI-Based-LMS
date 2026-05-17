"""
app/ui/screens/loans_screen.py
────────────────────────────────
Loans screen — redesigned form flow:

  1. Client search — live popup (type 2+ chars) showing name + NIN + phone.
     Selecting a client auto-fills monthly income from client record.

  2. Statement analysis — upload → analyse → 3 scenario cards appear.
     Clicking a scenario card auto-fills principal + duration.
     If no statement, client's stored monthly_income is used for ceiling.

  3. Submit — always triggers auto_score_loan() in background so every
     loan reaches the manager with a risk score attached.
     If statement was not analysed, a reminder banner is shown (not a blocker).
"""

import customtkinter as ctk
import tkinter as tk
import os
import shutil
import threading
from datetime import date
from decimal import Decimal, InvalidOperation
from PIL import Image

from app.ui.styles.theme import (
    COLORS, FONTS,
    primary_button_style, secondary_button_style,
    input_style, danger_button_style,
)
from app.ui.components.sidebar import Sidebar
from app.ui.components.data_table import DataTable
from app.ui.components.date_picker import DatePicker
from app.ui.components.statement_analysis_widget import StatementAnalysisWidget
from app.config.settings import LOAN_TYPES, COLLATERAL_UPLOAD_DIR

_GREEN_DARK = "#1A5C1E"
_GREEN      = "#34A038"
_GOLD       = "#D4A820"
_WHITE      = "#FFFFFF"
_TEXT       = "#1A2E1A"
_LIGHT      = "#F4F6F4"
_BORDER     = "#C8DFC8"
_MUTED      = "#7A9A7A"


def _clean_number(raw: str) -> str:
    return raw.strip().replace(",", "").replace(" ", "").replace("UGX", "")

def _to_float(raw: str) -> float:
    cleaned = _clean_number(raw)
    if not cleaned:
        raise ValueError("Field is empty.")
    try:
        return float(cleaned)
    except (ValueError, InvalidOperation):
        raise ValueError(f'"{raw}" is not a valid number.')

def _to_int(raw: str) -> int:
    return int(_to_float(raw))


# ══════════════════════════════════════════════════════════════════════════════
# Client picker dialog (kept for multiple-match fallback)
# ══════════════════════════════════════════════════════════════════════════════

class ClientPickerDialog(tk.Toplevel):
    def __init__(self, master, clients: list):
        super().__init__(master)
        self.result  = None
        self.clients = clients
        self.title("Select Client")
        self.resizable(False, False)
        self.configure(bg=_LIGHT)
        self.grab_set()
        height = min(120 + len(clients) * 54, 520)
        self.geometry(f"520x{height}")
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"520x{height}+{(sw-520)//2}+{(sh-height)//2}")
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=_GREEN_DARK, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="👥  Select a client",
                 bg=_GREEN_DARK, fg=_WHITE,
                 font=("Helvetica", 12, "bold")).pack(
            side="left", padx=16, fill="y")
        tk.Button(hdr, text="✕", bg=_GREEN_DARK, fg=_WHITE,
                  relief="flat", bd=0, padx=14, cursor="hand2",
                  font=("Helvetica", 13),
                  command=self._cancel).pack(side="right", fill="y")

        col_hdr = tk.Frame(self, bg=_GREEN, height=30)
        col_hdr.pack(fill="x", padx=12)
        col_hdr.pack_propagate(False)
        for text, w in [("Full Name", 22), ("NIN", 16), ("Phone", 14)]:
            tk.Label(col_hdr, text=text, bg=_GREEN, fg=_WHITE,
                     font=("Helvetica", 9, "bold"),
                     width=w, anchor="w").pack(
                side="left", padx=(12 if text == "Full Name" else 2, 0),
                fill="y")

        outer  = tk.Frame(self, bg=_BORDER, padx=1, pady=1)
        outer.pack(fill="both", expand=True, padx=12, pady=(4, 0))
        canvas = tk.Canvas(outer, bg=_WHITE, highlightthickness=0)
        sb     = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        frame  = tk.Frame(canvas, bg=_WHITE)
        win    = canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win, width=e.width))

        for i, client in enumerate(self.clients):
            bg  = _WHITE if i % 2 == 0 else "#F0F7F0"
            row = tk.Frame(frame, bg=bg, cursor="hand2")
            row.pack(fill="x")
            tk.Label(row, text=client.full_name, bg=bg, fg=_TEXT,
                     font=("Helvetica", 10, "bold"),
                     width=22, anchor="w").pack(
                side="left", padx=(12, 4), pady=10)
            tk.Label(row, text=client.nin or "—", bg=bg, fg=_MUTED,
                     font=("Helvetica", 9), width=16, anchor="w").pack(
                side="left", padx=2)
            tk.Label(row, text=client.phone_number or "—", bg=bg, fg=_MUTED,
                     font=("Helvetica", 9), width=14, anchor="w").pack(
                side="left", padx=2)
            tk.Button(row, text="Select →", bg=_GREEN, fg=_WHITE,
                      relief="flat", bd=0,
                      font=("Helvetica", 9, "bold"),
                      padx=12, pady=4, cursor="hand2",
                      command=lambda c=client: self._select(c)).pack(
                side="right", padx=12, pady=6)
            for w in (row,):
                w.bind("<Enter>",    lambda e, f=row: f.configure(bg="#D5EDD5"))
                w.bind("<Leave>",    lambda e, f=row, b=bg: f.configure(bg=b))
                w.bind("<Button-1>", lambda e, c=client: self._select(c))

        bottom = tk.Frame(self, bg=_LIGHT, pady=8)
        bottom.pack(fill="x", padx=12)
        tk.Button(bottom, text="✖  Cancel", bg=_LIGHT, fg=_MUTED,
                  relief="flat", bd=1, font=("Helvetica", 9),
                  padx=14, pady=5, cursor="hand2",
                  command=self._cancel).pack(side="right")

    def _select(self, client):
        self.result = client
        self.grab_release()
        self.destroy()

    def _cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
# File picker
# ══════════════════════════════════════════════════════════════════════════════

class FilePicker(tk.Toplevel):
    SUPPORTED_EXT = {
        ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    }

    def __init__(self, master):
        super().__init__(master)
        self.result          = []
        self._current_dir    = os.path.expanduser("~")
        self._selected_files = set()
        self._file_buttons   = {}
        self.title("Select Collateral Documents")
        self.resizable(True, True)
        self.geometry("640x480")
        self.configure(bg=_LIGHT)
        self.update_idletasks()
        self.grab_set()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"640x480+{(sw-640)//2}+{(sh-480)//2}")
        self._build()
        self._load_dir(self._current_dir)

    def _build(self):
        hdr = tk.Frame(self, bg=_GREEN_DARK, height=48)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="📁  Select Collateral Documents",
                 bg=_GREEN_DARK, fg=_WHITE,
                 font=("Helvetica", 12, "bold")).pack(
            side="left", padx=16, fill="y")
        tk.Button(hdr, text="✕", bg=_GREEN_DARK, fg=_WHITE,
                  relief="flat", bd=0, padx=12, cursor="hand2",
                  font=("Helvetica", 12), command=self._cancel).pack(
            side="right", fill="y")
        path_bar = tk.Frame(self, bg=_GREEN, height=36)
        path_bar.pack(fill="x")
        path_bar.pack_propagate(False)
        for label, cmd in [
            ("⬆  Up",        self._go_up),
            ("🏠  Home",      lambda: self._load_dir(os.path.expanduser("~"))),
            ("🖥  Desktop",   lambda: self._load_dir(
                os.path.join(os.path.expanduser("~"), "Desktop"))),
            ("📥  Downloads", lambda: self._load_dir(
                os.path.join(os.path.expanduser("~"), "Downloads"))),
        ]:
            tk.Button(path_bar, text=label, bg=_GREEN, fg=_WHITE,
                      relief="flat", bd=0, padx=12, cursor="hand2",
                      font=("Helvetica", 10, "bold"),
                      command=cmd).pack(side="left", fill="y")
        self.path_label = tk.Label(path_bar, text="", bg=_GREEN, fg=_GOLD,
                                   font=("Helvetica", 9), anchor="w")
        self.path_label.pack(side="left", fill="both", expand=True, padx=8)
        file_outer = tk.Frame(self, bg=_BORDER, padx=1, pady=1)
        file_outer.pack(fill="both", expand=True, padx=12, pady=8)
        canvas    = tk.Canvas(file_outer, bg=_WHITE, highlightthickness=0)
        scrollbar = tk.Scrollbar(file_outer, orient="vertical",
                                 command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.file_frame = tk.Frame(canvas, bg=_WHITE)
        self._canvas_window = canvas.create_window(
            (0, 0), window=self.file_frame, anchor="nw")
        self.file_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(
                        self._canvas_window, width=e.width))
        self._canvas = canvas
        bottom = tk.Frame(self, bg=_LIGHT, pady=8)
        bottom.pack(fill="x", padx=12)
        self.sel_label = tk.Label(bottom, text="No files selected",
                                  bg=_LIGHT, fg=_MUTED,
                                  font=("Helvetica", 9), anchor="w")
        self.sel_label.pack(side="left", fill="x", expand=True)
        tk.Button(bottom, text="✖  Cancel", bg=_LIGHT, fg=_TEXT,
                  relief="flat", bd=1, font=("Helvetica", 10),
                  padx=16, pady=6, cursor="hand2",
                  command=self._cancel).pack(side="right", padx=(4, 0))
        tk.Button(bottom, text="✔  Add Selected", bg=_GREEN, fg=_WHITE,
                  relief="flat", bd=0, font=("Helvetica", 10, "bold"),
                  padx=16, pady=6, cursor="hand2",
                  command=self._confirm).pack(side="right")

    def _load_dir(self, path: str):
        if not os.path.isdir(path):
            return
        self._current_dir = path
        self.path_label.configure(text=f"  {path}")
        self._file_buttons.clear()
        for w in self.file_frame.winfo_children():
            w.destroy()
        try:
            entries = sorted(os.scandir(path),
                             key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            tk.Label(self.file_frame, text="⚠  Permission denied",
                     bg=_WHITE, fg="#C0392B",
                     font=("Helvetica", 10)).pack(padx=16, pady=16)
            return
        for entry in entries:
            if entry.name.startswith("."):
                continue
            is_dir  = entry.is_dir()
            ext     = os.path.splitext(entry.name)[1].lower()
            is_file = not is_dir and ext in self.SUPPORTED_EXT
            if not is_dir and not is_file:
                continue
            icon      = "📁" if is_dir else self._file_icon(ext)
            row_frame = tk.Frame(self.file_frame, bg=_WHITE, cursor="hand2")
            row_frame.pack(fill="x", padx=4, pady=1)
            icon_lbl  = tk.Label(row_frame, text=icon, bg=_WHITE,
                                 font=("Segoe UI Emoji", 13),
                                 width=3, anchor="center")
            icon_lbl.pack(side="left", padx=(8, 0), pady=4)
            name_lbl  = tk.Label(row_frame, text=entry.name, bg=_WHITE,
                                 fg=_TEXT, font=("Helvetica", 10), anchor="w")
            name_lbl.pack(side="left", fill="x", expand=True, padx=8)
            if is_file:
                size_kb = entry.stat().st_size // 1024
                tk.Label(row_frame,
                         text=f"{size_kb} KB" if size_kb else "< 1 KB",
                         bg=_WHITE, fg=_MUTED,
                         font=("Helvetica", 9)).pack(side="right", padx=12)
                self._file_buttons[entry.path] = (row_frame, icon_lbl, name_lbl)
            if is_dir:
                for w in (row_frame, icon_lbl, name_lbl):
                    w.bind("<Double-Button-1>",
                           lambda e, p=entry.path: self._load_dir(p))
                    w.bind("<Button-1>",
                           lambda e, p=entry.path: self._load_dir(p))
            else:
                for w in (row_frame, icon_lbl, name_lbl):
                    w.bind("<Button-1>",
                           lambda e, p=entry.path: self._toggle_file(p))
        self._canvas.yview_moveto(0)

    def _file_icon(self, ext: str) -> str:
        return {
            ".pdf": "📄", ".jpg": "🖼", ".jpeg": "🖼", ".png": "🖼",
            ".bmp": "🖼", ".gif": "🖼", ".tiff": "🖼",
            ".doc": "📝", ".docx": "📝", ".xls": "📊", ".xlsx": "📊",
        }.get(ext, "📎")

    def _toggle_file(self, path: str):
        if path in self._selected_files:
            self._selected_files.discard(path)
            self._set_row_color(path, _WHITE)
        else:
            self._selected_files.add(path)
            self._set_row_color(path, "#E8F4E8")
        count = len(self._selected_files)
        self.sel_label.configure(
            text=f"{count} file{'s' if count != 1 else ''} selected"
            if count else "No files selected",
            fg=_GREEN if count else _MUTED)

    def _set_row_color(self, path: str, color: str):
        widgets = self._file_buttons.get(path)
        if widgets:
            for w in widgets:
                w.configure(bg=color)

    def _go_up(self):
        parent = os.path.dirname(self._current_dir)
        if parent != self._current_dir:
            self._load_dir(parent)

    def _confirm(self):
        self.result = list(self._selected_files)
        self.grab_release()
        self.destroy()

    def _cancel(self):
        self.result = []
        self.grab_release()
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
# Loans screen
# ══════════════════════════════════════════════════════════════════════════════

class LoansScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master            = master
        self.current_user      = master.current_user
        self.selected_loan     = None
        self._collateral_files = []
        self.found_client_id   = None
        self._found_client_obj = None    # full client object after selection
        self._statement_analysed = False  # track whether statement was analysed
        self._search_popup     = None    # live client search popup

        # Pagination
        self.current_page  = 1
        self.page_size     = 25
        self.total_records = 0
        self.total_pages   = 1

        self._build()
        self._load_loans()

    def _navigate(self, screen: str):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    def refresh(self):
        threading.Thread(target=self._load_loans, daemon=True).start()

    # ── Layout ─────────────────────────────────────────────────────────────────

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        Sidebar(self, "loans", self._navigate, self.current_user).grid(
            row=0, column=0, sticky="nsew")
        main = ctk.CTkFrame(self, fg_color=COLORS["bg_primary"])
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)
        self._build_list_panel(main)
        self._build_detail_panel(main)

    # ── Left: loan list ────────────────────────────────────────────────────────

    def _build_list_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        panel.grid(row=0, column=0, sticky="nsew", padx=(24, 8), pady=24)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(2, weight=1)

        title_row = ctk.CTkFrame(panel, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        title_row.columnconfigure(0, weight=1)
        ctk.CTkLabel(title_row, text="Loans", font=FONTS["title"],
                     text_color=COLORS["accent_green_dark"]).grid(
            row=0, column=0, sticky="w")
        ctk.CTkLabel(title_row,
                     text="Manage loan applications, approvals, and repayments.",
                     font=FONTS["body_small"],
                     text_color=COLORS["text_muted"]).grid(
            row=1, column=0, sticky="w")

        filter_row = ctk.CTkFrame(panel, fg_color="transparent")
        filter_row.grid(row=1, column=0, sticky="ew", pady=(12, 12))
        filter_row.columnconfigure(2, weight=1)

        self.status_filter = ctk.CTkOptionMenu(
            filter_row,
            values=["All", "pending", "approved", "active",
                    "completed", "defaulted", "rejected"],
            command=self._on_status_change,
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_green"],
            button_hover_color=COLORS["accent_green_dark"],
            text_color=COLORS["text_primary"],
            font=FONTS["body_small"], width=130,
        )
        self.status_filter.grid(row=0, column=0, padx=(0, 8))

        ctk.CTkButton(filter_row, text="🔍 Search loans",
                      command=self._perform_search,
                      fg_color=COLORS["bg_input"],
                      hover_color=COLORS["bg_hover"],
                      text_color=COLORS["text_primary"],
                      font=FONTS["body_small"], width=120).grid(
            row=0, column=1, padx=(0, 8))

        self.search_var = ctk.StringVar()
        self._last_search_value = ""
        self._search_timer = None
        self.search_var.trace_add("write", self._on_search_change)
        ctk.CTkEntry(filter_row, textvariable=self.search_var,
                     placeholder_text="🔍  Loan number, client name, NIN or phone...",
                     **input_style()).grid(
            row=0, column=2, sticky="ew", padx=(0, 8))

        ctk.CTkButton(filter_row, text="+ New Loan", width=120,
                      command=self._new_loan_form,
                      **primary_button_style()).grid(row=0, column=3)

        self.table = DataTable(
            panel,
            columns=[
                ("loan_number", "Loan No.",  115),
                ("client_name", "Client",    160),
                ("loan_type",   "Type",      120),
                ("principal",   "Principal", 115),
                ("status",      "Status",     90),
            ],
            on_select=self._on_loan_selected,
        )
        self.table.grid(row=2, column=0, sticky="nsew")

        pagination_frame = ctk.CTkFrame(panel, fg_color="transparent")
        pagination_frame.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        pagination_frame.columnconfigure(1, weight=1)

        self.prev_btn = ctk.CTkButton(
            pagination_frame, text="◀ Previous", width=100,
            command=self._prev_page,
            fg_color="#FFFFFF", hover_color=COLORS["bg_input"],
            text_color=COLORS["text_secondary"],
            border_width=1, border_color=COLORS["border"],
            font=FONTS["body_small"], state="disabled")
        self.prev_btn.grid(row=0, column=0, padx=(0, 4))

        self.page_label = ctk.CTkLabel(
            pagination_frame, text="Page 1 of 1 (0 records)",
            font=FONTS["body_small"], text_color=COLORS["text_muted"])
        self.page_label.grid(row=0, column=1)

        self.next_btn = ctk.CTkButton(
            pagination_frame, text="Next ▶", width=100,
            command=self._next_page,
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["accent_green_dark"],
            text_color="#FFFFFF",
            font=FONTS["body_small"], state="disabled")
        self.next_btn.grid(row=0, column=2, padx=(4, 0))

    # ── Right: detail / form panel ─────────────────────────────────────────────

    def _build_detail_panel(self, parent):
        self.detail_panel = ctk.CTkScrollableFrame(
            parent, fg_color=COLORS["bg_card"], corner_radius=12,
            border_width=1, border_color=COLORS["border"],
            scrollbar_button_color=COLORS["accent_green"],
            scrollbar_button_hover_color=COLORS["accent_green_dark"],
        )
        self.detail_panel.grid(row=0, column=1, sticky="nsew",
                               padx=(8, 24), pady=24)
        self.detail_panel.columnconfigure(0, weight=1)
        self._show_empty_state()

    def _show_empty_state(self):
        for w in self.detail_panel.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.detail_panel,
            text="Select a loan\nor click + New Loan",
            font=FONTS["body"], text_color=COLORS["text_muted"],
            justify="center").pack(expand=True, pady=80)

    # ── Loan detail ────────────────────────────────────────────────────────────

    def _on_loan_selected(self, row: dict):
        from app.core.services.loan_service import LoanService
        loan = LoanService.get_loan_by_id(row["id"])
        self.selected_loan = loan
        if loan:
            self._render_loan_detail(loan)

    def _render_loan_detail(self, loan):
        self.selected_loan = loan
        for w in self.detail_panel.winfo_children():
            w.destroy()

        ctk.CTkLabel(self.detail_panel, text=loan.loan_number,
                     font=FONTS["subtitle"],
                     text_color=COLORS["accent_green_dark"]).pack(
            anchor="w", padx=20, pady=(20, 4))

        status_colors = {
            "pending":   COLORS["warning"],
            "approved":  COLORS.get("info", COLORS["accent_green"]),
            "active":    COLORS["accent_green"],
            "completed": COLORS["text_muted"],
            "defaulted": COLORS["danger"],
            "rejected":  COLORS["danger"],
        }
        ctk.CTkLabel(self.detail_panel,
                     text=loan.status.value.upper(), font=FONTS["badge"],
                     text_color=status_colors.get(
                         loan.status.value, COLORS["text_secondary"])).pack(
            anchor="w", padx=20)
        self._divider()

        from app.core.services.client_service import ClientService
        from app.core.services.repayment_service import RepaymentService
        client  = ClientService.get_client_by_id(loan.client_id)
        balance = RepaymentService.get_outstanding_balance(loan.id)

        for label, value in [
            ("Client",             client.full_name if client else "—"),
            ("Phone",              client.phone_number if client else "—"),
            ("Loan Type",          loan.loan_type.value if loan.loan_type else "—"),
            ("Principal",          f"UGX {float(loan.principal_amount):,.0f}"),
            ("Interest (10%/mo)",  f"UGX {float(loan.total_interest):,.0f}"
                                   if loan.total_interest else "—"),
            ("Total Repayable",    f"UGX {float(loan.total_repayable):,.0f}"
                                   if loan.total_repayable else "—"),
            ("Monthly Instalment", f"UGX {float(loan.monthly_installment):,.0f}"
                                   if loan.monthly_installment else "—"),
            ("Duration",           f"{loan.duration_months} months"),
            ("Application Date",   str(loan.application_date)
                                   if loan.application_date else "—"),
            ("Approval Date",      str(loan.approval_date)
                                   if loan.approval_date else "—"),
            ("Due Date",           str(loan.due_date) if loan.due_date else "—"),
            ("Outstanding Bal.",   f"UGX {float(balance):,.0f}"),
            ("Purpose",            loan.purpose or "—"),
            ("Risk Score",         str(loan.risk_score)
                                   if loan.risk_score else "⏳ Auto-assessing..."),
        ]:
            row_f = ctk.CTkFrame(self.detail_panel, fg_color="transparent")
            row_f.pack(fill="x", padx=20, pady=2)
            ctk.CTkLabel(row_f, text=label, font=FONTS["body_small"],
                         text_color=COLORS["text_muted"],
                         width=140, anchor="w").pack(side="left")
            ctk.CTkLabel(row_f, text=value, font=FONTS["body_small"],
                         text_color=COLORS["text_primary"],
                         anchor="w", wraplength=180).pack(side="left")

        self._render_collateral(loan)
        self._render_repayments(loan)
        self._divider()

        btn_frame = ctk.CTkFrame(self.detail_panel, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(4, 8))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        btn_frame.columnconfigure(2, weight=1)

        if loan.status.value == "pending":
            ctk.CTkButton(btn_frame, text="✎  Edit",
                          fg_color=COLORS["accent_gold"],
                          hover_color=COLORS["accent_gold_dark"],
                          text_color=_WHITE, font=FONTS["button"],
                          corner_radius=8, height=38,
                          command=lambda: self._edit_loan_form(loan)).grid(
                row=0, column=0, padx=(0, 4), sticky="ew")
            ctk.CTkButton(btn_frame, text="✔  Approve",
                          fg_color=COLORS["accent_green"],
                          hover_color=COLORS["accent_green_dark"],
                          text_color=_WHITE, font=FONTS["button"],
                          corner_radius=8, height=38,
                          command=lambda: self._approve_loan(loan.id)).grid(
                row=0, column=1, padx=4, sticky="ew")
            ctk.CTkButton(btn_frame, text="✖  Reject",
                          command=lambda: self._reject_loan(loan.id),
                          **danger_button_style()).grid(
                row=0, column=2, padx=(4, 0), sticky="ew")
        elif loan.status.value == "active":
            ctk.CTkButton(btn_frame, text="💳  Record Payment",
                          command=lambda: self.master.show_screen("repayments"),
                          **primary_button_style()).grid(
                row=0, column=0, columnspan=3, sticky="ew")

        ctk.CTkButton(self.detail_panel, text="🖨  Print Loan Agreement",
                      height=38, fg_color=COLORS["accent_gold"],
                      hover_color=COLORS["accent_gold_dark"],
                      text_color=_TEXT, font=FONTS["button"], corner_radius=8,
                      command=lambda: self._print_loan_agreement(loan)).pack(
            fill="x", padx=20, pady=(0, 20))

    def _edit_loan_form(self, loan):
        from app.core.services.loan_service import LoanService
        loan = LoanService.get_loan_by_id(loan.id)
        self._new_loan_form(loan=loan)

    def _render_collateral(self, loan):
        from app.database.connection import get_db
        from app.core.models.collateral import Collateral
        with get_db() as db:
            collaterals = db.query(Collateral).filter_by(loan_id=loan.id).all()
            coll_data   = [(c.description, c.file_path) for c in collaterals]
        if not coll_data:
            return
        self._divider()
        ctk.CTkLabel(self.detail_panel, text="Collateral Documents",
                     font=FONTS["subheading"],
                     text_color=COLORS["text_secondary"]).pack(
            anchor="w", padx=20)
        coll_grid = ctk.CTkFrame(self.detail_panel, fg_color="transparent")
        coll_grid.pack(fill="x", padx=20, pady=8)
        for i, (desc, fpath) in enumerate(coll_data):
            tile = ctk.CTkFrame(coll_grid, fg_color=COLORS["bg_input"],
                                corner_radius=6, width=80, height=80)
            tile.grid(row=0, column=i, padx=4)
            tile.grid_propagate(False)
            if os.path.exists(fpath):
                try:
                    img = Image.open(fpath)
                    img.thumbnail((72, 72))
                    ctkimg = ctk.CTkImage(light_image=img, dark_image=img,
                                         size=(72, 72))
                    ctk.CTkLabel(tile, image=ctkimg, text="",
                                 fg_color="transparent").pack(expand=True)
                except Exception:
                    ctk.CTkLabel(tile, text="DOC", font=FONTS["caption"],
                                 text_color=COLORS["text_muted"]).pack(
                        expand=True)
            else:
                ctk.CTkLabel(tile, text="DOC", font=FONTS["caption"],
                             text_color=COLORS["text_muted"]).pack(expand=True)
            ctk.CTkLabel(coll_grid, text=desc[:12], font=FONTS["caption"],
                         text_color=COLORS["text_muted"]).grid(
                row=1, column=i, padx=4)

    def _render_repayments(self, loan):
        from app.core.services.repayment_service import RepaymentService
        repayments = RepaymentService.get_repayments_for_loan(loan.id)
        if not repayments:
            return
        self._divider()
        ctk.CTkLabel(self.detail_panel, text="Repayment History",
                     font=FONTS["subheading"],
                     text_color=COLORS["text_secondary"]).pack(
            anchor="w", padx=20)
        for r in repayments:
            row = ctk.CTkFrame(self.detail_panel,
                               fg_color=COLORS["bg_input"], corner_radius=6)
            row.pack(fill="x", padx=20, pady=4)
            ctk.CTkLabel(row,
                         text=f"UGX {float(r.amount):,.0f}  •  {r.payment_date}",
                         font=FONTS["body_small"],
                         text_color=COLORS["accent_green"]).pack(
                anchor="w", padx=12, pady=8)

    # ══════════════════════════════════════════════════════════════════════════
    # New loan form — redesigned
    # ══════════════════════════════════════════════════════════════════════════

    def _new_loan_form(self, loan=None):
        self.selected_loan       = loan
        self.found_client_id     = loan.client_id if loan else None
        self._found_client_obj   = None
        self._collateral_files   = []
        self._statement_analysed = False
        self._search_popup       = None

        for w in self.detail_panel.winfo_children():
            w.destroy()

        title_text = "Edit Pending Loan" if loan else "New Loan Application"
        ctk.CTkLabel(self.detail_panel, text=title_text,
                     font=FONTS["subtitle"],
                     text_color=COLORS["accent_green_dark"]).pack(
            anchor="w", padx=20, pady=(20, 2))
        ctk.CTkLabel(
            self.detail_panel,
            text=("Update the pending application below and click Save."
                  if loan else
                  "Fill in all required fields (*) then click Submit."),
            font=FONTS["body_small"],
            text_color=COLORS["text_muted"]).pack(
            anchor="w", padx=20, pady=(0, 8))

        # ── Loan ID preview ────────────────────────────────────────────────
        id_frame = ctk.CTkFrame(self.detail_panel,
                                fg_color=COLORS["bg_input"], corner_radius=8,
                                border_width=1, border_color=COLORS["border"])
        id_frame.pack(fill="x", padx=20, pady=(0, 4))
        id_inner = ctk.CTkFrame(id_frame, fg_color="transparent")
        id_inner.pack(fill="x", padx=14, pady=10)
        id_inner.columnconfigure(1, weight=1)
        ctk.CTkLabel(id_inner, text="🔖  Loan ID:",
                     font=FONTS["body_small"],
                     text_color=COLORS["text_muted"], anchor="w").grid(
            row=0, column=0, sticky="w", padx=(0, 12))
        ctk.CTkLabel(id_inner,
                     text=(loan.loan_number if loan
                           else "Auto-assigned on submission"),
                     font=FONTS["body_small"],
                     text_color=COLORS["text_muted"], anchor="w").grid(
            row=0, column=1, sticky="w")

        # ══════════════════════════════════════════════════════════════════
        # CLIENT SEARCH — live popup
        # ══════════════════════════════════════════════════════════════════
        self._section("Client Information")

        ctk.CTkLabel(
            self.detail_panel,
            text="Type a name or NIN — a popup will show matching clients.",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="w").pack(fill="x", padx=20, pady=(0, 4))

        # Search entry
        self.client_search_var = ctk.StringVar()
        self.client_search_entry = ctk.CTkEntry(
            self.detail_panel,
            textvariable=self.client_search_var,
            placeholder_text="Type name or NIN (min 2 characters)...",
            **input_style())
        self.client_search_entry.pack(fill="x", padx=20)
        self.client_search_entry.bind(
            "<KeyRelease>", self._on_client_key)
        self.client_search_entry.bind(
            "<FocusOut>",
            lambda e: self.after(300, self._close_client_popup))

        # Selected client display card
        self.client_card = ctk.CTkFrame(
            self.detail_panel,
            fg_color=COLORS["bg_input"], corner_radius=8)
        self.client_card.pack(fill="x", padx=20, pady=(6, 0))
        self.client_card_label = ctk.CTkLabel(
            self.client_card,
            text="No client selected yet.",
            font=FONTS["body_small"],
            text_color=COLORS["text_muted"],
            anchor="w", justify="left")
        self.client_card_label.pack(padx=12, pady=10, anchor="w")

        # Monthly income (auto-filled from client, editable)
        self._flabel("Stated Monthly Income (UGX)")
        self.income_var = ctk.StringVar()
        self.income_entry = ctk.CTkEntry(
            self.detail_panel,
            textvariable=self.income_var,
            placeholder_text="Auto-filled from client record",
            **input_style())
        self.income_entry.pack(fill="x", padx=20)
        ctk.CTkLabel(
            self.detail_panel,
            text="⚠  Stated income may be overstated. "
                 "Use statement analysis for a more accurate ceiling.",
            font=FONTS["caption"],
            text_color=COLORS["warning"] if COLORS.get("warning") else "#D69E2E",
            anchor="w", wraplength=280).pack(
            fill="x", padx=20, pady=(2, 0))

        if loan:
            from app.core.services.client_service import ClientService
            client = ClientService.get_client_by_id(loan.client_id)
            if client:
                self._apply_client_selection(client)
                self.client_search_entry.configure(state="disabled")

        # ══════════════════════════════════════════════════════════════════
        # LOAN DETAILS
        # ══════════════════════════════════════════════════════════════════
        self._section("Loan Details")

        self._flabel("Loan Type *")
        self.loan_type_var = ctk.StringVar(value=LOAN_TYPES[0])
        ctk.CTkOptionMenu(
            self.detail_panel, variable=self.loan_type_var,
            values=LOAN_TYPES,
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_green"],
            button_hover_color=COLORS["accent_green_dark"],
            text_color=COLORS["text_primary"],
            font=FONTS["body_small"]).pack(fill="x", padx=20)

        self._flabel("Principal Amount (UGX) *")
        self.principal_entry = ctk.CTkEntry(
            self.detail_panel,
            placeholder_text="e.g.  500000  or  500,000",
            **input_style())
        self.principal_entry.pack(fill="x", padx=20)
        self.principal_entry.bind("<KeyRelease>", self._update_interest_preview)

        self._flabel("Duration (months) *")
        self.duration_entry = ctk.CTkEntry(
            self.detail_panel,
            placeholder_text="e.g.  12  (for 1 year)",
            **input_style())
        self.duration_entry.pack(fill="x", padx=20)
        self.duration_entry.bind("<KeyRelease>", self._update_interest_preview)

        self._flabel("Application Date *")
        date_row = ctk.CTkFrame(self.detail_panel, fg_color="transparent")
        date_row.pack(fill="x", padx=20)
        date_row.columnconfigure(0, weight=1)
        self.application_date_picker = DatePicker(
            date_row,
            initial_date=(loan.application_date
                          if loan and loan.application_date
                          else date.today()))
        self.application_date_picker.grid(row=0, column=0, sticky="ew")

        self._flabel("Purpose / Reason")
        self.purpose_entry = ctk.CTkEntry(
            self.detail_panel,
            placeholder_text="e.g.  School fees, Business capital...",
            **input_style())
        self.purpose_entry.pack(fill="x", padx=20)

        # Interest preview
        self.interest_preview = ctk.CTkLabel(
            self.detail_panel, text="",
            font=FONTS["body_small"],
            text_color=COLORS["accent_green_dark"])
        self.interest_preview.pack(anchor="w", padx=20, pady=(8, 0))

        if loan:
            self.loan_type_var.set(
                loan.loan_type.value if loan.loan_type else LOAN_TYPES[0])
            self.principal_entry.insert(0, str(int(loan.principal_amount)))
            self.duration_entry.insert(0, str(loan.duration_months))
            self.purpose_entry.insert(0, loan.purpose or "")
            self._update_interest_preview()

        # ══════════════════════════════════════════════════════════════════
        # STATEMENT ANALYSIS — with scenario cards
        # ══════════════════════════════════════════════════════════════════
        self._section("Financial Statement Analysis")

        ctk.CTkLabel(
            self.detail_panel,
            text=(
                "Upload a MoMo or bank statement → click Analyse → "
                "pick a scenario card to auto-fill principal & duration.\n"
                "If skipped, the stated monthly income above is used."
            ),
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            wraplength=300, justify="left").pack(
            anchor="w", padx=20, pady=(0, 8))

        def _on_statement_accepted(principal: float, duration: int, ceiling):
            """Called when a scenario card Accept button is clicked."""
            self._statement_analysed = True
            self.principal_entry.delete(0, "end")
            self.principal_entry.insert(0, str(int(principal)))
            self.duration_entry.delete(0, "end")
            self.duration_entry.insert(0, str(int(duration)))
            self._update_interest_preview()
            # Show confirmation
            if hasattr(self, "stmt_status_label"):
                self.stmt_status_label.configure(
                    text=f"✓ Statement analysed — scenario accepted: "
                         f"UGX {int(principal):,} / {duration} months",
                    text_color=COLORS["accent_green"])

        stmt_frame = ctk.CTkFrame(self.detail_panel, fg_color="transparent")
        stmt_frame.pack(fill="x", padx=20, pady=(0, 4))
        stmt_frame.columnconfigure(0, weight=1)

        self.statement_widget = StatementAnalysisWidget(
            stmt_frame,
            on_accept=_on_statement_accepted,
            current_user=self.current_user)
        self.statement_widget.grid(row=0, column=0, sticky="ew")

        # Statement status label
        self.stmt_status_label = ctk.CTkLabel(
            self.detail_panel, text="",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"], anchor="w")
        self.stmt_status_label.pack(fill="x", padx=20, pady=(2, 0))

        # ══════════════════════════════════════════════════════════════════
        # COLLATERAL
        # ══════════════════════════════════════════════════════════════════
        self._section("Collateral Documents")
        ctk.CTkLabel(self.detail_panel,
                     text="Attach photos or scans (land title, logbook, etc.)",
                     font=FONTS["caption"],
                     text_color=COLORS["text_muted"]).pack(
            anchor="w", padx=20, pady=(0, 8))
        coll_btn_row = ctk.CTkFrame(self.detail_panel, fg_color="transparent")
        coll_btn_row.pack(fill="x", padx=20)
        ctk.CTkButton(coll_btn_row, text="📎  Browse Files",
                      height=36, font=FONTS["body_small"],
                      fg_color=COLORS["accent_green"],
                      hover_color=COLORS["accent_green_dark"],
                      text_color=_WHITE, corner_radius=8,
                      command=self._add_collateral).pack(side="left")
        self.coll_count_label = ctk.CTkLabel(
            coll_btn_row, text="No files added yet",
            font=FONTS["caption"], text_color=COLORS["text_muted"])
        self.coll_count_label.pack(side="left", padx=(12, 0))
        self.coll_thumb_frame = ctk.CTkFrame(
            self.detail_panel, fg_color="transparent")
        self.coll_thumb_frame.pack(fill="x", padx=20, pady=8)

        # ══════════════════════════════════════════════════════════════════
        # SUBMIT
        # ══════════════════════════════════════════════════════════════════
        self._divider()
        self.loan_form_error = ctk.CTkLabel(
            self.detail_panel, text="",
            font=FONTS["body_small"], text_color=COLORS["danger"],
            wraplength=300, justify="left")
        self.loan_form_error.pack(padx=20, pady=(8, 4), anchor="w")

        ctk.CTkButton(
            self.detail_panel,
            text="✔  Submit Loan Application",
            command=self._submit_loan,
            **primary_button_style()).pack(fill="x", padx=20, pady=(4, 24))

    # ══════════════════════════════════════════════════════════════════════════
    # Live client search popup
    # ══════════════════════════════════════════════════════════════════════════

    def _on_client_key(self, event=None):
        term = self.client_search_var.get().strip()
        if len(term) >= 2:
            threading.Thread(
                target=self._fetch_clients_for_popup,
                args=(term,), daemon=True).start()
        else:
            self._close_client_popup()

    def _fetch_clients_for_popup(self, term: str):
        try:
            from app.core.services.client_service import ClientService
            clients = ClientService.get_all_clients(search=term)
            self.after(0, lambda: self._show_client_popup(clients))
        except Exception as e:
            print(f"[LoansScreen] Client search error: {e}")

    def _show_client_popup(self, clients: list):
        # Destroy any existing popup
        self._close_client_popup()
        if not clients:
            return

        # Get position of the search entry
        entry = self.client_search_entry
        entry.update_idletasks()

        # We need root-level coordinates
        try:
            x = entry.winfo_rootx()
            y = entry.winfo_rooty() + entry.winfo_height() + 2
            w = max(entry.winfo_width(), 400)
        except Exception:
            return

        rows_shown = min(len(clients), 6)
        h          = rows_shown * 56 + 8

        popup = tk.Toplevel(self)
        popup.wm_overrideredirect(True)
        popup.geometry(f"{w}x{h}+{x}+{y}")
        popup.attributes("-topmost", True)
        popup.configure(bg=_WHITE)
        self._search_popup = popup

        # Outer border frame
        border = tk.Frame(popup, bg=_BORDER, padx=1, pady=1)
        border.pack(fill="both", expand=True)

        # Scrollable inner
        canvas = tk.Canvas(border, bg=_WHITE, highlightthickness=0,
                           height=h - 2)
        canvas.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(border, orient="vertical", command=canvas.yview)
        if len(clients) > 6:
            sb.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=sb.set)

        inner = tk.Frame(canvas, bg=_WHITE)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(
                       scrollregion=canvas.bbox("all")))

        for i, client in enumerate(clients[:10]):
            bg  = _WHITE if i % 2 == 0 else "#F8FFF8"
            row = tk.Frame(inner, bg=bg, cursor="hand2", height=54)
            row.pack(fill="x")
            row.pack_propagate(False)

            # Hover
            def _enter(e, r=row):  r.configure(bg="#D5EDD5")
            def _leave(e, r=row, b=bg): r.configure(bg=b)
            row.bind("<Enter>", _enter)
            row.bind("<Leave>", _leave)

            # Name
            tk.Label(row, text=client.full_name, bg=bg, fg=_TEXT,
                     font=("Helvetica", 10, "bold"), anchor="w").pack(
                side="left", padx=(12, 4), pady=(8, 2), fill="x")

            # Detail line
            detail_row = tk.Frame(row, bg=bg)
            detail_row.pack(side="left", fill="x", expand=True,
                            padx=(0, 8))

            details = []
            if client.nin:
                details.append(f"NIN: {client.nin}")
            if client.phone_number:
                details.append(f"📞 {client.phone_number}")
            if client.occupation:
                details.append(client.occupation)

            tk.Label(detail_row,
                     text="  ·  ".join(details) if details else "—",
                     bg=bg, fg=_MUTED,
                     font=("Helvetica", 8), anchor="w").pack(
                side="left", pady=(0, 4))

            # Select button
            tk.Button(row, text="Select",
                      bg=_GREEN, fg=_WHITE,
                      relief="flat", bd=0,
                      font=("Helvetica", 9, "bold"),
                      padx=10, pady=3, cursor="hand2",
                      command=lambda c=client: self._select_client(c)).pack(
                side="right", padx=8, pady=10)

            # Divider
            if i < len(clients) - 1:
                tk.Frame(inner, bg=_BORDER, height=1).pack(
                    fill="x", padx=8)

            # Bind click on whole row
            for widget in [row, detail_row] + list(row.winfo_children()):
                try:
                    if not isinstance(widget, tk.Button):
                        widget.bind("<Button-1>",
                                    lambda e, c=client: self._select_client(c))
                except Exception:
                    pass

    def _select_client(self, client):
        """Called when a client is chosen from the popup."""
        self._close_client_popup()
        self._apply_client_selection(client)

    def _apply_client_selection(self, client):
        """Apply the selected client to the form."""
        self.found_client_id   = client.id
        self._found_client_obj = client

        # Update search entry text
        if hasattr(self, "client_search_var"):
            self.client_search_var.set(client.full_name)

        # Update client card
        nin   = client.nin           or "—"
        phone = client.phone_number  or "—"
        occ   = client.occupation    or "—"
        inc   = (f"UGX {float(str(client.monthly_income).replace(',','')):.0f}"
                 if client.monthly_income else "—")

        self.client_card_label.configure(
            text=(f"✔  {client.full_name}\n"
                  f"NIN: {nin}   Phone: {phone}\n"
                  f"Occupation: {occ}   Stated Income: {inc}"),
            text_color=COLORS["accent_green"])

        # Auto-fill monthly income from client record
        if client.monthly_income and hasattr(self, "income_var"):
            try:
                inc_val = float(
                    str(client.monthly_income).replace(",", "").strip())
                self.income_var.set(str(int(inc_val)))
            except (ValueError, TypeError):
                pass

    def _close_client_popup(self):
        if self._search_popup:
            try:
                self._search_popup.destroy()
            except Exception:
                pass
            self._search_popup = None

    # ── Form helpers ───────────────────────────────────────────────────────────

    def _section(self, text: str):
        ctk.CTkFrame(self.detail_panel, fg_color=COLORS["border"],
                     height=1).pack(fill="x", padx=20, pady=(14, 0))
        ctk.CTkLabel(self.detail_panel, text=text,
                     font=FONTS["subheading"],
                     text_color=COLORS["accent_green_dark"],
                     anchor="w").pack(fill="x", padx=20, pady=(6, 4))

    def _flabel(self, text: str):
        ctk.CTkLabel(self.detail_panel, text=text,
                     font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"],
                     anchor="w").pack(fill="x", padx=20, pady=(8, 2))

    def _divider(self):
        ctk.CTkFrame(self.detail_panel, fg_color=COLORS["border"],
                     height=1).pack(fill="x", padx=20, pady=8)

    def _update_interest_preview(self, *_):
        try:
            principal = _to_float(self.principal_entry.get())
            months    = _to_int(self.duration_entry.get())
            if principal <= 0 or months <= 0:
                self.interest_preview.configure(text="")
                return
            interest = principal * 0.10 * months
            total    = principal + interest
            monthly  = total / months
            self.interest_preview.configure(
                text=(f"Interest: UGX {interest:,.0f}  |  "
                      f"Total: UGX {total:,.0f}  |  "
                      f"Monthly: UGX {monthly:,.0f}"))
        except Exception:
            self.interest_preview.configure(text="")

    # ── Collateral ─────────────────────────────────────────────────────────────

    def _add_collateral(self):
        picker = FilePicker(self.winfo_toplevel())
        self.wait_window(picker)
        if picker.result:
            for f in picker.result:
                if f not in self._collateral_files:
                    self._collateral_files.append(f)
            self._refresh_collateral_thumbs()

    def _refresh_collateral_thumbs(self):
        for w in self.coll_thumb_frame.winfo_children():
            w.destroy()
        count = len(self._collateral_files)
        self.coll_count_label.configure(
            text=f"{count} file{'s' if count != 1 else ''} added"
            if count else "No files added yet")
        for i, fpath in enumerate(self._collateral_files):
            tile = ctk.CTkFrame(self.coll_thumb_frame,
                                fg_color=COLORS["bg_input"],
                                corner_radius=6, width=72, height=72)
            tile.grid(row=0, column=i * 2, padx=4, pady=4)
            tile.grid_propagate(False)
            try:
                img = Image.open(fpath)
                img.thumbnail((66, 66))
                ctkimg = ctk.CTkImage(light_image=img, dark_image=img,
                                      size=(66, 66))
                ctk.CTkLabel(tile, image=ctkimg, text="",
                             fg_color="transparent").pack(expand=True)
            except Exception:
                ext = os.path.splitext(fpath)[1].upper()
                ctk.CTkLabel(tile, text=ext or "DOC", font=FONTS["caption"],
                             text_color=COLORS["text_muted"]).pack(expand=True)
            ctk.CTkLabel(self.coll_thumb_frame,
                         text=os.path.basename(fpath)[:10],
                         font=FONTS["caption"],
                         text_color=COLORS["text_muted"]).grid(
                row=1, column=i * 2, padx=4)
            ctk.CTkButton(
                self.coll_thumb_frame, text="✕", width=20, height=20,
                fg_color=COLORS["danger"], hover_color="#A93226",
                text_color=_WHITE, font=("Helvetica", 10), corner_radius=4,
                command=lambda p=fpath: self._remove_collateral(p)).grid(
                row=0, column=i * 2 + 1, sticky="n")

    def _remove_collateral(self, fpath: str):
        if fpath in self._collateral_files:
            self._collateral_files.remove(fpath)
        self._refresh_collateral_thumbs()

    # ══════════════════════════════════════════════════════════════════════════
    # Submit — with statement reminder and auto risk scoring
    # ══════════════════════════════════════════════════════════════════════════

    def _submit_loan(self):
        from app.core.services.loan_service import LoanService
        from app.database.connection import get_db
        from app.core.models.collateral import Collateral
        from app.core.models.loan import Loan

        # ── Validation ────────────────────────────────────────────────────
        if not self.found_client_id:
            self.loan_form_error.configure(
                text="⚠  Please search for and select a client first.")
            return

        try:
            principal = _to_float(self.principal_entry.get())
        except ValueError as e:
            self.loan_form_error.configure(text=f"⚠  Principal: {e}")
            return
        if principal <= 0:
            self.loan_form_error.configure(
                text="⚠  Principal must be greater than zero.")
            return

        try:
            duration = _to_int(self.duration_entry.get())
        except ValueError:
            self.loan_form_error.configure(
                text="⚠  Duration must be a whole number of months (e.g. 12).")
            return
        if duration <= 0:
            self.loan_form_error.configure(
                text="⚠  Duration must be at least 1 month.")
            return

        # ── Statement reminder (non-blocking) ─────────────────────────────
        # If no statement was analysed, remind the user but still allow submit.
        # The stated income from the client record is used as the ceiling basis.
        if not self._statement_analysed:
            income_raw = self.income_var.get().strip() if hasattr(
                self, "income_var") else ""
            if income_raw:
                self.loan_form_error.configure(
                    text=(
                        "ℹ  No statement analysed — using stated monthly income "
                        f"(UGX {income_raw}) for the loan ceiling estimate. "
                        "Note: stated income may be overstated. "
                        "Click Submit again to proceed without a statement."
                    ),
                    text_color=COLORS.get("warning", "#D69E2E"))

                # If this is the first time they hit submit without a statement,
                # warn them but mark as acknowledged so second click proceeds.
                if not getattr(self, "_stmt_warning_shown", False):
                    self._stmt_warning_shown = True
                    return   # let them read the warning first
            # No income + no statement → continue anyway (loan officer's call)

        self._stmt_warning_shown = False
        self.loan_form_error.configure(
            text="Saving loan...", text_color=COLORS["text_muted"])

        try:
            # ── Save loan ─────────────────────────────────────────────────
            if (self.selected_loan
                    and self.selected_loan.status.value == "pending"):
                loan = LoanService.update_loan(
                    loan_id          = self.selected_loan.id,
                    loan_type        = self.loan_type_var.get(),
                    principal_amount = principal,
                    duration_months  = duration,
                    purpose          = self.purpose_entry.get().strip() or None,
                    application_date = self.application_date_picker.get_date(),
                    updated_by_id    = (self.current_user.id
                                        if self.current_user else None),
                )
            else:
                loan = LoanService.create_loan(
                    client_id        = self.found_client_id,
                    loan_type        = self.loan_type_var.get(),
                    principal_amount = principal,
                    duration_months  = duration,
                    purpose          = self.purpose_entry.get().strip() or None,
                    created_by_id    = (self.current_user.id
                                        if self.current_user else None),
                )
                # Set application date
                with get_db() as db:
                    l = db.query(Loan).filter_by(id=loan.id).first()
                    if l:
                        l.application_date = self.application_date_picker.get_date()
                        db.commit()

            # ── Save collateral ───────────────────────────────────────────
            os.makedirs(COLLATERAL_UPLOAD_DIR, exist_ok=True)
            with get_db() as db:
                for fpath in self._collateral_files:
                    fname = f"loan_{loan.id}_{os.path.basename(fpath)}"
                    dest  = os.path.join(COLLATERAL_UPLOAD_DIR, fname)
                    shutil.copy2(fpath, dest)
                    db.add(Collateral(
                        loan_id        = loan.id,
                        description    = os.path.splitext(
                            os.path.basename(fpath))[0][:100],
                        file_name      = fname,
                        file_path      = dest,
                        file_type      = os.path.splitext(fpath)[1].lower(),
                        file_size_kb   = int(os.path.getsize(fpath) / 1024),
                        uploaded_by_id = (self.current_user.id
                                          if self.current_user else None),
                    ))
                    db.commit()

            # ── Save statement analysis ───────────────────────────────────
            try:
                if hasattr(self, "statement_widget"):
                    stmt_result    = self.statement_widget.get_statement_result()
                    ceiling_result = self.statement_widget.get_ceiling_result()
                    if (stmt_result
                            and stmt_result.source_type not in (
                                "error", "unknown", None)):
                        from app.core.models.statement_analysis import (
                            StatementAnalysis)
                        with get_db() as db:
                            db.add(StatementAnalysis(
                                loan_id             = loan.id,
                                source_file         = (
                                    self.statement_widget._file_path or ""),
                                statement_type      = stmt_result.source_type,
                                months_covered      = stmt_result.months_covered,
                                avg_monthly_income  = float(
                                    stmt_result.avg_monthly_income),
                                avg_monthly_expense = float(
                                    stmt_result.avg_monthly_expense),
                                net_monthly_flow    = float(
                                    stmt_result.net_monthly_flow),
                                income_consistency  = stmt_result.income_consistency,
                                recommended_ceiling = float(
                                    ceiling_result.recommended_ceiling)
                                    if ceiling_result else 0,
                                affordability_score = (
                                    ceiling_result.affordability_score
                                    if ceiling_result else 0),
                                created_by_id       = (
                                    self.current_user.id
                                    if self.current_user else None),
                            ))
                            db.commit()
            except Exception:
                pass   # statement save is optional — never block submission

            # ── AUTO RISK SCORING ─────────────────────────────────────────
            # Runs silently in background. Writes risk_score to the loan
            # record so the manager sees it before approving.
            # Human still approves or rejects — agent only informs.
            loan_id_for_scoring = loan.id
            stated_income = 0.0
            try:
                income_raw = self.income_var.get().strip()
                if income_raw:
                    stated_income = float(income_raw.replace(",", ""))
            except (ValueError, AttributeError):
                pass

            def _run_auto_risk():
                try:
                    from app.core.agents.auto_risk import auto_score_loan
                    auto_score_loan(loan_id_for_scoring)
                    print(f"[LoansScreen] Auto risk scoring complete "
                          f"for loan #{loan_id_for_scoring}")
                except Exception as e:
                    print(f"[LoansScreen] Auto risk error: {e}")

            threading.Thread(target=_run_auto_risk, daemon=True).start()
            # ── END AUTO RISK ─────────────────────────────────────────────

            # ── Reset form ────────────────────────────────────────────────
            self.loan_form_error.configure(
                text=f"✔  Loan {loan.loan_number} saved. "
                     f"Risk assessment running in background...",
                text_color=COLORS["accent_green"])
            self._collateral_files   = []
            self._statement_analysed = False
            self.found_client_id     = None
            self._found_client_obj   = None

            self._load_loans()
            if (self.selected_loan
                    and self.selected_loan.status.value == "pending"):
                self._on_loan_selected({"id": loan.id})
            else:
                self._show_empty_state()

        except Exception as e:
            self.loan_form_error.configure(
                text=f"⚠  {e}",
                text_color=COLORS["danger"])

    # ── Approve / reject ───────────────────────────────────────────────────────

    def _approve_loan(self, loan_id: int):
        from app.core.services.loan_service import LoanService
        try:
            LoanService.approve_loan(
                loan_id,
                approved_by_id=(self.current_user.id
                                if self.current_user else None))
            self._load_loans()
            self._show_empty_state()
        except Exception as e:
            self._show_error_popup(str(e))

    def _reject_loan(self, loan_id: int):
        from app.core.services.loan_service import LoanService
        try:
            LoanService.reject_loan(
                loan_id,
                reason="Rejected by loan officer.",
                rejected_by_id=(self.current_user.id
                                if self.current_user else None))
            self._load_loans()
            self._show_empty_state()
        except Exception as e:
            self._show_error_popup(str(e))

    def _show_error_popup(self, message: str):
        err = tk.Toplevel(self.winfo_toplevel())
        err.title("Error")
        err.geometry("360x130")
        err.configure(bg=_LIGHT)
        err.grab_set()
        sw, sh = err.winfo_screenwidth(), err.winfo_screenheight()
        err.geometry(f"360x130+{(sw-360)//2}+{(sh-130)//2}")
        tk.Label(err, text=message, bg=_LIGHT, fg="#C0392B",
                 font=("Helvetica", 10), wraplength=320).pack(pady=20)
        tk.Button(err, text="Close", bg=_GREEN, fg=_WHITE,
                  relief="flat", padx=20, pady=6,
                  command=err.destroy).pack()

    # ── Print loan agreement ───────────────────────────────────────────────────

    def _print_loan_agreement(self, loan):
        from app.ui.components.save_dialog import SaveDialog
        dialog = SaveDialog(
            self.winfo_toplevel(),
            title        = "Save Loan Agreement As",
            default_name = f"loan_agreement_{loan.loan_number}.pdf",
            extension    = ".pdf")
        self.wait_window(dialog)
        if not dialog.result:
            return
        try:
            from app.core.services.report_service import ReportService
            from app.core.services.client_service import ClientService
            import subprocess
            client   = ClientService.get_client_by_id(loan.client_id)
            pdf_path = ReportService.generate_loan_agreement(
                loan            = loan,
                client          = client,
                generated_by_id = (self.current_user.id
                                   if self.current_user else None),
                save_path       = dialog.result)
            if os.path.exists(pdf_path):
                subprocess.Popen(["xdg-open", pdf_path])
        except Exception as e:
            self._show_error_popup(f"Could not generate document:\n{e}")

    # ── Load loans table ───────────────────────────────────────────────────────

    def _load_loans(self, *_):
        try:
            from app.database.connection import get_db
            from sqlalchemy import text

            status = (self.status_filter.get()
                      if hasattr(self, "status_filter") else "All")
            search = (self.search_var.get().strip()
                      if hasattr(self, "search_var") else None)

            with get_db() as db:
                conditions = ["1=1"]
                params     = {}

                if status and status != "All":
                    conditions.append("l.status = :status")
                    params["status"] = status

                if search:
                    conditions.append(
                        "(c.full_name ILIKE :search "
                        "OR l.loan_number ILIKE :search "
                        "OR c.nin ILIKE :search "
                        "OR c.phone_number ILIKE :search)")
                    params["search"] = f"%{search}%"

                where = " AND ".join(conditions)

                count_sql = text(f"""
                    SELECT COUNT(*) FROM loans l
                    JOIN clients c ON l.client_id = c.id
                    WHERE {where}
                """)
                self.total_records = db.execute(count_sql, params).scalar() or 0
                self.total_pages   = max(
                    1,
                    (self.total_records + self.page_size - 1) // self.page_size)
                self.current_page  = max(
                    1, min(self.current_page, self.total_pages))
                offset = (self.current_page - 1) * self.page_size

                sql = text(f"""
                    SELECT l.id, l.loan_number, l.loan_type,
                           l.principal_amount, l.status, c.full_name
                    FROM   loans   l
                    JOIN   clients c ON l.client_id = c.id
                    WHERE  {where}
                    ORDER  BY l.id DESC
                    LIMIT  {self.page_size} OFFSET {offset}
                """)
                rows = [
                    {
                        "id":          r.id,
                        "loan_number": r.loan_number,
                        "client_name": r.full_name or "—",
                        "loan_type":   r.loan_type or "—",
                        "principal":   f"UGX {float(r.principal_amount):,.0f}",
                        "status":      (r.status.upper() if r.status else "—"),
                    }
                    for r in db.execute(sql, params).mappings()
                ]

            if hasattr(self, "table"):
                self.after(0, lambda: self.table.update_rows(rows))
            self.after(0, self._update_pagination_controls)

        except Exception as e:
            print(f"[LoansScreen] Load error: {e}")

    # ── Pagination ─────────────────────────────────────────────────────────────

    def _on_status_change(self, value):
        self.current_page = 1
        self._load_loans()

    def _prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._load_loans()

    def _next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._load_loans()

    def _update_pagination_controls(self):
        start = (self.current_page - 1) * self.page_size + 1
        end   = min(self.current_page * self.page_size, self.total_records)
        if self.total_records == 0:
            self.page_label.configure(text="No records found")
        else:
            self.page_label.configure(
                text=(f"Page {self.current_page} of {self.total_pages} "
                      f"({start}–{end} of {self.total_records} records)"))
        self.prev_btn.configure(
            state="normal" if self.current_page > 1 else "disabled")
        self.next_btn.configure(
            state="normal" if self.current_page < self.total_pages else "disabled")

    # ── Search ─────────────────────────────────────────────────────────────────

    def _perform_search(self):
        self.current_page = 1
        self._load_loans()

    def _on_search_change(self, *_):
        current = self.search_var.get().strip()
        if self._search_timer:
            self.after_cancel(self._search_timer)
        if not current and self._last_search_value:
            self.current_page = 1
            self._load_loans()
        elif current:
            self._search_timer = self.after(300, self._perform_debounced_search)
        self._last_search_value = current

    def _perform_debounced_search(self):
        self.current_page = 1
        self._load_loans()
        self._search_timer = None