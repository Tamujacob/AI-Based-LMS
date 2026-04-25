"""
app/ui/components/save_dialog.py
──────────────────────────────────
Themed file-save dialog matching the Bingongold green/gold brand.
Returns the chosen save path via self.result, or None if cancelled.

Usage:
    dialog = SaveDialog(master, title="Save Report As",
                        default_name="report.pdf", extension=".pdf")
    master.wait_window(dialog)
    if dialog.result:
        # use dialog.result as the save path
"""

import os
import tkinter as tk

_GREEN_DARK = "#1A5C1E"
_GREEN      = "#34A038"
_GOLD       = "#D4A820"
_WHITE      = "#FFFFFF"
_TEXT       = "#1A2E1A"
_LIGHT      = "#F4F6F4"
_BORDER     = "#C8DFC8"
_MUTED      = "#7A9A7A"
_HOVER      = "#2E7D32"


class SaveDialog(tk.Toplevel):
    """
    Themed Save As dialog.
    After wait_window(), check self.result for the chosen path (or None).
    """

    def __init__(self, master, title: str = "Save File As",
                 default_name: str = "document.pdf",
                 extension: str = ".pdf"):
        super().__init__(master)
        self.result       = None
        self._extension   = extension
        self._current_dir = os.path.expanduser("~")
        self._dir_buttons = {}

        self.title(title)
        self.resizable(True, True)
        self.geometry("660x500")
        self.configure(bg=_LIGHT)
        self.update_idletasks()
        self.grab_set()

        # Centre on screen
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"660x500+{(sw-660)//2}+{(sh-500)//2}")

        self._build(title, default_name)
        self._load_dir(self._current_dir)

    # ── Build UI ───────────────────────────────────────────────────────────────

    def _build(self, title: str, default_name: str):

        # ── Header ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=_GREEN_DARK, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text=f"💾  {title}",
                 bg=_GREEN_DARK, fg=_WHITE,
                 font=("Helvetica", 12, "bold")).pack(
            side="left", padx=18, fill="y")

        tk.Button(hdr, text="✕", bg=_GREEN_DARK, fg=_WHITE,
                  activebackground="#C0392B", activeforeground=_WHITE,
                  relief="flat", bd=0, padx=14, cursor="hand2",
                  font=("Helvetica", 13),
                  command=self._cancel).pack(side="right", fill="y")

        # ── Quick-access bar ──────────────────────────────────────────────
        quick = tk.Frame(self, bg=_GREEN, height=38)
        quick.pack(fill="x")
        quick.pack_propagate(False)

        for label, path_fn in [
            ("⬆  Up",        self._go_up),
            ("🏠  Home",      lambda: self._load_dir(os.path.expanduser("~"))),
            ("🖥  Desktop",   lambda: self._load_dir(
                os.path.join(os.path.expanduser("~"), "Desktop"))),
            ("📥  Downloads", lambda: self._load_dir(
                os.path.join(os.path.expanduser("~"), "Downloads"))),
            ("📄  Documents", lambda: self._load_dir(
                os.path.join(os.path.expanduser("~"), "Documents"))),
        ]:
            tk.Button(quick, text=label, bg=_GREEN, fg=_WHITE,
                      activebackground=_HOVER, activeforeground=_WHITE,
                      relief="flat", bd=0, padx=10, cursor="hand2",
                      font=("Helvetica", 9, "bold"),
                      command=path_fn).pack(side="left", fill="y")

        # Current path label
        self.path_label = tk.Label(quick, text="", bg=_GREEN,
                                   fg=_GOLD, font=("Helvetica", 9),
                                   anchor="w")
        self.path_label.pack(side="left", fill="both", expand=True, padx=8)

        # ── File/folder browser ────────────────────────────────────────────
        browser_outer = tk.Frame(self, bg=_BORDER, padx=1, pady=1)
        browser_outer.pack(fill="both", expand=True, padx=12, pady=(8, 4))

        canvas    = tk.Canvas(browser_outer, bg=_WHITE, highlightthickness=0)
        scrollbar = tk.Scrollbar(browser_outer, orient="vertical",
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
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(self._canvas_window, width=e.width))
        canvas.bind_all(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
        self._canvas = canvas

        # ── Filename row ───────────────────────────────────────────────────
        fname_row = tk.Frame(self, bg=_LIGHT, pady=6)
        fname_row.pack(fill="x", padx=12)

        tk.Label(fname_row, text="File name:",
                 bg=_LIGHT, fg=_TEXT,
                 font=("Helvetica", 10, "bold"),
                 width=12, anchor="w").pack(side="left")

        self.filename_var = tk.StringVar(value=default_name)
        fname_entry = tk.Entry(
            fname_row,
            textvariable=self.filename_var,
            font=("Helvetica", 10),
            bg=_WHITE, fg=_TEXT,
            relief="solid", bd=1,
            insertbackground=_GREEN,
        )
        fname_entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(4, 0))
        fname_entry.bind("<Return>", lambda e: self._confirm())

        # ── Bottom action bar ──────────────────────────────────────────────
        bottom = tk.Frame(self, bg=_LIGHT, pady=10)
        bottom.pack(fill="x", padx=12)

        # Extension hint
        ext_label = "PDF (*.pdf)" if self._extension == ".pdf" else "Word (*.docx)"
        tk.Label(bottom, text=f"Type: {ext_label}",
                 bg=_LIGHT, fg=_MUTED,
                 font=("Helvetica", 9)).pack(side="left")

        tk.Button(bottom, text="✖  Cancel",
                  bg=_LIGHT, fg=_TEXT,
                  activebackground=_BORDER,
                  relief="flat", bd=1,
                  font=("Helvetica", 10), padx=18, pady=7,
                  cursor="hand2",
                  command=self._cancel).pack(side="right", padx=(6, 0))

        tk.Button(bottom, text="💾  Save",
                  bg=_GREEN, fg=_WHITE,
                  activebackground=_HOVER, activeforeground=_WHITE,
                  relief="flat", bd=0,
                  font=("Helvetica", 10, "bold"), padx=20, pady=7,
                  cursor="hand2",
                  command=self._confirm).pack(side="right")

    # ── Directory loading ──────────────────────────────────────────────────────

    def _load_dir(self, path: str):
        if not os.path.isdir(path):
            return
        self._current_dir = path
        self.path_label.configure(text=f"  {path}")

        for w in self.file_frame.winfo_children():
            w.destroy()
        self._dir_buttons.clear()

        try:
            entries = sorted(
                os.scandir(path),
                key=lambda e: (not e.is_dir(), e.name.lower()),
            )
        except PermissionError:
            tk.Label(self.file_frame,
                     text="⚠  Permission denied",
                     bg=_WHITE, fg="#C0392B",
                     font=("Helvetica", 10)).pack(padx=16, pady=16)
            return

        for entry in entries:
            if entry.name.startswith("."):
                continue
            if not entry.is_dir():
                continue   # only show folders — user types the filename manually

            row_frame = tk.Frame(self.file_frame, bg=_WHITE, cursor="hand2")
            row_frame.pack(fill="x", padx=4, pady=1)

            icon_lbl = tk.Label(row_frame, text="📁", bg=_WHITE,
                                font=("Segoe UI Emoji", 13),
                                width=3, anchor="center")
            icon_lbl.pack(side="left", padx=(8, 0), pady=5)

            name_lbl = tk.Label(row_frame, text=entry.name, bg=_WHITE,
                                fg=_TEXT, font=("Helvetica", 10), anchor="w")
            name_lbl.pack(side="left", fill="x", expand=True, padx=8)

            for w in (row_frame, icon_lbl, name_lbl):
                w.bind("<Double-Button-1>",
                       lambda e, p=entry.path: self._load_dir(p))
                w.bind("<Button-1>",
                       lambda e, p=entry.path: self._load_dir(p))
                w.bind("<Enter>",
                       lambda e, f=row_frame: f.configure(bg="#E8F4E8"))
                w.bind("<Leave>",
                       lambda e, f=row_frame: f.configure(bg=_WHITE))

        self._canvas.yview_moveto(0)

    # ── Navigation ─────────────────────────────────────────────────────────────

    def _go_up(self):
        parent = os.path.dirname(self._current_dir)
        if parent != self._current_dir:
            self._load_dir(parent)

    # ── Actions ────────────────────────────────────────────────────────────────

    def _confirm(self):
        fname = self.filename_var.get().strip()
        if not fname:
            return

        # Ensure correct extension
        if not fname.lower().endswith(self._extension):
            fname += self._extension

        self.result = os.path.join(self._current_dir, fname)
        self.grab_release()
        self.destroy()

    def _cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()