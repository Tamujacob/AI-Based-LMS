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
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.configure(fg_color=COLORS["bg_primary"])
        self._center_window()

        self.current_user = None
        self.current_screen = None
        self._screens = {}
        self._transition_pending = False

        self.show_screen("login")

    def _center_window(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - WINDOW_WIDTH) // 2
        y = (sh - WINDOW_HEIGHT) // 2
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")

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