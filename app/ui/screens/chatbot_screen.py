"""
app/ui/screens/chatbot_screen.py
──────────────────────────────────────────────────────────────
AI Chatbot screen — powered by Groq API (free).

New in this version:
  - (+) button next to input — uploads a PDF/image statement
  - Statement is parsed by StatementParser and ceiling calculated
  - Results are injected into the chat as a message automatically
  - Falls back to local answers if no Groq key is set
  - Input box anchored above taskbar (fixed height row)

Password fixes (v2):
  - Password entry now actually visible and correctly sized in attachment bar
  - Placeholder updated to "Last 4 digits of loan number (if encrypted)"
  - Retry flow: if wrong password, bar stays open with red error prompt
  - Password field hidden for unencrypted PDFs and images
"""

import os
import threading
import customtkinter as ctk
from datetime import datetime
from app.ui.styles.theme import COLORS, FONTS
from app.ui.components.sidebar import Sidebar

SUGGESTED_QUERIES = [
    "Show me all overdue loans",
    "How many active loans do we have?",
    "What is our total outstanding balance?",
    "Which loans haven't had a payment in 60 days?",
    "How many clients do we have?",
    "Show loans approved this month",
    "What is the total amount collected today?",
    "What is the risk on loan BG-2025-00001?",
    "Which clients have the most loans?",
    "Show me completed loans this year",
]


def _pdf_is_encrypted(path: str) -> bool:
    """
    Returns True if the PDF at *path* is password-protected.
    Uses pdfplumber first, falls back to pypdf.
    Returns False for images and non-PDF files (they never need a password).
    """
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".pdf",):
        return False
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            # pdfplumber raises an exception on encrypted PDFs when no password
            # is given, so reaching this line means it opened fine → not encrypted.
            _ = pdf.pages
        return False
    except Exception:
        pass
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        return reader.is_encrypted
    except Exception:
        return False


class ChatbotScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master               = master
        self.current_user         = master.current_user
        self.conversation_history = []
        self._attached_statement  = None   # path of uploaded statement
        self._statement_result    = None   # parsed StatementResult
        self._file_is_encrypted   = False  # track whether current file needs PW
        self._build()
        self._check_api_status()
        self._add_message(
            "assistant",
            "Hello! I am the Bingongold Credit AI Assistant, powered by Groq.\n\n"
            "I can only answer questions about your loans, clients, and repayments. "
            "I have live access to your database.\n\n"
            'Try: "Show me all overdue loans"  or  '
            '"What is the risk on loan BG-2025-00001?"\n\n'
            "You can also upload a borrower's bank or MoMo statement using the "
            "📎 button to get a loan recommendation."
        )

    def _navigate(self, screen):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    # ── Refresh — called by AppRoot on return visit ───────────────────────────

    def refresh(self):
        """Keep conversation history intact — just recheck API status."""
        threading.Thread(target=self._check_api_status, daemon=True).start()

    # ── Layout ─────────────────────────────────────────────────────────────────

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        Sidebar(self, "chatbot", self._navigate, self.current_user).grid(
            row=0, column=0, sticky="nsew")

        main = ctk.CTkFrame(self, fg_color=COLORS["bg_primary"])
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        self._build_chat_panel(main)
        self._build_suggestions_panel(main)

    # ── Chat panel ─────────────────────────────────────────────────────────────

    def _build_chat_panel(self, parent):
        chat_outer = ctk.CTkFrame(parent, fg_color="transparent")
        chat_outer.grid(row=0, column=0, sticky="nsew", padx=(24, 8), pady=24)
        chat_outer.columnconfigure(0, weight=1)
        chat_outer.rowconfigure(1, weight=1)   # messages expand
        chat_outer.rowconfigure(2, weight=0)   # attachment bar fixed
        chat_outer.rowconfigure(3, weight=0)   # input row fixed

        # ── Title row ──────────────────────────────────────────────────────
        title_row = ctk.CTkFrame(chat_outer, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        title_row.columnconfigure(1, weight=1)

        ctk.CTkLabel(
            title_row, text="AI Chatbot",
            font=FONTS["title"],
            text_color=COLORS["accent_green_dark"],
        ).grid(row=0, column=0, sticky="w")

        self.status_badge = ctk.CTkLabel(
            title_row, text="● checking...",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
        )
        self.status_badge.grid(row=0, column=1, sticky="w", padx=(12, 0))

        ctk.CTkButton(
            title_row, text="Clear Chat",
            width=100, height=30,
            font=FONTS["body_small"],
            fg_color=COLORS["border"],
            hover_color=COLORS["bg_input"],
            text_color=COLORS["text_secondary"],
            corner_radius=6,
            command=self._clear_chat,
        ).grid(row=0, column=2, sticky="e")

        # ── Messages scrollable area ───────────────────────────────────────
        self.messages_frame = ctk.CTkScrollableFrame(
            chat_outer,
            fg_color=COLORS["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
            scrollbar_button_color=COLORS["accent_green"],
            scrollbar_button_hover_color=COLORS["accent_green_dark"],
        )
        self.messages_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 6))
        self.messages_frame.columnconfigure(0, weight=1)

        # ── Attachment bar ─────────────────────────────────────────────────
        # FIX 1: Correct column weights so all widgets actually render.
        # FIX 2: Placeholder text updated to give clear instructions.
        # FIX 4: Password row is shown/hidden based on encryption detection.
        self.attachment_bar = ctk.CTkFrame(
            chat_outer,
            fg_color=COLORS["bg_input"],
            corner_radius=8,
        )
        # Not gridded yet — shown when a file is attached via _show_attachment_bar()
        # Row 0: filename + remove button
        # Row 1: password entry (only shown when file is encrypted)
        self.attachment_bar.columnconfigure(0, weight=1)   # filename label stretches
        self.attachment_bar.columnconfigure(1, weight=0)   # remove button fixed

        self.attachment_label = ctk.CTkLabel(
            self.attachment_bar,
            text="",
            font=FONTS["body_small"],
            text_color=COLORS["accent_green_dark"],
            anchor="w",
        )
        self.attachment_label.grid(row=0, column=0, padx=(12, 4),
                                   pady=(6, 2), sticky="ew")

        ctk.CTkButton(
            self.attachment_bar,
            text="✕ Remove",
            width=80, height=26,
            font=FONTS["caption"],
            fg_color="transparent",
            hover_color=COLORS["border"],
            text_color=COLORS["danger"],
            corner_radius=6,
            command=self._remove_attachment,
        ).grid(row=0, column=1, padx=8, pady=(6, 2))

        # Password row — spans both columns; hidden/shown per _show_password_row()
        self._pw_row = ctk.CTkFrame(
            self.attachment_bar, fg_color="transparent")
        self._pw_row.columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self._pw_row,
            text="🔒 Password:",
            font=FONTS["body_small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).grid(row=0, column=0, padx=(12, 6), pady=(0, 6))

        self.statement_password_var = ctk.StringVar()
        self.attachment_password_entry = ctk.CTkEntry(
            self._pw_row,
            textvariable=self.statement_password_var,
            # FIX 2: Clear instruction matching the business rule
            placeholder_text="Last 4 digits of loan number (if encrypted)",
            show="•",
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            font=FONTS["body_small"],
            corner_radius=8,
            height=32,
            border_width=1,
        )
        self.attachment_password_entry.grid(
            row=0, column=1, padx=(0, 12), pady=(0, 6), sticky="ew")

        # Error label shown on wrong password (FIX 3)
        self._pw_error_label = ctk.CTkLabel(
            self.attachment_bar,
            text="",
            font=FONTS["caption"],
            text_color=COLORS["danger"],
            anchor="w",
        )
        # Not gridded until needed

        # ── Input row — fixed height, never behind taskbar ─────────────────
        input_frame = ctk.CTkFrame(
            chat_outer, fg_color="transparent", height=52)
        input_frame.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        input_frame.grid_propagate(False)
        input_frame.columnconfigure(1, weight=1)

        # (+) Attach statement button
        self.attach_btn = ctk.CTkButton(
            input_frame,
            text="📎",
            width=48, height=48,
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["accent_green"],
            text_color=COLORS["accent_green"],
            font=("Helvetica", 18),
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
            command=self._attach_statement,
        )
        self.attach_btn.grid(row=0, column=0, padx=(0, 6))

        self.input_var = ctk.StringVar()
        self.input_entry = ctk.CTkEntry(
            input_frame,
            textvariable=self.input_var,
            placeholder_text="Ask about loans, clients, or upload a statement with 📎 ...",
            fg_color=COLORS["bg_card"],
            border_color=COLORS["accent_green"],
            text_color=COLORS["text_primary"],
            font=FONTS["body"],
            corner_radius=10,
            height=48,
            border_width=1,
        )
        self.input_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6))
        self.input_entry.bind("<Return>", lambda e: self._send_message())

        self.send_btn = ctk.CTkButton(
            input_frame,
            text="Send",
            width=90, height=48,
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["accent_green_dark"],
            text_color="#FFFFFF",
            font=FONTS["button"],
            corner_radius=10,
            command=self._send_message,
        )
        self.send_btn.grid(row=0, column=2)

    # ── Suggestions panel ──────────────────────────────────────────────────────

    def _build_suggestions_panel(self, parent):
        panel = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
        )
        panel.grid(row=0, column=1, sticky="nsew", padx=(8, 24), pady=24)
        panel.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            panel, text="Suggested Questions",
            font=FONTS["subheading"],
            text_color=COLORS["accent_green_dark"],
        ).pack(anchor="w", padx=16, pady=(16, 6))

        ctk.CTkFrame(
            panel, fg_color=COLORS["border"], height=1,
        ).pack(fill="x", padx=16, pady=(0, 6))

        for query in SUGGESTED_QUERIES:
            ctk.CTkButton(
                panel, text=query,
                anchor="w", height=36,
                font=FONTS["body_small"],
                fg_color="transparent",
                hover_color=COLORS["bg_input"],
                text_color=COLORS["text_secondary"],
                corner_radius=6,
                command=lambda q=query: self._use_suggestion(q),
            ).pack(fill="x", padx=8, pady=2)

        ctk.CTkFrame(panel, fg_color="transparent").pack(
            fill="both", expand=True)

        # Statement upload hint
        ctk.CTkFrame(
            panel, fg_color=COLORS["border"], height=1,
        ).pack(fill="x", padx=16, pady=(0, 4))

        ctk.CTkButton(
            panel,
            text="📎  Analyse Statement",
            height=36,
            font=FONTS["body_small"],
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["accent_green_dark"],
            text_color="#FFFFFF",
            corner_radius=8,
            command=self._attach_statement,
        ).pack(fill="x", padx=8, pady=(0, 4))

        ctk.CTkLabel(
            panel,
            text="Upload a MoMo or bank\nstatement for a loan\nrecommendation.",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            justify="center",
        ).pack(pady=(0, 8))

        ctk.CTkLabel(
            panel,
            text="Powered by Groq (free)\nFalls back to local mode\nif no API key is set.",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            justify="center",
        ).pack(pady=(0, 12))

    # ── Attachment bar helpers ─────────────────────────────────────────────────

    def _show_attachment_bar(self, filename: str, encrypted: bool):
        """
        Grid the attachment bar into row 2 of chat_outer.
        Shows the password row only when *encrypted* is True (FIX 4).
        Clears any previous error label.
        """
        self.attachment_label.configure(
            text=f"📎  {filename}  — click Send to analyse")

        # Show/hide password row based on encryption state
        if encrypted:
            self._pw_row.grid(row=1, column=0, columnspan=2, sticky="ew")
            self.attachment_password_entry.focus()
        else:
            self._pw_row.grid_forget()
            self.statement_password_var.set("")

        # Clear any old error
        self._pw_error_label.grid_forget()
        self._pw_error_label.configure(text="")

        self.attachment_bar.grid(row=2, column=0, sticky="ew",
                                 pady=(0, 4),
                                 in_=self.attachment_bar.master)

    def _show_password_error(self, message: str):
        """
        FIX 3: Show a red error message inside the attachment bar and
        re-enable the Send button so the user can retry with the correct password.
        The password field is highlighted red.
        """
        self._pw_error_label.configure(text=f"⚠  {message}")
        self._pw_error_label.grid(row=2, column=0, columnspan=2,
                                  padx=12, pady=(0, 6), sticky="ew")

        # Highlight the password entry border red to draw attention
        self.attachment_password_entry.configure(
            border_color=COLORS["danger"])

        # Re-enable send so the user can retry
        self.send_btn.configure(state="normal", text="Send")
        self.attachment_password_entry.focus()

    def _clear_password_error(self):
        """Remove error styling before a retry attempt."""
        self._pw_error_label.grid_forget()
        self._pw_error_label.configure(text="")
        self.attachment_password_entry.configure(
            border_color=COLORS["border"])

    # ── Statement attachment ───────────────────────────────────────────────────

    def _attach_statement(self):
        """Open file picker, detect encryption, show attachment bar."""
        from app.ui.components.save_dialog import OpenDialog

        filetypes = [
            ("Supported files", "*.pdf *.png *.jpg *.jpeg *.bmp *.tiff"),
            ("PDF files", "*.pdf"),
            ("Image files", "*.png *.jpg *.jpeg *.bmp *.tiff"),
            ("All files", "*.*"),
        ]

        dialog = OpenDialog(self.master, title="Select Bank or MoMo Statement",
                            filetypes=filetypes)
        self.master.wait_window(dialog)

        path = dialog.result
        if not path:
            return

        self._attached_statement = path
        filename = os.path.basename(path)

        # FIX 4: Detect encryption and only show password row when needed
        self._file_is_encrypted = _pdf_is_encrypted(path)
        self._show_attachment_bar(filename, self._file_is_encrypted)

        # Change attach button to green to confirm
        self.attach_btn.configure(
            fg_color=COLORS["accent_green"],
            text_color="#FFFFFF",
        )

        self.input_var.set(
            "Analyse this statement and tell me how much this borrower can borrow.")
        self.input_entry.focus()

    def _remove_attachment(self):
        """Remove the attached statement and reset the bar."""
        self._attached_statement  = None
        self._statement_result    = None
        self._file_is_encrypted   = False
        self.statement_password_var.set("")
        self._pw_error_label.configure(text="")
        self._pw_error_label.grid_forget()
        self.attachment_bar.grid_forget()
        self.attach_btn.configure(
            fg_color=COLORS["bg_input"],
            text_color=COLORS["accent_green"],
        )
        self.input_var.set("")

    def _parse_statement_and_respond(self, message: str):
        path = self._attached_statement
        try:
            self.after(0, lambda: self._add_system_note(
                f"Analysing statement: {os.path.basename(path)}..."))

            from app.core.agents.statement_parser import StatementParser
            pw = self.statement_password_var.get().strip()
            result = StatementParser.parse(path, password=pw if pw else None)
            self._statement_result = result

            # ── FIX 3: Detect wrong-password error and trigger retry flow ──
            if result.statement_type == "unknown" or not result.transactions:
                warning_text = "; ".join(result.parse_warnings).lower()
                is_pw_error  = any(kw in warning_text for kw in [
                    "password", "encrypted", "decrypt", "incorrect"])
                is_no_text   = "no text extracted" in warning_text

                if (is_pw_error or is_no_text) and self._file_is_encrypted:
                    # Wrong or missing password — keep bar open, show error
                    self.after(0, lambda: self._show_password_error(
                        "Wrong password. Enter the last 4 digits of the loan number and try again."
                    ))
                    return  # send_btn already re-enabled inside _show_password_error

                # Unreadable for a different reason — normal error message
                error_msg = "; ".join(result.parse_warnings)
                self.after(0, lambda: self._add_message(
                    "assistant",
                    f"I could not read that file.\n\n{error_msg}\n\n"
                    "Please make sure the file is a readable PDF or clear image."
                ))
                return

            # ── Clear any previous password error styling on success ───────
            self.after(0, self._clear_password_error)

            # ── Render statement result card ───────────────────────────────
            from app.core.agents.loan_ceiling_engine import LoanCeilingEngine
            ceiling = LoanCeilingEngine.calculate(statement_result=result)

            def show_card():
                from app.ui.components.statement_result_card import StatementResultCard
                card = StatementResultCard(
                    parent    = self.messages_frame,
                    result    = result,
                    ceiling   = ceiling,
                    on_accept = self._on_accept_scenario,
                )
                card.pack(fill="x", padx=12, pady=6)
                self._scroll_to_bottom()

            self.after(0, show_card)

            # ── Inject statement context into conversation history ──────────
            ceiling_text      = ceiling.as_text() if ceiling else "N/A"
            statement_context = (
                f"[STATEMENT CONTEXT — available for all follow-up questions]\n"
                f"A financial statement has been uploaded and analysed.\n\n"
                f"{result.as_text()}\n\n"
                f"LOAN CEILING SCENARIOS:\n{ceiling_text}\n"
                f"[END STATEMENT CONTEXT]"
            )

            self.conversation_history = [
                msg for msg in self.conversation_history
                if not (msg["role"] == "system"
                        and "[STATEMENT CONTEXT" in msg.get("content", ""))
            ]
            self.conversation_history.insert(0, {
                "role":    "system",
                "content": statement_context,
            })

            # ── Get AI response ────────────────────────────────────────────
            from app.core.agents.ai_core import AICore
            response = AICore.chat(
                message=message,
                history=self.conversation_history[:-1],
            )
            self.conversation_history.append(
                {"role": "assistant", "content": response})
            self.after(0, lambda: self._add_message("assistant", response))
            self.after(0, self._remove_attachment)

        except Exception as e:
            self.after(0, lambda: self._add_message(
                "assistant",
                f"An error occurred while analysing the statement:\n{e}"
            ))
        finally:
            self.after(0, lambda: self.send_btn.configure(
                state="normal", text="Send"))

    def _on_accept_scenario(self, scenario_name: str,
                             principal: float, months: int):
        """
        Called when the user clicks Accept on a loan scenario card.
        Navigates to the loans screen with the values pre-filled.
        """
        result = self._statement_result
        client = result.client_name if result else ""
        nin    = result.nin         if result else ""

        self._add_message(
            "assistant",
            f"Scenario accepted: {scenario_name.title()} — "
            f"UGX {int(principal):,} over {months} months.\n\n"
            f"Opening the loan form now..."
        )

        if hasattr(self.master, "pre_fill_loan"):
            self.master.pre_fill_loan(
                principal   = principal,
                months      = months,
                client_name = client,
                nin         = nin,
            )
            self.master.show_screen("loans")

    def _clear_statement_context(self):
        """Remove the injected statement system message from history."""
        self.conversation_history = [
            msg for msg in self.conversation_history
            if not (msg["role"] == "system"
                    and "[STATEMENT CONTEXT" in msg.get("content", ""))
        ]
        self._statement_result = None

    # ── Message rendering ──────────────────────────────────────────────────────

    def _add_message(self, role: str, text: str):
        is_user      = (role == "user")
        bubble_color = COLORS["accent_green"] if is_user else COLORS["bg_input"]
        text_color   = "#FFFFFF"              if is_user else COLORS["text_primary"]
        align        = "e"                    if is_user else "w"

        wrapper = ctk.CTkFrame(self.messages_frame, fg_color="transparent")
        wrapper.pack(fill="x", padx=12, pady=4)

        time_str   = datetime.now().strftime("%H:%M")
        label_text = f"You  {time_str}" if is_user else f"Assistant  {time_str}"

        ctk.CTkLabel(
            wrapper, text=label_text,
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor=align,
        ).pack(fill="x")

        bubble = ctk.CTkFrame(wrapper, fg_color=bubble_color, corner_radius=10)
        bubble.pack(anchor=align, pady=(2, 0), fill="x")

        txt = ctk.CTkTextbox(
            bubble,
            width=1,
            height=max(100, min(260, 20 + 20 * (text.count('\n') + len(text) // 70))),
            fg_color=bubble_color,
            text_color=text_color,
            font=FONTS["body_small"],
            wrap="word",
            corner_radius=8,
            border_width=0,
        )
        txt.pack(fill="x", padx=10, pady=10)
        txt.insert("0.0", text)
        txt.configure(state="disabled")

        self._scroll_to_bottom()

    def _add_system_note(self, text: str):
        """Grey system note — for parsing progress and summaries."""
        wrapper = ctk.CTkFrame(self.messages_frame, fg_color="transparent")
        wrapper.pack(fill="x", padx=12, pady=2)

        note = ctk.CTkFrame(
            wrapper,
            fg_color=COLORS["bg_card"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"],
        )
        note.pack(fill="x")

        ctk.CTkLabel(
            note, text=text,
            font=("Courier", 10),
            text_color=COLORS["text_secondary"],
            anchor="w", justify="left",
            wraplength=600,
        ).pack(padx=12, pady=8)

        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        self.after(
            100,
            lambda: self.messages_frame._parent_canvas.yview_moveto(1.0),
        )

    # ── Actions ────────────────────────────────────────────────────────────────

    def _use_suggestion(self, query: str):
        self.input_var.set(query)
        self.input_entry.focus()

    def _clear_chat(self):
        for widget in self.messages_frame.winfo_children():
            widget.destroy()
        self.conversation_history = []
        self._remove_attachment()
        self._add_message(
            "assistant",
            "Chat cleared. How can I help you?"
        )

    def _send_message(self):
        message = self.input_var.get().strip()
        if not message:
            return

        # FIX 3: Clear password error styling on each new send attempt
        self._clear_password_error()

        self._add_message("user", message)
        self.input_var.set("")
        self.send_btn.configure(state="disabled", text="...")
        self.conversation_history.append({"role": "user", "content": message})

        if self._attached_statement:
            threading.Thread(
                target=self._parse_statement_and_respond,
                args=(message,),
                daemon=True,
            ).start()
        else:
            threading.Thread(
                target=self._get_response,
                args=(message,),
                daemon=True,
            ).start()

    def _get_response(self, message: str):
        try:
            from app.core.agents.ai_core import AICore
            response = AICore.chat(
                message=message,
                history=self.conversation_history[:-1],
            )
            self.conversation_history.append(
                {"role": "assistant", "content": response})
            self.after(0, lambda: self._add_message("assistant", response))
        except Exception as e:
            self.after(0, lambda: self._add_message(
                "assistant",
                f"Something went wrong: {e}\n\nPlease try again."
            ))
        finally:
            self.after(0, lambda: self.send_btn.configure(
                state="normal", text="Send"))

    # ── API status ─────────────────────────────────────────────────────────────

    def _check_api_status(self):
        def check():
            try:
                from app.core.agents.ai_core import AICore
                status = AICore.check_groq_status()
                if status == "online":
                    self.after(0, lambda: self.status_badge.configure(
                        text="● Online  (Groq — llama-3.3-70b)",
                        text_color=COLORS["accent_green"],
                    ))
                else:
                    self.after(0, lambda: self.status_badge.configure(
                        text="● Offline  (local mode — add GROQ_API_KEY to .env)",
                        text_color=COLORS["warning"],
                    ))
            except Exception:
                self.after(0, lambda: self.status_badge.configure(
                    text="● Offline  (local mode)",
                    text_color=COLORS["warning"],
                ))
        threading.Thread(target=check, daemon=True).start()