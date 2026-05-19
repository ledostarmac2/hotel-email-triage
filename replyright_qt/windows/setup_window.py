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


class SetupWindow(QWidget):
    """First-run window to create the initial admin account.

    Emits setup_complete(user_dict) on success. The caller should then
    transition directly to the main window (the admin is already logged in).
    """

    setup_complete = Signal(dict)

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self._client = client
        self._worker: ApiWorker | None = None
        self.setObjectName("login-root")
        self.setWindowTitle("ReplyRight — Create Admin Account")
        self.setMinimumSize(480, 400)
        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.setContentsMargins(0, 0, 0, 0)

        card = QWidget()
        card.setObjectName("login-card")
        card.setFixedWidth(380)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(14)

        title = QLabel("Create Admin Account")
        title.setObjectName("login-title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel(
            "No admin account exists yet.\n"
            "Create the first admin to start using ReplyRight."
        )
        subtitle.setObjectName("login-subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)

        self._email_field = QLineEdit()
        self._email_field.setObjectName("login-field")
        self._email_field.setPlaceholderText("Admin email address")
        self._email_field.returnPressed.connect(self._on_submit)

        self._password_field = QLineEdit()
        self._password_field.setObjectName("login-field")
        self._password_field.setPlaceholderText("Password (8+ characters)")
        self._password_field.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_field.returnPressed.connect(self._on_submit)

        self._confirm_field = QLineEdit()
        self._confirm_field.setObjectName("login-field")
        self._confirm_field.setPlaceholderText("Confirm password")
        self._confirm_field.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_field.returnPressed.connect(self._on_submit)

        self._submit_btn = QPushButton("Create admin account")
        self._submit_btn.setObjectName("primary-btn")
        self._submit_btn.setFixedHeight(40)
        self._submit_btn.clicked.connect(self._on_submit)

        self._error_label = QLabel("")
        self._error_label.setObjectName("error-label")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setWordWrap(True)
        self._error_label.hide()

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(8)
        layout.addWidget(QLabel("Email"))
        layout.addWidget(self._email_field)
        layout.addWidget(QLabel("Password"))
        layout.addWidget(self._password_field)
        layout.addWidget(QLabel("Confirm password"))
        layout.addWidget(self._confirm_field)
        layout.addSpacing(4)
        layout.addWidget(self._submit_btn)
        layout.addWidget(self._error_label)

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
        confirm = self._confirm_field.text()

        if not email or "@" not in email:
            self._show_error("Please enter a valid email address.")
            return
        if len(password) < 8:
            self._show_error("Password must be at least 8 characters.")
            return
        if password != confirm:
            self._show_error("Passwords do not match.")
            return

        self._set_loading(True)
        self._error_label.hide()
        self._worker = ApiWorker(self._client.setup_admin, email, password)
        self._worker.success.connect(self._on_success)
        self._worker.failure.connect(self._on_failure)
        self._worker.start()

    def _on_success(self, result: dict) -> None:
        self._set_loading(False)
        self.setup_complete.emit(result)

    def _on_failure(self, message: str) -> None:
        self._set_loading(False)
        self._show_error(message or "Failed to create admin account.")

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _set_loading(self, loading: bool) -> None:
        self._submit_btn.setEnabled(not loading)
        self._submit_btn.setText("Creating…" if loading else "Create admin account")
        for field in (self._email_field, self._password_field, self._confirm_field):
            field.setEnabled(not loading)

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()
