"""
app/ui/app_root.py — Updated with users and logs screens
"""

import customtkinter as ctk
from app.ui.styles.theme import configure_theme, COLORS
from app.config.settings import APP_NAME, WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT


class AppRoot(ctk.CTk):

    def __init__(self):
        configure_theme()
        super().__init__()

        self.title(APP_NAME)
        self.configure(fg_color=COLORS["bg_primary"])

        # Must call update_idletasks before reading screen dimensions
        self.update_idletasks()
        self._setup_window()

        self.current_user = None
        self.current_screen = None
        self._screens = {}
        self._transition_pending = False

        self.show_screen("login")

    def _setup_window(self):
        """
        Detect actual screen size at runtime and size the window to fit.
        Works correctly on 768p laptops, 1080p desktops, and 4K monitors.
        """
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        # Detect DPI scaling (HiDPI / retina screens)
        try:
            scale = self.tk.call("tk", "scaling")
            # Typical base scaling is 1.33 at 96dpi; anything above means HiDPI
            dpi_factor = scale / 1.3333
        except Exception:
            dpi_factor = 1.0

        # Taskbar / dock reserve — varies by OS and screen height
        if sh <= 768:
            taskbar = 52   # small laptop, taskbar takes more % of screen
        elif sh <= 900:
            taskbar = 48
        else:
            taskbar = 44

        usable_w = sw
        usable_h = sh - taskbar

        # Window occupies 92% of usable space, capped at comfortable maximums
        win_w = min(int(usable_w * 0.92), 1600)
        win_h = min(int(usable_h * 0.96), 1050)

        # Never go below minimum usable size
        win_w = max(win_w, WINDOW_MIN_WIDTH)
        win_h = max(win_h, WINDOW_MIN_HEIGHT)

        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.geometry(f"{win_w}x{win_h}")

        # Centre on screen
        x = (sw - win_w) // 2
        y = max(0, (usable_h - win_h) // 2)
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")

        # Print detected config to console for debugging
        print(f"[Window] Screen: {sw}x{sh}  |  "
            f"Window: {win_w}x{win_h}  |  "
            f"DPI scale: {dpi_factor:.2f}")

    def show_screen(self, screen_name: str, **kwargs):
        if self._transition_pending:
            return
        self._transition_pending = True

        def _do_switch():
            if self.current_screen is not None:
                try:
                    self.current_screen.destroy()
                except Exception:
                    pass
                self.current_screen = None
            try:
                screen_class = self._get_screen_class(screen_name)
                self.current_screen = screen_class(self, **kwargs)
                self.current_screen.pack(fill="both", expand=True)
                self.update()
                self.update_idletasks()
            except Exception as e:
                print(f"[AppRoot] Error loading '{screen_name}': {e}")
                import traceback; traceback.print_exc()
            finally:
                self._transition_pending = False
                self.after(50, self.update)

        self.after(0, _do_switch)

    def _get_screen_class(self, name: str):
        if name not in self._screens:
            if name == "login":
                from app.ui.screens.login_screen import LoginScreen
                self._screens["login"] = LoginScreen
            elif name == "dashboard":
                from app.ui.screens.dashboard_screen import DashboardScreen
                self._screens["dashboard"] = DashboardScreen
            elif name == "clients":
                from app.ui.screens.clients_screen import ClientsScreen
                self._screens["clients"] = ClientsScreen
            elif name == "loans":
                from app.ui.screens.loans_screen import LoansScreen
                self._screens["loans"] = LoansScreen
            elif name == "repayments":
                from app.ui.screens.repayments_screen import RepaymentsScreen
                self._screens["repayments"] = RepaymentsScreen
            elif name == "reports":
                from app.ui.screens.reports_screen import ReportsScreen
                self._screens["reports"] = ReportsScreen
            elif name == "agent":
                from app.ui.screens.agent_screen import AgentScreen
                self._screens["agent"] = AgentScreen
            elif name == "chatbot":
                from app.ui.screens.chatbot_screen import ChatbotScreen
                self._screens["chatbot"] = ChatbotScreen
            elif name == "users":
                from app.ui.screens.users_screen import UsersScreen
                self._screens["users"] = UsersScreen
            elif name == "logs":
                from app.ui.screens.logs_screen import LogsScreen
                self._screens["logs"] = LogsScreen
            elif name == "settings":
                from app.ui.screens.settings_screen import SettingsScreen
                self._screens["settings"] = SettingsScreen
            else:
                raise ValueError(f"Unknown screen: {name}")
        return self._screens[name]

    def login(self, user):
        self.current_user = user
        self._screens = {}
        self.show_screen("dashboard")

    def logout(self):
        self.current_user = None
        self._screens = {}
        self.show_screen("login")