"""
main.py
──────────────────────────────────────────────────────────────
Application entry point.

Performance fix: all screen modules and services are imported
in a background thread while the login screen is visible.
This moves the 10-15 second first-load delay to startup
instead of hitting it on the first navigation click.
"""

import threading


def _preload_modules():
    """
    Import all heavy modules in the background while login is showing.
    By the time the user logs in, everything is already loaded.
    """
    try:
        # Services
        from app.core.services.loan_service       import LoanService
        from app.core.services.client_service     import ClientService
        from app.core.services.repayment_service  import RepaymentService
        from app.core.services.auth_service       import AuthService
        from app.core.services.report_service     import ReportService

        # Models
        from app.core.models.loan        import Loan, LoanStatus, LoanType
        from app.core.models.client      import Client
        from app.core.models.repayment   import Repayment
        from app.core.models.collateral  import Collateral
        from app.core.models.audit_log   import AuditLog
        from app.core.models.user        import User

        # UI screens — import the class but don't instantiate
        from app.ui.screens.dashboard_screen   import DashboardScreen
        from app.ui.screens.clients_screen     import ClientsScreen
        from app.ui.screens.loans_screen       import LoansScreen
        from app.ui.screens.repayments_screen  import RepaymentsScreen
        from app.ui.screens.reports_screen     import ReportsScreen
        from app.ui.screens.agent_screen       import AgentScreen
        from app.ui.screens.chatbot_screen     import ChatbotScreen
        from app.ui.screens.users_screen       import UsersScreen
        from app.ui.screens.logs_screen        import LogsScreen
        from app.ui.screens.settings_screen    import SettingsScreen

        # Heavy libraries
        from PIL import Image
        import sqlalchemy
        import bcrypt

        print("[Preload] All modules loaded in background.")

    except Exception as e:
        # Never crash the app due to preload failure
        print(f"[Preload] Warning: {e}")


def main():
    # ── Test DB connection ────────────────────────────────────────────────
    from app.database.connection import test_connection, create_all_tables
    if not test_connection():
        print("ERROR: Could not connect to the database.")
        print("Check your .env file — DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD.")
        return

    create_all_tables()

    # ── Start background preloader immediately ────────────────────────────
    # This runs while the login screen is visible so screens load instantly
    threading.Thread(target=_preload_modules, daemon=True).start()

    # ── Launch the app ────────────────────────────────────────────────────
    from app.ui.app_root import AppRoot
    app = AppRoot()
    app.mainloop()


if __name__ == "__main__":
    main()