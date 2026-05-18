from __future__ import annotations

import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from replyright_qt.api_client import ApiClient
from replyright_qt.styles.theme import STYLESHEET
from replyright_qt.windows.login_window import LoginWindow
from replyright_qt.windows.main_window import MainWindow


def run_app(base_url: str) -> None:
    """Create the QApplication, wire login → main, and block until the user quits."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ReplyRight")
    app.setOrganizationName("ReplyRight")
    app.setStyleSheet(STYLESHEET)

    icon_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "outlook_dashboard", "static", "replyright.ico",
    )
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    client = ApiClient(base_url)
    login_window = LoginWindow(client)
    main_window = MainWindow(client)

    def on_login(user_data: dict) -> None:
        login_window.hide()
        main_window.set_user(user_data)
        main_window.show()
        main_window.load_inbox()

    def on_logout() -> None:
        client.logout()
        main_window.hide()
        login_window.clear()
        login_window.show()

    login_window.logged_in.connect(on_login)
    main_window.logged_out.connect(on_logout)

    login_window.show()
    app.exec()
