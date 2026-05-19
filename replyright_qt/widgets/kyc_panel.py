from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from replyright_qt.api_client import ApiClient, ApiWorker
from replyright_qt.widgets.kyc_dialogs import KycNotificationDialog

DEFAULT_TEAM_MEMBERS = ["Hyun Song", "Eleanor Green", "Dakota Weglarz", "Brian Tarabocchia"]

# KycEvent statuses that accept user actions
_ACTIONABLE = {"pending", "acknowledged", "snoozed"}


def _ro_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


def _fmt_ts(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%m/%d %I:%M %p")
    except (ValueError, AttributeError):
        return iso or ""


class KycPanel(QWidget):
    """KYC Inspection Reminder — tracks and actions inspection reminders."""

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self._client = client
        self._kyc_status: dict = {}
        self._kyc_config: dict = {}
        self._current_event_id: int | None = None
        self._refresh_pending = False
        self._refresh_counter = 0
        self._notification: KycNotificationDialog | None = None

        self._build_ui()

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(1000)
        self._poll_timer.timeout.connect(self._on_tick)
        # Timer starts/stops with panel visibility via showEvent/hideEvent

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        main = QVBoxLayout(container)
        main.setContentsMargins(24, 24, 24, 24)
        main.setSpacing(16)

        title = QLabel("KYC Inspection Reminder")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        main.addWidget(title)

        subtitle = QLabel("Track and complete KYC inspection reminders for your shift.")
        subtitle.setWordWrap(True)
        main.addWidget(subtitle)

        # ── Current status ────────────────────────────────────────────────────
        status_group = QGroupBox("Current Status")
        status_layout = QVBoxLayout(status_group)
        status_layout.setSpacing(6)

        self._status_label = QLabel("Loading...")
        self._status_label.setWordWrap(True)
        self._due_label = QLabel("")
        self._countdown_label = QLabel("")
        self._countdown_label.setStyleSheet("font-weight: bold;")
        self._missed_label = QLabel("")

        for lbl in (self._status_label, self._due_label, self._countdown_label, self._missed_label):
            status_layout.addWidget(lbl)

        main.addWidget(status_group)

        # ── Action buttons ────────────────────────────────────────────────────
        action_group = QGroupBox("Actions")
        action_layout = QVBoxLayout(action_group)

        # Team member selector for Complete action
        team_row = QHBoxLayout()
        team_row.addWidget(QLabel("Completed by:"))
        self._team_combo = QComboBox()
        self._team_combo.addItems(DEFAULT_TEAM_MEMBERS)
        self._team_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        team_row.addWidget(self._team_combo)
        action_layout.addLayout(team_row)

        btn_row = QHBoxLayout()

        self._ack_btn = QPushButton("Acknowledge")
        self._ack_btn.setObjectName("secondary-btn")
        self._ack_btn.setEnabled(False)
        self._ack_btn.clicked.connect(self._on_acknowledge)
        btn_row.addWidget(self._ack_btn)

        self._snooze_btn = QPushButton("Snooze")
        self._snooze_btn.setObjectName("secondary-btn")
        self._snooze_btn.setEnabled(False)
        self._snooze_btn.clicked.connect(self._on_snooze)
        btn_row.addWidget(self._snooze_btn)

        self._snooze_spin = QSpinBox()
        self._snooze_spin.setRange(1, 240)
        self._snooze_spin.setValue(15)
        self._snooze_spin.setSuffix(" min")
        self._snooze_spin.setFixedWidth(80)
        btn_row.addWidget(self._snooze_spin)

        self._complete_btn = QPushButton("Complete")
        self._complete_btn.setObjectName("primary-btn")
        self._complete_btn.setEnabled(False)
        self._complete_btn.clicked.connect(self._on_complete)
        btn_row.addWidget(self._complete_btn)

        self._skip_btn = QPushButton("Skip")
        self._skip_btn.setObjectName("danger-btn")
        self._skip_btn.setEnabled(False)
        self._skip_btn.clicked.connect(self._on_skip)
        btn_row.addWidget(self._skip_btn)

        btn_row.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        action_layout.addLayout(btn_row)

        # Manual reminder creation
        manual_row = QHBoxLayout()
        self._create_btn = QPushButton("Create Manual Reminder")
        self._create_btn.setObjectName("secondary-btn")
        self._create_btn.clicked.connect(self._on_create_reminder)
        manual_row.addWidget(self._create_btn)
        manual_row.addStretch()
        action_layout.addLayout(manual_row)

        self._action_error = QLabel("")
        self._action_error.setStyleSheet("color: #e53e3e;")
        self._action_error.setWordWrap(True)
        action_layout.addWidget(self._action_error)

        main.addWidget(action_group)

        # ── Settings ──────────────────────────────────────────────────────────
        settings_group = QGroupBox("Settings")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setSpacing(8)

        self._enabled_check = QCheckBox("Reminders enabled")
        self._enabled_check.setChecked(True)
        settings_layout.addWidget(self._enabled_check)

        self._strict_check = QCheckBox("Strict mode (acknowledgement required)")
        settings_layout.addWidget(self._strict_check)

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Reminder interval:"))
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(1, 240)
        self._interval_spin.setValue(15)
        self._interval_spin.setSuffix(" min")
        self._interval_spin.setFixedWidth(80)
        interval_row.addWidget(self._interval_spin)
        interval_row.addStretch()
        settings_layout.addLayout(interval_row)

        settings_layout.addWidget(QLabel("On Phones Today:"))
        self._team_checks: dict[str, QCheckBox] = {}
        for name in DEFAULT_TEAM_MEMBERS:
            cb = QCheckBox(name)
            cb.setChecked(True)
            self._team_checks[name] = cb
            settings_layout.addWidget(cb)

        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("secondary-btn")
        save_btn.clicked.connect(self._on_save_settings)
        settings_layout.addWidget(save_btn)

        main.addWidget(settings_group)

        # ── History ───────────────────────────────────────────────────────────
        history_group = QGroupBox("Inspection History")
        history_layout = QVBoxLayout(history_group)

        self._history_table = QTableWidget(0, 5)
        self._history_table.setHorizontalHeaderLabels(["Due", "Status", "Team Member", "Completed", "Source"])
        self._history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._history_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._history_table.verticalHeader().setVisible(False)
        self._history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._history_table.setMaximumHeight(220)
        history_layout.addWidget(self._history_table)
        main.addWidget(history_group)

        main.addStretch()
        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ── Visibility lifecycle ───────────────────────────────────────────────────

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._poll_timer.isActive():
            self._poll_timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._poll_timer.stop()

    def activate(self) -> None:
        """Called when this panel becomes the active page."""
        self._fetch_status()
        self._fetch_config()
        self._fetch_history()

    # ── Poll timer ─────────────────────────────────────────────────────────────

    def _on_tick(self) -> None:
        self._update_countdown()
        self._refresh_counter += 1
        if self._refresh_counter >= 3 and not self._refresh_pending:
            self._refresh_counter = 0
            self._fetch_status()

    def _update_countdown(self) -> None:
        next_due_at = self._kyc_status.get("next_due_at")
        if not next_due_at:
            self._countdown_label.setText("")
            return
        try:
            next_due = datetime.fromisoformat(next_due_at.replace("Z", "+00:00"))
            now = datetime.now(tz=timezone.utc)
            remaining = max(0.0, (next_due - now).total_seconds())
            minutes, seconds = divmod(int(remaining), 60)
            self._countdown_label.setText(f"Time remaining: {minutes:02d}:{seconds:02d}")
        except (ValueError, OSError):
            pass

    # ── API calls ──────────────────────────────────────────────────────────────

    def _fetch_status(self) -> None:
        if self._refresh_pending:
            return
        self._refresh_pending = True
        worker = ApiWorker(self._client.kyc_get_status)
        worker.success.connect(self._on_status_loaded)
        worker.failure.connect(self._on_status_error)
        worker.start()
        self._status_worker = worker

    def _on_status_loaded(self, data: dict) -> None:
        self._refresh_pending = False
        self._kyc_status = data
        self._apply_status(data)

    def _on_status_error(self, _: str) -> None:
        self._refresh_pending = False
        self._status_label.setText("Status: Could not connect to backend")

    def _apply_status(self, data: dict) -> None:
        current = data.get("current_event") or {}
        event_status = current.get("status", "")
        overdue = data.get("overdue", False)
        requires_ack = data.get("requires_acknowledgement", False)
        missed = data.get("missed_count", 0)
        next_due_at = data.get("next_due_at")
        self._current_event_id = current.get("id")

        # Status label
        if not current:
            color = "#1a1d2e"
            self._status_label.setText("No active reminder")
            self._status_label.setStyleSheet(f"color: {color};")
        elif overdue:
            color = "#e53e3e"
            self._status_label.setText(f"INSPECTION OVERDUE — {event_status.upper()}")
            self._status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        else:
            color_map = {
                "pending": "#c05621",
                "acknowledged": "#285e61",
                "snoozed": "#744210",
                "completed": "#276749",
                "skipped": "#4a5568",
                "expired": "#742a2a",
            }
            color = color_map.get(event_status, "#1a1d2e")
            self._status_label.setText(f"Status: {event_status.title()}")
            self._status_label.setStyleSheet(f"color: {color};")

        # Due time label
        if next_due_at:
            self._due_label.setText(f"Next due: {_fmt_ts(next_due_at)}")
        else:
            self._due_label.setText("")

        # Missed count
        if missed > 0:
            self._missed_label.setText(f"Missed inspections: {missed}")
            self._missed_label.setStyleSheet("color: #e53e3e;")
        else:
            self._missed_label.setText("")
            self._missed_label.setStyleSheet("")

        # Update team combo from config
        team = self._kyc_config.get("phone_team_members", DEFAULT_TEAM_MEMBERS)
        self._update_team_combo(team)

        # Enable/disable action buttons
        actionable = bool(current) and event_status in _ACTIONABLE
        self._ack_btn.setEnabled(actionable and event_status != "acknowledged")
        self._snooze_btn.setEnabled(actionable)
        self._snooze_spin.setEnabled(actionable)
        self._complete_btn.setEnabled(actionable)
        self._skip_btn.setEnabled(actionable)

        # Strict mode popup when acknowledgement is required
        if requires_ack and (self._notification is None or not self._notification.isVisible()):
            self._show_notification(overdue=True, strict=True)

    def _update_team_combo(self, team_members: list[str]) -> None:
        current_text = self._team_combo.currentText()
        self._team_combo.clear()
        self._team_combo.addItems(team_members or DEFAULT_TEAM_MEMBERS)
        idx = self._team_combo.findText(current_text)
        if idx >= 0:
            self._team_combo.setCurrentIndex(idx)

    def _fetch_config(self) -> None:
        worker = ApiWorker(self._client.kyc_get_config)
        worker.success.connect(self._on_config_loaded)
        worker.failure.connect(lambda _: None)
        worker.start()
        self._config_worker = worker

    def _on_config_loaded(self, data: dict) -> None:
        self._kyc_config = data
        self._enabled_check.setChecked(bool(data.get("enabled", True)))
        self._strict_check.setChecked(bool(data.get("strict_mode", False)))
        interval = data.get("reminder_interval_minutes", 15)
        self._interval_spin.setValue(int(interval))

        team = data.get("phone_team_members", DEFAULT_TEAM_MEMBERS)
        for name, cb in self._team_checks.items():
            cb.setChecked(name in team)

        self._snooze_spin.setValue(int(interval))
        self._update_team_combo(team)

    def _fetch_history(self) -> None:
        worker = ApiWorker(self._client.kyc_get_history, 50)
        worker.success.connect(self._on_history_loaded)
        worker.failure.connect(lambda _: None)
        worker.start()
        self._history_worker = worker

    def _on_history_loaded(self, data: list) -> None:
        if not isinstance(data, list):
            return
        self._history_table.setRowCount(0)
        for event in reversed(data):
            row = self._history_table.rowCount()
            self._history_table.insertRow(row)
            status = event.get("status", "")
            status_item = _ro_item(status)
            color_map = {
                "completed": Qt.GlobalColor.darkGreen,
                "skipped": Qt.GlobalColor.darkGray,
                "expired": Qt.GlobalColor.red,
                "acknowledged": Qt.GlobalColor.darkCyan,
            }
            if status in color_map:
                status_item.setForeground(color_map[status])
            self._history_table.setItem(row, 0, _ro_item(_fmt_ts(event.get("due_at"))))
            self._history_table.setItem(row, 1, status_item)
            self._history_table.setItem(row, 2, _ro_item(event.get("team_member") or ""))
            self._history_table.setItem(row, 3, _ro_item(_fmt_ts(event.get("completed_at"))))
            self._history_table.setItem(row, 4, _ro_item(event.get("source") or ""))

    # ── Button handlers ────────────────────────────────────────────────────────

    def _on_notify_snooze(self) -> None:
        """Snooze from the notification dialog — always 5 minutes."""
        if self._current_event_id is None:
            return
        self._set_actions_enabled(False)
        worker = ApiWorker(self._client.kyc_snooze, self._current_event_id, 5)
        worker.success.connect(self._on_action_done)
        worker.failure.connect(self._on_action_error)
        worker.start()
        self._action_worker = worker

    def _on_acknowledge(self) -> None:
        if self._current_event_id is None:
            return
        self._set_actions_enabled(False)
        worker = ApiWorker(self._client.kyc_acknowledge, self._current_event_id)
        worker.success.connect(self._on_action_done)
        worker.failure.connect(self._on_action_error)
        worker.start()
        self._action_worker = worker

    def _on_snooze(self) -> None:
        if self._current_event_id is None:
            return
        minutes = self._snooze_spin.value()
        self._set_actions_enabled(False)
        worker = ApiWorker(self._client.kyc_snooze, self._current_event_id, minutes)
        worker.success.connect(self._on_action_done)
        worker.failure.connect(self._on_action_error)
        worker.start()
        self._action_worker = worker

    def _on_complete(self) -> None:
        if self._current_event_id is None:
            return
        team_member = self._team_combo.currentText() or None
        self._set_actions_enabled(False)
        worker = ApiWorker(self._client.kyc_complete, self._current_event_id, team_member)
        worker.success.connect(self._on_complete_done)
        worker.failure.connect(self._on_action_error)
        worker.start()
        self._action_worker = worker

    def _on_skip(self) -> None:
        if self._current_event_id is None:
            return
        self._set_actions_enabled(False)
        worker = ApiWorker(self._client.kyc_skip, self._current_event_id)
        worker.success.connect(self._on_action_done)
        worker.failure.connect(self._on_action_error)
        worker.start()
        self._action_worker = worker

    def _on_create_reminder(self) -> None:
        self._create_btn.setEnabled(False)
        worker = ApiWorker(self._client.kyc_create_reminder, None, "manual")
        worker.success.connect(self._on_reminder_created)
        worker.failure.connect(self._on_action_error)
        worker.start()
        self._create_worker = worker

    def _on_action_done(self, _: dict) -> None:
        self._action_error.setText("")
        self._fetch_status()
        self._fetch_history()

    def _on_complete_done(self, event: dict) -> None:
        team = event.get("team_member") or "team"
        self._action_error.setText("")
        self._action_error.setStyleSheet("color: #38a169;")
        self._action_error.setText(f"Inspection completed by {team}.")
        self._fetch_status()
        self._fetch_history()

    def _on_reminder_created(self, _: dict) -> None:
        self._create_btn.setEnabled(True)
        self._action_error.setText("")
        self._fetch_status()

    def _on_action_error(self, message: str) -> None:
        self._action_error.setStyleSheet("color: #e53e3e;")
        self._action_error.setText(f"Error: {message}")
        self._create_btn.setEnabled(True)
        self._fetch_status()

    def _set_actions_enabled(self, enabled: bool) -> None:
        for btn in (self._ack_btn, self._snooze_btn, self._complete_btn, self._skip_btn):
            btn.setEnabled(enabled)

    def _on_save_settings(self) -> None:
        update = {
            "enabled": self._enabled_check.isChecked(),
            "strict_mode": self._strict_check.isChecked(),
            "reminder_interval_minutes": self._interval_spin.value(),
            "phone_team_members": [
                name for name, cb in self._team_checks.items() if cb.isChecked()
            ],
        }
        worker = ApiWorker(self._client.kyc_update_config, update)
        worker.success.connect(self._on_config_loaded)
        worker.failure.connect(lambda msg: self._action_error.setText(f"Settings error: {msg}"))
        worker.start()
        self._save_worker = worker

    # ── Notification dialog ────────────────────────────────────────────────────

    def _show_notification(self, overdue: bool = False, strict: bool = False) -> None:
        if overdue:
            title = "KYC Inspection Overdue"
            message = "A KYC inspection is overdue. Please acknowledge or complete it now."
            success = False
        else:
            title = "KYC Inspection Due"
            message = "A KYC inspection reminder is due."
            success = True

        dlg = KycNotificationDialog(title, message, success=success, strict=strict, parent=self)
        dlg.acknowledged.connect(self._on_acknowledge)
        dlg.snoozed.connect(self._on_notify_snooze)
        self._notification = dlg
        dlg.show()
