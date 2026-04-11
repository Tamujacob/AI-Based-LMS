"""
app/ui/app_root.py
─────────────────────────────────────────────
Root Tkinter window. Manages screen switching
and holds the currently logged-in user session.
"""

import customtkinter as ctk
from app.ui.styles.theme import configure_theme, COLORS, FONTS
from app.config.settings import APP_NAME, WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT


class AppRoot(ctk.CTk):
    """Main application window with screen management."""

    def __init__(self):
        configure_theme()
        super().__init__()

        # ── Window Setup ───────────────────────────────────────────────────
        self.title(APP_NAME)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.configure(fg_color=COLORS["bg_primary"])

        # Center window on screen
        self._center_window()

        # ── Session State ──────────────────────────────────────────────────
        self.current_user = None   # Set after successful login
        self.current_screen = None

        # ── Screen Registry ────────────────────────────────────────────────
        # Screens are imported lazily to avoid circular imports
        self._screens = {}

        # ── Start with Login ───────────────────────────────────────────────
        self.show_screen("login")

    def _center_window(self):
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - WINDOW_WIDTH) // 2
        y = (screen_h - WINDOW_HEIGHT) // 2
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")

    def show_screen(self, screen_name: str, **kwargs):
        """Switch to the named screen, destroying the current one."""
        # Destroy current screen if any
        if self.current_screen is not None:
            self.current_screen.destroy()
            self.current_screen = None

        # Lazy-import and instantiate the screen
        screen_class = self._get_screen_class(screen_name)
        self.current_screen = screen_class(self, **kwargs)
        self.current_screen.pack(fill="both", expand=True)

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
            elif name == "settings":
                from app.ui.screens.settings_screen import SettingsScreen
                self._screens["settings"] = SettingsScreen
            else:
                raise ValueError(f"Unknown screen: {name}")
        return self._screens[name]

    def login(self, user):
        """Called by LoginScreen after successful authentication."""
        self.current_user = user
        self.show_screen("dashboard")

    def logout(self):
        """Clear session and return to login screen."""
        self.current_user = None
        self.show_screen("login")