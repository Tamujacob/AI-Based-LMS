"""
app/ui/components/statement_analysis_widget.py
──────────────────────────────────────────────────────────────
Reusable widget for uploading and analysing financial statements.

Embedded inside the new loan form in loans_screen.py.

Usage:
    widget = StatementAnalysisWidget(parent, on_accept=callback)
    widget.pack(fill="x")

    # on_accept callback receives:
    def callback(principal: float, duration: int, ceiling_result):
        pass   # auto-fills loan form fields
"""

import threading
import customtkinter as ctk
from app.ui.styles.theme import COLORS, FONTS, input_style


class StatementAnalysisWidget(ctk.CTkFrame):
    """
    Statement upload and analysis panel.
    Shows upload button, runs analysis, displays results,
    and provides an Accept Recommendation button.
    """

    def __init__(self, master, on_accept=None, current_user=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_accept    = on_accept
        self.current_user = current_user
        self._result      = None
        self._ceiling     = None
        self._file_path   = None
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)

        # Section header
        ctk.CTkLabel(self, text="Financial Statement Analysis",
                     font=FONTS["subheading"],
                     text_color=COLORS["accent_green_dark"],
                     anchor="w").grid(row=0, column=0, sticky="w", pady=(0, 4))
        ctk.CTkLabel(self,
                     text="Upload a Mobile Money or bank statement PDF for AI-powered loan sizing.",
                     font=FONTS["caption"],
                     text_color=COLORS["text_muted"],
                     anchor="w").grid(row=1, column=0, sticky="w", pady=(0, 8))

        # Upload row
        upload_row = ctk.CTkFrame(self, fg_color="transparent")
        upload_row.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkButton(upload_row, text="Upload Statement",
                      height=36, font=FONTS["button"],
                      fg_color=COLORS["accent_green"],
                      hover_color=COLORS["accent_green_dark"],
                      text_color="#FFFFFF", corner_radius=8,
                      command=self._upload_statement).pack(side="left")

        self.file_label = ctk.CTkLabel(
            upload_row, text="No file selected",
            font=FONTS["caption"], text_color=COLORS["text_muted"])
        self.file_label.pack(side="left", padx=(10, 0))

        # Stated income fallback
        stated_row = ctk.CTkFrame(self, fg_color="transparent")
        stated_row.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        stated_row.columnconfigure(1, weight=1)

        ctk.CTkLabel(stated_row, text="OR  Stated Monthly Income (UGX):",
                     font=FONTS["body_small"],
                     text_color=COLORS["text_secondary"]).grid(
            row=0, column=0, padx=(0, 8))
        self.stated_income_var = ctk.StringVar()
        ctk.CTkEntry(stated_row, textvariable=self.stated_income_var,
                     placeholder_text="e.g. 800000",
                     **input_style()).grid(row=0, column=1, sticky="ew")

        # Analyse button
        ctk.CTkButton(self, text="Analyse & Get Recommendation",
                      height=38, font=FONTS["button"],
                      fg_color=COLORS["accent_green"],
                      hover_color=COLORS["accent_green_dark"],
                      text_color="#FFFFFF", corner_radius=8,
                      command=self._run_analysis).grid(
            row=4, column=0, sticky="ew", pady=(0, 8))

        # Results box
        self.results_box = ctk.CTkTextbox(
            self, height=200,
            fg_color=COLORS["bg_input"],
            text_color=COLORS["text_primary"],
            font=("Courier", 10), wrap="word",
            corner_radius=8, border_width=1,
            border_color=COLORS["border"])
        self.results_box.grid(row=5, column=0, sticky="ew", pady=(0, 8))
        self.results_box.insert("end", "Analysis results will appear here.")
        self.results_box.configure(state="disabled")

        # Accept button (hidden until analysis runs)
        self.accept_btn = ctk.CTkButton(
            self, text="Accept Recommendation — Fill Loan Form",
            height=40, font=FONTS["button"],
            fg_color=COLORS["accent_gold"],
            hover_color=COLORS["accent_gold_dark"],
            text_color=COLORS["text_on_gold"],
            corner_radius=8,
            command=self._accept_recommendation,
            state="disabled")
        self.accept_btn.grid(row=6, column=0, sticky="ew", pady=(0, 4))

    def _upload_statement(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Select Bank or Mobile Money Statement",
            filetypes=[
                ("PDF files",   "*.pdf"),
                ("Images",      "*.png *.jpg *.jpeg"),
                ("All files",   "*.*"),
            ])
        if path:
            self._file_path = path
            import os
            self.file_label.configure(
                text=os.path.basename(path),
                text_color=COLORS["accent_green"])

    def _run_analysis(self):
        self._set_results("Analysing statement... please wait.")
        threading.Thread(target=self._do_analysis, daemon=True).start()

    def _do_analysis(self):
        try:
            from app.core.agents.statement_parser import StatementParser
            from app.core.agents.loan_ceiling_engine import LoanCeilingEngine

            # Get stated income if entered
            stated = 0
            try:
                raw = self.stated_income_var.get().strip().replace(",", "")
                if raw:
                    stated = float(raw)
            except Exception:
                pass

            # Parse statement if uploaded
            parsed = None
            if self._file_path:
                parsed = StatementParser.parse(self._file_path)

            # Run ceiling engine
            ceiling = LoanCeilingEngine.calculate(
                statement_result=parsed,
                stated_income=stated,
            )
            self._ceiling = ceiling

            # Build output text
            lines = []
            if parsed and parsed.source_type != "error":
                lines.append(StatementParser.format_result_summary(parsed))
                lines.append("")
            lines.append(ceiling.as_text())
            output = "\n".join(lines)

            self.after(0, lambda: self._set_results(output))
            self.after(0, lambda: self.accept_btn.configure(state="normal"))

        except Exception as e:
            self.after(0, lambda: self._set_results(f"Analysis error: {e}"))

    def _accept_recommendation(self):
        if not self._ceiling:
            return
        if self.on_accept:
            self.on_accept(
                float(self._ceiling.recommended_ceiling),
                self._ceiling.recommended_duration,
                self._ceiling,
            )

    def _set_results(self, text: str):
        self.results_box.configure(state="normal")
        self.results_box.delete("1.0", "end")
        self.results_box.insert("end", text)
        self.results_box.configure(state="disabled")