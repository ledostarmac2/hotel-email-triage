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


class CredentialsSetupWindow(QWidget):
    """First-run window to enter Supabase and Anthropic credentials.

    Emits setup_complete() when credentials are successfully saved.
    The caller should then check startup state and route accordingly.
    """

    setup_complete = Signal()

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self._client = client
        self._worker: ApiWorker | None = None
        self.setObjectName("login-root")
        self.setWindowTitle("ReplyRight — Initial Setup")
        self.setMinimumSize(520, 520)
        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.setContentsMargins(0, 0, 0, 0)

        card = QWidget()
        card.setObjectName("login-card")
        card.setFixedWidth(440)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(36, 32, 36, 36)
        layout.setSpacing(12)

        title = QLabel("ReplyRight Setup")
        title.setObjectName("login-title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel(
            "Enter your Supabase project credentials to get started.\n"
            "These are saved locally and never transmitted."
        )
        subtitle.setObjectName("login-subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(8)

        def _field(placeholder: str, password: bool = False) -> QLineEdit:
            f = QLineEdit()
            f.setObjectName("login-field")
            f.setPlaceholderText(placeholder)
            if password:
                f.setEchoMode(QLineEdit.EchoMode.Password)
            return f

        layout.addWidget(QLabel("Supabase Project URL  (https://…)"))
        self._url_field = _field("https://xxxxxxxx.supabase.co")
        layout.addWidget(self._url_field)

        layout.addWidget(QLabel("Supabase Anon Key"))
        self._anon_key_field = _field("eyJ…", password=True)
        layout.addWidget(self._anon_key_field)

        layout.addWidget(QLabel("Supabase Service-Role Key"))
        self._svc_key_field = _field("eyJ…", password=True)
        layout.addWidget(self._svc_key_field)

        optional_label = QLabel("Anthropic API Key  (optional — enables AI analysis)")
        optional_label.setStyleSheet("color: #718096; font-size: 12px;")
        layout.addWidget(optional_label)
        self._ai_key_field = _field("sk-ant-…", password=True)
        layout.addWidget(self._ai_key_field)

        layout.addSpacing(4)

        self._submit_btn = QPushButton("Save credentials")
        self._submit_btn.setObjectName("primary-btn")
        self._submit_btn.setFixedHeight(40)
        self._submit_btn.clicked.connect(self._on_submit)
        layout.addWidget(self._submit_btn)

        self._error_label = QLabel("")
        self._error_label.setObjectName("error-label")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setWordWrap(True)
        self._error_label.hide()
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
        url = self._url_field.text().strip()
        anon = self._anon_key_field.text().strip()
        svc = self._svc_key_field.text().strip()
        ai = self._ai_key_field.text().strip()

        if not url.startswith("https://"):
            self._show_error("Supabase URL must start with https://")
            return
        if len(anon) < 20:
            self._show_error("Supabase anon key appears too short.")
            return
        if len(svc) < 20:
            self._show_error("Supabase service-role key appears too short.")
            return

        self._set_loading(True)
        self._error_label.hide()
        self._worker = ApiWorker(
            self._client.credentials_setup, url, anon, svc, ai
        )
        self._worker.success.connect(self._on_success)
        self._worker.failure.connect(self._on_failure)
        self._worker.start()

    def _on_success(self, _: dict) -> None:
        self._set_loading(False)
        self.setup_complete.emit()

    def _on_failure(self, message: str) -> None:
        self._set_loading(False)
        self._show_error(message or "Failed to save credentials.")

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _set_loading(self, loading: bool) -> None:
        self._submit_btn.setEnabled(not loading)
        self._submit_btn.setText("Saving…" if loading else "Save credentials")
        for field in (self._url_field, self._anon_key_field, self._svc_key_field, self._ai_key_field):
            field.setEnabled(not loading)

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()
