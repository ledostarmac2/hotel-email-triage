from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from replyright_qt.api_client import ApiClient, ApiWorker


class LoginWindow(QWidget):
    """Full-screen login form. Emits logged_in(user_dict) on success."""

    logged_in = Signal(dict)

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self._client = client
        self._worker: ApiWorker | None = None
        self.setObjectName("login-root")
        self.setWindowTitle("ReplyRight — Sign In")
        self.setMinimumSize(480, 360)
        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.setContentsMargins(0, 0, 0, 0)

        card = QWidget()
        card.setObjectName("login-card")
        card.setFixedWidth(380)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 36, 36, 36)
        card_layout.setSpacing(14)

        title = QLabel("ReplyRight")
        title.setObjectName("login-title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("Hotel email triage")
        subtitle.setObjectName("login-subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._email_field = QLineEdit()
        self._email_field.setObjectName("login-field")
        self._email_field.setPlaceholderText("Email address")
        self._email_field.returnPressed.connect(self._on_submit)

        self._password_field = QLineEdit()
        self._password_field.setObjectName("login-field")
        self._password_field.setPlaceholderText("Password")
        self._password_field.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_field.returnPressed.connect(self._on_submit)

        self._submit_btn = QPushButton("Sign in")
        self._submit_btn.setObjectName("primary-btn")
        self._submit_btn.setFixedHeight(40)
        self._submit_btn.clicked.connect(self._on_submit)

        self._error_label = QLabel("")
        self._error_label.setObjectName("error-label")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setWordWrap(True)
        self._error_label.hide()

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(8)
        card_layout.addWidget(QLabel("Email"))
        card_layout.addWidget(self._email_field)
        card_layout.addWidget(QLabel("Password"))
        card_layout.addWidget(self._password_field)
        card_layout.addSpacing(4)
        card_layout.addWidget(self._submit_btn)
        card_layout.addWidget(self._error_label)

        h_wrap = QHBoxLayout()
        h_wrap.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        h_wrap.addWidget(card)
        h_wrap.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        root.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        root.addLayout(h_wrap)
        root.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _on_submit(self) -> None:
        email = self._email_field.text().strip()
        password = self._password_field.text()
        if not email or not password:
            self._show_error("Please enter your email and password.")
            return
        self._set_loading(True)
        self._error_label.hide()
        self._worker = ApiWorker(self._client.login, email, password)
        self._worker.success.connect(self._on_login_success)
        self._worker.failure.connect(self._on_login_failure)
        self._worker.start()

    def _on_login_success(self, user_data: dict) -> None:
        self._set_loading(False)
        self.logged_in.emit(user_data)

    def _on_login_failure(self, message: str) -> None:
        self._set_loading(False)
        self._show_error(message or "Sign-in failed. Check your credentials.")

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _set_loading(self, loading: bool) -> None:
        self._submit_btn.setEnabled(not loading)
        self._submit_btn.setText("Signing in…" if loading else "Sign in")
        self._email_field.setEnabled(not loading)
        self._password_field.setEnabled(not loading)

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()

    def clear(self) -> None:
        self._email_field.clear()
        self._password_field.clear()
        self._error_label.hide()
        self._set_loading(False)
