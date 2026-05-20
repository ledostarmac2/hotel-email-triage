from __future__ import annotations

import os

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGraphicsDropShadowEffect,
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
    forgot_password_requested = Signal()

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self._client = client
        self._worker: ApiWorker | None = None
        self._settings = QSettings("ReplyRight", "ReplyRight")
        self.setObjectName("login-root")
        self.setWindowTitle("ReplyRight - Sign In")
        self.setMinimumSize(520, 560)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(0)

        card = QWidget()
        card.setObjectName("login-card")
        card.setFixedWidth(430)
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(34)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(4, 8, 18, 95))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(38, 36, 38, 34)
        card_layout.setSpacing(12)

        logo_panel = QWidget()
        logo_panel.setObjectName("login-logo-panel")
        logo_panel_layout = QVBoxLayout(logo_panel)
        logo_panel_layout.setContentsMargins(14, 10, 14, 10)
        logo_panel_layout.setSpacing(2)
        brand_mark = QLabel("ReplyRight")
        brand_mark.setObjectName("login-mark")
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "outlook_dashboard",
            "static",
            "replyright-logo.png",
        )
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                brand_mark.setPixmap(pixmap.scaledToWidth(138, Qt.TransformationMode.SmoothTransformation))
                brand_mark.setObjectName("login-logo")
        logo_panel_layout.addWidget(brand_mark, alignment=Qt.AlignmentFlag.AlignCenter)
        logo_tagline = QLabel("The right response, every time.")
        logo_tagline.setObjectName("login-logo-tagline")
        logo_tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_panel_layout.addWidget(logo_tagline)

        title = QLabel("ReplyRight")
        title.setObjectName("login-title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("Hotel email triage for reservations operations")
        subtitle.setObjectName("login-subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._email_field = QLineEdit()
        self._email_field.setObjectName("login-field")
        self._email_field.setPlaceholderText("Email address")
        self._email_field.returnPressed.connect(self._on_submit)
        remembered = str(self._settings.value("remembered_email", "", str) or "").strip()
        if remembered:
            self._email_field.setText(remembered)

        self._password_field = QLineEdit()
        self._password_field.setObjectName("login-field")
        self._password_field.setPlaceholderText("Password")
        self._password_field.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_field.returnPressed.connect(self._on_submit)

        self._remember_email = QCheckBox("Remember email")
        self._remember_email.setObjectName("login-checkbox")
        self._remember_email.setChecked(bool(remembered))

        forgot_btn = QPushButton("Forgot password?")
        forgot_btn.setObjectName("link-btn")
        forgot_btn.setFlat(True)
        forgot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        forgot_btn.clicked.connect(self.forgot_password_requested)

        self._submit_btn = QPushButton("Sign in")
        self._submit_btn.setObjectName("primary-btn")
        self._submit_btn.setFixedHeight(44)
        self._submit_btn.clicked.connect(self._on_submit)

        self._error_label = QLabel("")
        self._error_label.setObjectName("error-label")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._error_label.setWordWrap(True)
        self._error_label.hide()

        divider = QFrame()
        divider.setObjectName("login-divider")
        divider.setFrameShape(QFrame.Shape.HLine)

        footnote = QLabel("Supabase sign-in. Outlook remains read-only.")
        footnote.setObjectName("login-footnote")
        footnote.setAlignment(Qt.AlignmentFlag.AlignCenter)

        options_row = QHBoxLayout()
        options_row.setContentsMargins(0, 2, 0, 2)
        options_row.addWidget(self._remember_email)
        options_row.addStretch(1)
        options_row.addWidget(forgot_btn)

        card_layout.addWidget(logo_panel, alignment=Qt.AlignmentFlag.AlignCenter)
        card_layout.addSpacing(6)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(18)
        card_layout.addWidget(self._field_label("Email"))
        card_layout.addWidget(self._email_field)
        card_layout.addWidget(self._field_label("Password"))
        card_layout.addWidget(self._password_field)
        card_layout.addLayout(options_row)
        card_layout.addSpacing(8)
        card_layout.addWidget(self._submit_btn)
        card_layout.addWidget(self._error_label)
        card_layout.addSpacing(14)
        card_layout.addWidget(divider)
        card_layout.addWidget(footnote)

        h_wrap = QHBoxLayout()
        h_wrap.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        h_wrap.addWidget(card)
        h_wrap.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        root.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        root.addLayout(h_wrap)
        root.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

    def _on_submit(self) -> None:
        email = self._email_field.text().strip()
        password = self._password_field.text()
        if not email or not password:
            self._show_error("Please enter your email and password.")
            return
        self._store_remembered_email(email)
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

    def _set_loading(self, loading: bool) -> None:
        self._submit_btn.setEnabled(not loading)
        self._submit_btn.setText("Signing in..." if loading else "Sign in")
        self._email_field.setEnabled(not loading)
        self._password_field.setEnabled(not loading)
        self._remember_email.setEnabled(not loading)

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("login-field-label")
        return label

    def _store_remembered_email(self, email: str) -> None:
        if self._remember_email.isChecked():
            self._settings.setValue("remembered_email", email.lower())
        else:
            self._settings.remove("remembered_email")

    def clear(self) -> None:
        remembered = str(self._settings.value("remembered_email", "", str) or "").strip()
        self._email_field.setText(remembered)
        self._remember_email.setChecked(bool(remembered))
        self._password_field.clear()
        self._error_label.hide()
        self._set_loading(False)
