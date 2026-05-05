"""
app/ui/app_root.py
──────────────────────────────────────────────────────────────
Root window manager for Bingongold Credit LMS.

Screen Caching:
  Screens are built ONCE and cached. Navigation shows/hides
  them with pack/pack_forget — no rebuilding.

Smart Refresh:
  refresh() is only called if the screen's data is more than
  REFRESH_INTERVAL seconds old. This prevents the dashboard
  from visually reloading every time you click back to it.
"""

import time
import threading
import customtkinter as ctk
from app.ui.styles.theme import configure_theme, COLORS
from app.config.settings import APP_NAME, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT

# Only refresh a screen's data if it was last refreshed more than this
# many seconds ago. Set lower for more live data, higher for less flicker.
REFRESH_INTERVAL = 30   # seconds


class AppRoot(ctk.CTk):

    def __init__(self):
        configure_theme()
        super().__init__()

        self.title(APP_NAME)
        self.configure(fg_color=COLORS["bg_primary"])
        self.update_idletasks()
        self._setup_window()

        self.current_user        = None
        self.current_screen_name = None
        self._screen_cache       = {}      # name → widget
        self._screen_classes     = {}      # name → class
        self._last_refresh       = {}      # name → timestamp of last refresh
        self._transition_pending = False

        self.after(100, lambda: self.show_screen("login"))

    # ── Window sizing ──────────────────────────────────────────────────────────

    def _setup_window(self):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        try:
            scale      = self.tk.call("tk", "scaling")
            dpi_factor = scale / 1.3333
        except Exception:
            dpi_factor = 1.0

        taskbar  = 52 if sh <= 768 else (48 if sh <= 900 else 44)
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
        if self._transition_pending:
            return
        self._transition_pending = True
        self.after(0, lambda: self._do_switch(screen_name, force_rebuild))

    def _do_switch(self, screen_name: str, force_rebuild: bool):
        try:
            # ── Hide current screen ────────────────────────────────────────
            if self.current_screen_name:
                cached = self._screen_cache.get(self.current_screen_name)
                if cached:
                    try:
                        cached.pack_forget()
                    except Exception:
                        pass

            # ── Wipe cache on logout ───────────────────────────────────────
            if force_rebuild:
                for widget in list(self._screen_cache.values()):
                    try:
                        widget.destroy()
                    except Exception:
                        pass
                self._screen_cache.clear()
                self._screen_classes.clear()
                self._last_refresh.clear()

            # ── Get or build target screen ─────────────────────────────────
            if screen_name in self._screen_cache:
                widget = self._screen_cache[screen_name]
                try:
                    widget.pack(fill="both", expand=True)
                except Exception:
                    del self._screen_cache[screen_name]
                    widget = self._build_screen(screen_name)

                # ── KEY FIX: only refresh if data is stale ─────────────────
                self._maybe_refresh(screen_name, widget)

            else:
                widget = self._build_screen(screen_name)
                # Mark as just refreshed so returning immediately won't refresh again
                self._last_refresh[screen_name] = time.time()

            self.current_screen_name = screen_name
            self.update_idletasks()

        except Exception as e:
            print(f"[AppRoot] Error loading '{screen_name}': {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._transition_pending = False

    def _build_screen(self, screen_name: str):
        """Build, pack, and cache a screen widget."""
        screen_class = self._get_screen_class(screen_name)
        widget       = screen_class(self)
        widget.pack(fill="both", expand=True)
        self._screen_cache[screen_name] = widget
        return widget

    def _maybe_refresh(self, screen_name: str, widget):
        """
        Only call refresh() if:
          1. The screen has a refresh() method
          2. Data is older than REFRESH_INTERVAL seconds
          3. OR this is the dashboard (always show fresh counts)

        This prevents the repayments table from being rebuilt
        every single time you navigate back to the dashboard.
        """
        if not hasattr(widget, "refresh"):
            return

        last = self._last_refresh.get(screen_name, 0)
        age  = time.time() - last

        # Dashboard refreshes if data is older than 30 seconds
        # Other screens refresh if older than 60 seconds
        threshold = REFRESH_INTERVAL if screen_name == "dashboard" else 60

        if age >= threshold:
            self._last_refresh[screen_name] = time.time()
            threading.Thread(target=widget.refresh, daemon=True).start()
        # else: data is fresh — show cached screen instantly, no refresh

    # ── Screen class registry ──────────────────────────────────────────────────

    def _get_screen_class(self, name: str):
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

    # ── Public method for manual refresh (e.g. Refresh button) ────────────────

    def force_refresh(self, screen_name: str = None):
        """
        Force a data refresh on a screen regardless of age.
        Called by the Refresh button on the dashboard.
        """
        name   = screen_name or self.current_screen_name
        widget = self._screen_cache.get(name)
        if widget and hasattr(widget, "refresh"):
            self._last_refresh[name] = 0   # reset timer so refresh runs
            threading.Thread(target=widget.refresh, daemon=True).start()

    # ── Auth ───────────────────────────────────────────────────────────────────

    def login(self, user):
        self.current_user = user

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
        self.current_user        = None
        self.current_screen_name = None
        self.show_screen("login", force_rebuild=True)