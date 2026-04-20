"""
app/ui/screens/chatbot_screen.py — Fixed layout, input not hidden behind taskbar
"""

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
]


class ChatbotScreen(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.master = master
        self.current_user = master.current_user
        self.conversation_history = []
        self._build()
        self._add_message("assistant",
            "Hello! I'm your AI assistant for Bingongold Credit. "
            "Ask me anything about your loans, clients, or repayments in plain English.\n\n"
            'Try: "Show me all overdue loans" or "How many clients do we have?"')

    def _navigate(self, screen):
        if screen == "logout":
            self.master.logout()
        else:
            self.master.show_screen(screen)

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        Sidebar(self, "chatbot", self._navigate, self.current_user).grid(
            row=0, column=0, sticky="nsew")

        # Main area — use regular frame with manual layout so input stays visible
        main = ctk.CTkFrame(self, fg_color=COLORS["bg_primary"])
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        self._build_chat_panel(main)
        self._build_suggestions_panel(main)

    def _build_chat_panel(self, parent):
        # Outer container for chat — uses grid with fixed bottom row for input
        chat_outer = ctk.CTkFrame(parent, fg_color="transparent")
        chat_outer.grid(row=0, column=0, sticky="nsew", padx=(24, 8), pady=24)
        chat_outer.columnconfigure(0, weight=1)
        chat_outer.rowconfigure(1, weight=1)  # Messages row expands
        chat_outer.rowconfigure(2, weight=0)  # Input row stays fixed

        # Title
        title_row = ctk.CTkFrame(chat_outer, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ctk.CTkLabel(title_row, text="AI Chatbot",
                     font=FONTS["title"],
                     text_color=COLORS["accent_green_dark"]).pack(side="left")
        ctk.CTkButton(title_row, text="Clear Chat", width=100, height=30,
                      font=FONTS["body_small"],
                      fg_color=COLORS["border"],
                      hover_color=COLORS["bg_input"],
                      text_color=COLORS["text_secondary"],
                      corner_radius=6,
                      command=self._clear_chat).pack(side="right")

        # Messages scrollable area
        self.messages_frame = ctk.CTkScrollableFrame(
            chat_outer,
            fg_color=COLORS["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
            scrollbar_button_color=COLORS["border"])
        self.messages_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        self.messages_frame.columnconfigure(0, weight=1)

        # Input row — FIXED at bottom, never hidden
        input_frame = ctk.CTkFrame(chat_outer, fg_color="transparent", height=52)
        input_frame.grid(row=2, column=0, sticky="ew")
        input_frame.grid_propagate(False)
        input_frame.columnconfigure(0, weight=1)

        self.input_var = ctk.StringVar()
        self.input_entry = ctk.CTkEntry(
            input_frame,
            textvariable=self.input_var,
            placeholder_text="Ask me anything... e.g. 'Show all overdue loans'",
            fg_color=COLORS["bg_card"],
            border_color=COLORS["accent_green"],
            text_color=COLORS["text_primary"],
            font=FONTS["body"],
            corner_radius=10,
            height=48,
            border_width=1,
        )
        self.input_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
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
        self.send_btn.grid(row=0, column=1)

    def _build_suggestions_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"],
                              corner_radius=10, border_width=1,
                              border_color=COLORS["border"])
        panel.grid(row=0, column=1, sticky="nsew", padx=(8, 24), pady=24)
        panel.columnconfigure(0, weight=1)

        ctk.CTkLabel(panel, text="Suggested Questions",
                     font=FONTS["subheading"],
                     text_color=COLORS["accent_green_dark"]).pack(
            anchor="w", padx=16, pady=(16, 8))

        ctk.CTkFrame(panel, fg_color=COLORS["border"],
                     height=1).pack(fill="x", padx=16, pady=(0, 8))

        for query in SUGGESTED_QUERIES:
            ctk.CTkButton(
                panel, text=query, anchor="w", height=38,
                font=FONTS["body_small"],
                fg_color="transparent",
                hover_color=COLORS["bg_input"],
                text_color=COLORS["text_secondary"],
                corner_radius=6,
                command=lambda q=query: self._use_suggestion(q),
            ).pack(fill="x", padx=8, pady=2)

        ctk.CTkFrame(panel, fg_color="transparent").pack(fill="both", expand=True)

    def _add_message(self, role: str, text: str):
        is_user = role == "user"
        bubble_color = COLORS["accent_green"] if is_user else COLORS["bg_input"]
        text_color = "#FFFFFF" if is_user else COLORS["text_primary"]
        align = "e" if is_user else "w"

        wrapper = ctk.CTkFrame(self.messages_frame, fg_color="transparent")
        wrapper.pack(fill="x", padx=12, pady=4)

        time_str = datetime.now().strftime("%H:%M")
        label_text = f"You  {time_str}" if is_user else f"Assistant  {time_str}"
        ctk.CTkLabel(wrapper, text=label_text,
                     font=FONTS["caption"],
                     text_color=COLORS["text_muted"],
                     anchor=align).pack(fill="x")

        bubble = ctk.CTkFrame(wrapper, fg_color=bubble_color, corner_radius=10)
        bubble.pack(anchor=align, pady=(2, 0))
        ctk.CTkLabel(bubble, text=text, font=FONTS["body_small"],
                     text_color=text_color, anchor="w", justify="left",
                     wraplength=480).pack(padx=14, pady=10)

        self.after(100, lambda: self.messages_frame._parent_canvas.yview_moveto(1.0))

    def _use_suggestion(self, query: str):
        self.input_var.set(query)
        self.input_entry.focus()

    def _clear_chat(self):
        for widget in self.messages_frame.winfo_children():
            widget.destroy()
        self.conversation_history = []
        self._add_message("assistant", "Chat cleared. How can I help you?")

    def _send_message(self):
        message = self.input_var.get().strip()
        if not message:
            return
        self._add_message("user", message)
        self.input_var.set("")
        self.send_btn.configure(state="disabled", text="...")
        self.conversation_history.append({"role": "user", "content": message})
        threading.Thread(target=self._get_response,
                         args=(message,), daemon=True).start()

    def _get_response(self, message: str):
        try:
            from app.core.agents.chatbot import Chatbot
            response = Chatbot.respond(message, self.conversation_history[:-1])
            self.conversation_history.append({"role": "assistant", "content": response})
            self.after(0, lambda: self._add_message("assistant", response))
        except Exception as e:
            self.after(0, lambda: self._add_message("assistant", f"Error: {e}"))
        finally:
            self.after(0, lambda: self.send_btn.configure(state="normal", text="Send"))