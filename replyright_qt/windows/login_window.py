from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from replyright_core.models.user_models import Session
from replyright_qt.workers import AuthWorker, _run_in_thread


class LoginWindow(QDialog):
    """Native login dialog wired to AuthServiceProtocol (Supabase)."""

    login_successful = Signal(object)   # emits Session

    def __init__(self, auth_service=None, parent=None) -> None:
        super().__init__(parent)
        self._auth = auth_service
        self._threads: list = []

        self.setWindowTitle("ReplyRight — Sign In")
        self.setFixedSize(420, 320)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(36, 36, 36, 36)

        title = QLabel("Sign in to ReplyRight")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 6px;")
        layout.addWidget(title)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email address")
        self.email_input.setStyleSheet("padding: 8px; font-size: 14px;")
        layout.addWidget(self.email_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setStyleSheet("padding: 8px; font-size: 14px;")
        self.password_input.returnPressed.connect(self._handle_login)
        layout.addWidget(self.password_input)

        self.login_button = QPushButton("Sign In")
        self.login_button.clicked.connect(self._handle_login)
        self.login_button.setStyleSheet(
            "padding: 10px; font-weight: bold; font-size: 14px;"
            "background-color: #5b6af0; color: white; border-radius: 5px;"
        )
        layout.addWidget(self.login_button)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 12px; color: #ef4444;")
        layout.addWidget(self.status_label)

    def _set_busy(self, busy: bool) -> None:
        self.login_button.setEnabled(not busy)
        self.email_input.setEnabled(not busy)
        self.password_input.setEnabled(not busy)
        self.login_button.setText("Signing in…" if busy else "Sign In")
        if busy:
            self.status_label.setText("")

    def _handle_login(self) -> None:
        email = self.email_input.text().strip()
        password = self.password_input.text()

        if not email or not password:
            self.status_label.setText("Please enter your email and password.")
            return

        # No auth service injected — accept any non-empty credentials (dev/test mode)
        if self._auth is None:
            self.login_successful.emit(None)
            return

        self._set_busy(True)
        worker = AuthWorker(self._auth, email, password)
        worker.finished.connect(self._on_auth_finished)
        worker.error.connect(self._on_auth_error)
        _run_in_thread(worker, self._threads)

    def _on_auth_finished(self, session: Session | None) -> None:
        self._set_busy(False)
        if session is None:
            self.status_label.setText("Invalid email or password. Please try again.")
            return
        self.login_successful.emit(session)

    def _on_auth_error(self, message: str) -> None:
        self._set_busy(False)
        self.status_label.setText(f"Sign-in error: {message}")
