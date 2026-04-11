"""
app/ui/components/data_table.py
"""

import customtkinter as ctk
from app.ui.styles.theme import COLORS, FONTS


class DataTable(ctk.CTkFrame):
    def __init__(self, master, columns: list, rows: list = None,
                 on_select=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.columns = columns
        self.rows = rows or []
        self.on_select = on_select
        self.selected_row = None
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self._build_header()
        self._build_body()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=COLORS["bg_input"],
                               corner_radius=8, height=40)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        header.pack_propagate(False)

        inner = ctk.CTkFrame(header, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=8)

        for key, label, width in self.columns:
            ctk.CTkLabel(
                inner,
                text=label.upper(),
                font=FONTS["badge"],
                text_color=COLORS["accent_gold"],
                width=width,
                anchor="w",
            ).pack(side="left", padx=4)

    def _build_body(self):
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_hover"],
        )
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")
        self._render_rows()

    def _render_rows(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        if not self.rows:
            ctk.CTkLabel(
                self.scroll_frame,
                text="No records found.",
                font=FONTS["body"],
                text_color=COLORS["text_muted"],
            ).pack(pady=40)
            return

        for i, row in enumerate(self.rows):
            bg = COLORS["bg_card"] if i % 2 == 0 else COLORS["bg_secondary"]
            row_frame = ctk.CTkFrame(
                self.scroll_frame,
                fg_color=bg,
                corner_radius=6,
                height=38,
            )
            row_frame.pack(fill="x", pady=1)
            row_frame.pack_propagate(False)

            inner = ctk.CTkFrame(row_frame, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=8)

            for key, label, width in self.columns:
                value = str(row.get(key, ""))
                ctk.CTkLabel(
                    inner,
                    text=value,
                    font=FONTS["body_small"],
                    text_color=COLORS["text_primary"],
                    width=width,
                    anchor="w",
                ).pack(side="left", padx=4)

            row_frame.bind("<Button-1>",
                           lambda e, r=row: self._on_row_click(r))
            inner.bind("<Button-1>",
                       lambda e, r=row: self._on_row_click(r))
            for child in inner.winfo_children():
                child.bind("<Button-1>",
                           lambda e, r=row: self._on_row_click(r))

    def _on_row_click(self, row):
        self.selected_row = row
        if self.on_select:
            self.on_select(row)

    def update_rows(self, rows: list):
        self.rows = rows
        self._render_rows()