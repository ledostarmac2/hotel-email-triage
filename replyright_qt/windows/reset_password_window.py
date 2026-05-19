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


class ResetPasswordWindow(QWidget):
    """'Forgot password' screen — sends a reset link to the user's email."""

    back_to_login = Signal()

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self._client = client
        self._worker: ApiWorker | None = None
        self.setObjectName("login-root")
        self.setWindowTitle("ReplyRight — Reset Password")
        self.setMinimumSize(480, 340)
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

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

        title = QLabel("Reset your password")
        title.setObjectName("login-title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("Enter your email address and we'll send you a reset link.")
        subtitle.setObjectName("login-subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)

        self._email_field = QLineEdit()
        self._email_field.setObjectName("login-field")
        self._email_field.setPlaceholderText("Email address")
        self._email_field.returnPressed.connect(self._on_submit)

        self._submit_btn = QPushButton("Send reset link")
        self._submit_btn.setObjectName("primary-btn")
        self._submit_btn.setFixedHeight(40)
        self._submit_btn.clicked.connect(self._on_submit)

        self._status_label = QLabel("")
        self._status_label.setObjectName("error-label")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setWordWrap(True)
        self._status_label.hide()

        back_btn = QPushButton("← Back to sign in")
        back_btn.setObjectName("link-btn")
        back_btn.setFlat(True)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self._on_back)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(8)
        layout.addWidget(QLabel("Email"))
        layout.addWidget(self._email_field)
        layout.addSpacing(4)
        layout.addWidget(self._submit_btn)
        layout.addWidget(self._status_label)
        layout.addSpacing(8)
        layout.addWidget(back_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        h_wrap = QHBoxLayout()
        h_wrap.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        h_wrap.addWidget(card)
        h_wrap.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        root.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        root.addLayout(h_wrap)
        root.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_submit(self) -> None:
        email = self._email_field.text().strip()
        if not email or "@" not in email:
            self._show_status("Please enter a valid email address.", error=True)
            return
        self._set_loading(True)
        self._status_label.hide()
        self._worker = ApiWorker(self._client.forgot_password, email)
        self._worker.success.connect(self._on_success)
        self._worker.failure.connect(self._on_failure)
        self._worker.start()

    def _on_success(self, _: dict) -> None:
        self._set_loading(False)
        self._show_status(
            "If that email is registered, a reset link has been sent. Check your inbox.",
            error=False,
        )
        self._submit_btn.setEnabled(False)

    def _on_failure(self, message: str) -> None:
        self._set_loading(False)
        self._show_status(message or "Failed to send reset email. Contact your admin.", error=True)

    def _on_back(self) -> None:
        self.back_to_login.emit()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_loading(self, loading: bool) -> None:
        self._submit_btn.setEnabled(not loading)
        self._submit_btn.setText("Sending…" if loading else "Send reset link")
        self._email_field.setEnabled(not loading)

    def _show_status(self, message: str, *, error: bool) -> None:
        color = "#ef4444" if error else "#22c55e"
        self._status_label.setStyleSheet(f"color: {color};")
        self._status_label.setText(message)
        self._status_label.show()

    def clear(self) -> None:
        self._email_field.clear()
        self._status_label.hide()
        self._set_loading(False)
        self._submit_btn.setEnabled(True)
        self._submit_btn.setText("Send reset link")
