from __future__ import annotations

import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyleFactory

from replyright_qt.api_client import ApiClient, ApiWorker
from replyright_qt.styles.theme import STYLESHEET
from replyright_qt.windows.credentials_setup_window import CredentialsSetupWindow
from replyright_qt.windows.login_window import LoginWindow
from replyright_qt.windows.main_window import MainWindow
from replyright_qt.windows.reset_password_window import ResetPasswordWindow
from replyright_qt.windows.setup_window import SetupWindow


def run_app(base_url: str) -> None:
    """Create the QApplication, run the first-run flow if needed, then show the main UI."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ReplyRight")
    app.setOrganizationName("ReplyRight")
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setStyleSheet(STYLESHEET)

    icon_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "outlook_dashboard", "static", "replyright.ico",
    )
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    client = ApiClient(base_url)

    credentials_window = CredentialsSetupWindow(client)
    setup_window = SetupWindow(client)
    login_window = LoginWindow(client)
    reset_password_window = ResetPasswordWindow(client)
    main_window = MainWindow(client)

    # ── Transition helpers ─────────────────────────────────────────────────────

    def _hide_all() -> None:
        for w in (credentials_window, setup_window, login_window, reset_password_window, main_window):
            w.hide()

    def _show_login() -> None:
        _hide_all()
        login_window.clear()
        login_window.show()

    def _show_main(user_data: dict) -> None:
        _hide_all()
        main_window.set_user(user_data)
        main_window.show()
        main_window.load_inbox()

    def _on_logout() -> None:
        client.logout()
        _route_startup()

    # ── Startup routing ────────────────────────────────────────────────────────

    def _route_startup() -> None:
        """Check startup state and show the appropriate first window."""
        _hide_all()
        worker = ApiWorker(client.get_startup_state)
        worker.success.connect(_on_startup_state)
        worker.failure.connect(_on_startup_state_error)
        worker.start()
        app._startup_worker = worker  # keep reference alive

    def _on_startup_state(data: dict) -> None:
        state = data.get("state", "login")
        if state == "credentials_setup":
            credentials_window.show()
        elif state == "admin_setup":
            setup_window.show()
        else:
            _show_login()

    def _on_startup_state_error(_: str) -> None:
        # Server may not support startup-state yet — fall through to login
        _show_login()

    # ── Signal wiring ──────────────────────────────────────────────────────────

    # After credentials saved, re-check state (may need admin setup next)
    credentials_window.setup_complete.connect(_route_startup)

    # After admin created, the result includes user data → go straight to main
    setup_window.setup_complete.connect(_show_main)

    # Normal login → main
    login_window.logged_in.connect(_show_main)

    # Forgot password → show reset screen; reset screen back → show login
    login_window.forgot_password_requested.connect(lambda: (_hide_all(), reset_password_window.clear(), reset_password_window.show()))
    reset_password_window.back_to_login.connect(_show_login)

    # Logout → back through startup routing
    main_window.logged_out.connect(_on_logout)

    # ── Launch ─────────────────────────────────────────────────────────────────

    _route_startup()
    app.exec()
