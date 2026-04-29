"""
app/ui/app_root.py
──────────────────────────────────────────────────────────────
Root window manager for Bingongold Credit LMS.

KEY IMPROVEMENT — Screen Caching:
  Old behaviour: every navigation destroyed the current screen
  and built a brand new one → lag on every click.

  New behaviour: screens are built ONCE on first visit and
  cached. Returning to a screen just shows the cached widget
  instantly (pack/pack_forget). A refresh() call updates the
  live data in the background without rebuilding the UI.

  Result: navigation feels instant after the first visit.
"""

import customtkinter as ctk
from app.ui.styles.theme import configure_theme, COLORS
from app.config.settings import (
    APP_NAME, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT
)


class AppRoot(ctk.CTk):

    def __init__(self):
        configure_theme()
        super().__init__()

        self.title(APP_NAME)
        self.configure(fg_color=COLORS["bg_primary"])

        self.update_idletasks()
        self._setup_window()

        self.current_user        = None
        self.current_screen_name = None   # string name of active screen
        self._screen_cache       = {}     # name → CTkFrame widget (kept alive)
        self._screen_classes     = {}     # name → class (lazy loaded)
        self._transition_pending = False

        self.show_screen("login")

    # ── Window sizing ──────────────────────────────────────────────────────────

    def _setup_window(self):
        """
        Size the window to fit the actual screen at runtime.
        Handles 768p laptops, 1080p desktops, and 4K monitors correctly.
        """
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        try:
            scale      = self.tk.call("tk", "scaling")
            dpi_factor = scale / 1.3333
        except Exception:
            dpi_factor = 1.0

        # Reserve space for taskbar / dock
        taskbar = 52 if sh <= 768 else (48 if sh <= 900 else 44)

        usable_h = sh - taskbar
        win_w    = min(int(sw * 0.92), 1600)
        win_h    = min(int(usable_h * 0.96), 1050)
        win_w    = max(win_w, WINDOW_MIN_WIDTH)
        win_h    = max(win_h, WINDOW_MIN_HEIGHT)

        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        x = (sw - win_w) // 2
        y = max(0, (usable_h - win_h) // 2)
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")

        print(f"[Window] Screen: {sw}x{sh}  |  "
              f"Window: {win_w}x{win_h}  |  "
              f"DPI scale: {dpi_factor:.2f}")

    # ── Screen switching ───────────────────────────────────────────────────────

    def show_screen(self, screen_name: str, force_rebuild: bool = False):
        """
        Switch to screen_name.

        First visit  → build the screen, cache it, show it.
        Return visit → show cached widget instantly, call refresh()
                       in a background thread to update live data.
        force_rebuild→ destroy all cached screens first (used on logout).
        """
        if self._transition_pending:
            return
        self._transition_pending = True
        self.after(0, lambda: self._do_switch(screen_name, force_rebuild))

    def _do_switch(self, screen_name: str, force_rebuild: bool):
        try:
            # ── Hide current screen without destroying it ──────────────────
            if self.current_screen_name:
                cached = self._screen_cache.get(self.current_screen_name)
                if cached:
                    try:
                        cached.pack_forget()
                    except Exception:
                        pass

            # ── force_rebuild: wipe cache (called on logout) ───────────────
            if force_rebuild:
                for widget in list(self._screen_cache.values()):
                    try:
                        widget.destroy()
                    except Exception:
                        pass
                self._screen_cache.clear()
                self._screen_classes.clear()

            # ── Get or build the target screen ─────────────────────────────
            if screen_name in self._screen_cache:
                # ── CACHED: show instantly ─────────────────────────────────
                widget = self._screen_cache[screen_name]
                try:
                    widget.pack(fill="both", expand=True)
                except Exception:
                    # Widget was somehow destroyed — rebuild it
                    del self._screen_cache[screen_name]
                    widget = self._build_screen(screen_name)

                # Refresh live data in background (non-blocking)
                self._refresh_screen(widget)

            else:
                # ── FIRST VISIT: build and cache ───────────────────────────
                widget = self._build_screen(screen_name)

            self.current_screen_name = screen_name
            self.update_idletasks()

        except Exception as e:
            print(f"[AppRoot] Error loading '{screen_name}': {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._transition_pending = False

    def _build_screen(self, screen_name: str):
        """Instantiate, pack, and cache a screen widget."""
        screen_class = self._get_screen_class(screen_name)
        widget       = screen_class(self)
        widget.pack(fill="both", expand=True)
        self._screen_cache[screen_name] = widget
        return widget

    def _refresh_screen(self, widget):
        """
        Call widget.refresh() in a background thread if the screen
        supports it. This reloads live DB data without rebuilding the UI.
        Screens that should support refresh():
          dashboard, clients, loans, repayments, logs
        """
        if not hasattr(widget, "refresh"):
            return
        import threading
        threading.Thread(
            target=widget.refresh,
            daemon=True,
        ).start()

    # ── Screen class registry (lazy imports) ───────────────────────────────────

    def _get_screen_class(self, name: str):
        """
        Return the screen class for name.
        Classes are imported lazily — only when first needed.
        This speeds up startup (no mass importing at launch).
        """
        if name not in self._screen_classes:
            if name == "login":
                from app.ui.screens.login_screen import LoginScreen
                self._screen_classes["login"] = LoginScreen

            elif name == "dashboard":
                from app.ui.screens.dashboard_screen import DashboardScreen
                self._screen_classes["dashboard"] = DashboardScreen

            elif name == "clients":
                from app.ui.screens.clients_screen import ClientsScreen
                self._screen_classes["clients"] = ClientsScreen

            elif name == "loans":
                from app.ui.screens.loans_screen import LoansScreen
                self._screen_classes["loans"] = LoansScreen

            elif name == "repayments":
                from app.ui.screens.repayments_screen import RepaymentsScreen
                self._screen_classes["repayments"] = RepaymentsScreen

            elif name == "reports":
                from app.ui.screens.reports_screen import ReportsScreen
                self._screen_classes["reports"] = ReportsScreen

            elif name == "agent":
                from app.ui.screens.agent_screen import AgentScreen
                self._screen_classes["agent"] = AgentScreen

            elif name == "chatbot":
                from app.ui.screens.chatbot_screen import ChatbotScreen
                self._screen_classes["chatbot"] = ChatbotScreen

            elif name == "users":
                from app.ui.screens.users_screen import UsersScreen
                self._screen_classes["users"] = UsersScreen

            elif name == "logs":
                from app.ui.screens.logs_screen import LogsScreen
                self._screen_classes["logs"] = LogsScreen

            elif name == "settings":
                from app.ui.screens.settings_screen import SettingsScreen
                self._screen_classes["settings"] = SettingsScreen

            else:
                raise ValueError(f"Unknown screen: '{name}'")

        return self._screen_classes[name]

    # ── Auth ───────────────────────────────────────────────────────────────────

    def login(self, user):
        """
        Called by LoginScreen after successful authentication.
        Destroys the login screen (never cached) and goes to dashboard.
        """
        self.current_user = user

        # Remove login from cache — it must rebuild fresh on next logout
        if "login" in self._screen_cache:
            try:
                self._screen_cache["login"].destroy()
            except Exception:
                pass
            del self._screen_cache["login"]
        if "login" in self._screen_classes:
            del self._screen_classes["login"]

        self.show_screen("dashboard")

    def logout(self):
        """
        Clear session and return to login.
        force_rebuild=True destroys ALL cached screens so the next
        login starts completely fresh (no stale user data visible).
        """
        self.current_user        = None
        self.current_screen_name = None
        self.show_screen("login", force_rebuild=True)