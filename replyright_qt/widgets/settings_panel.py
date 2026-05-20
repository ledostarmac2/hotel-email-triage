from __future__ import annotations

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from replyright_qt.api_client import ApiClient, ApiWorker


class SettingsPanel(QWidget):
    """Basic application settings for the native shell."""

    theme_changed = Signal(str)
    profile_image_changed = Signal(str)

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.setObjectName("detail-panel")
        self._client = client
        self._settings = QSettings("ReplyRight", "ReplyRight")
        self._user_email = ""
        self._reset_worker: ApiWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(18)

        title = QLabel("Settings")
        title.setObjectName("detail-title")
        root.addWidget(title)

        appearance = self._card("Appearance")
        appearance_layout = appearance.layout()
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme"))
        self._theme_combo = QComboBox()
        self._theme_combo.addItem("Light", "light")
        self._theme_combo.addItem("Dark", "dark")
        current = str(self._settings.value("theme", "light", str) or "light")
        idx = self._theme_combo.findData(current)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self._theme_combo)
        theme_row.addStretch()
        appearance_layout.addLayout(theme_row)
        root.addWidget(appearance)

        account = self._card("Account")
        account_layout = account.layout()
        self._account_label = QLabel("Signed in")
        self._account_label.setObjectName("muted-label")
        account_layout.addWidget(self._account_label)
        reset_row = QHBoxLayout()
        reset_btn = QPushButton("Send password reset")
        reset_btn.setObjectName("secondary-btn")
        reset_btn.clicked.connect(self._on_password_reset)
        self._reset_status = QLabel("")
        self._reset_status.setObjectName("muted-label")
        reset_row.addWidget(reset_btn)
        reset_row.addWidget(self._reset_status)
        reset_row.addStretch()
        account_layout.addLayout(reset_row)

        profile_row = QHBoxLayout()
        profile_btn = QPushButton("Choose profile photo")
        profile_btn.setObjectName("secondary-btn")
        profile_btn.clicked.connect(self._on_choose_profile_image)
        clear_profile_btn = QPushButton("Clear photo")
        clear_profile_btn.setObjectName("secondary-btn")
        clear_profile_btn.clicked.connect(self._on_clear_profile_image)
        self._profile_status = QLabel("")
        self._profile_status.setObjectName("muted-label")
        profile_row.addWidget(profile_btn)
        profile_row.addWidget(clear_profile_btn)
        profile_row.addWidget(self._profile_status)
        profile_row.addStretch()
        account_layout.addLayout(profile_row)
        root.addWidget(account)

        workflow = self._card("Workflow")
        workflow_layout = workflow.layout()
        self._auto_open = QCheckBox("Open the first conversation after changing queues")
        self._auto_open.setChecked(self._settings.value("auto_open_first", True, type=bool))
        self._auto_open.toggled.connect(lambda checked: self._settings.setValue("auto_open_first", checked))
        workflow_layout.addWidget(self._auto_open)
        self._compact_rows = QCheckBox("Use compact conversation rows")
        self._compact_rows.setChecked(self._settings.value("compact_rows", False, type=bool))
        self._compact_rows.toggled.connect(lambda checked: self._settings.setValue("compact_rows", checked))
        workflow_layout.addWidget(self._compact_rows)
        root.addWidget(workflow)

        safety = self._card("Safety")
        safety_layout = safety.layout()
        safety_copy = QLabel(
            "ReplyRight reads Outlook messages for triage and updates local ReplyRight state only. "
            "It does not send, move, delete, archive, categorize, or mark Outlook messages read."
        )
        safety_copy.setObjectName("summary-text")
        safety_copy.setWordWrap(True)
        safety_layout.addWidget(safety_copy)
        root.addWidget(safety)

        root.addStretch()

    def set_user(self, user_data: dict) -> None:
        self._user_email = str(user_data.get("email") or "")
        role = str(user_data.get("role") or "user").title()
        if self._user_email:
            self._account_label.setText(f"{self._user_email}\nRole: {role}")
        else:
            self._account_label.setText(f"Role: {role}")
        profile_path = str(self._settings.value("profile_image", "", str) or "")
        self._profile_status.setText("Profile photo set." if profile_path else "Using initials avatar.")
        self.profile_image_changed.emit(profile_path)

    def _card(self, title: str) -> QWidget:
        card = QWidget()
        card.setObjectName("settings-card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        header = QLabel(title)
        header.setObjectName("settings-title")
        layout.addWidget(header)
        return card

    def _on_theme_changed(self) -> None:
        mode = str(self._theme_combo.currentData() or "light")
        self._settings.setValue("theme", mode)
        self.theme_changed.emit(mode)

    def _on_password_reset(self) -> None:
        if not self._user_email:
            self._reset_status.setText("No signed-in email available.")
            return
        self._reset_status.setText("Sending reset link...")
        self._reset_worker = ApiWorker(self._client.forgot_password, self._user_email)
        self._reset_worker.success.connect(lambda _: self._reset_status.setText("Reset link sent if email is configured."))
        self._reset_worker.failure.connect(lambda msg: self._reset_status.setText(f"Error: {msg}"))
        self._reset_worker.start()

    def _on_choose_profile_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Profile Photo",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)",
        )
        if not path:
            return
        self._settings.setValue("profile_image", path)
        self._profile_status.setText("Profile photo set.")
        self.profile_image_changed.emit(path)

    def _on_clear_profile_image(self) -> None:
        self._settings.remove("profile_image")
        self._profile_status.setText("Using initials avatar.")
        self.profile_image_changed.emit("")
