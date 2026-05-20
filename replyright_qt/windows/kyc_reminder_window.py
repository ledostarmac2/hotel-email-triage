from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from PySide6.QtCore import QSettings, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

TEAM_MEMBERS = ["Hyun Song", "Eleanor Green", "Dakota Weglarz", "Brian Tarabocchia"]
_DEFAULT_INTERVAL_MINUTES = 15
_SETTINGS_ORG = "ReplyRight"
_SETTINGS_APP = "KYCReminder"


class _KycWorker(QThread):
    finished = Signal(bool, str)

    def __init__(self, account: str, password: str, team_members: list[str]) -> None:
        super().__init__()
        self._account = account
        self._password = password
        self._team_members = team_members

    def run(self) -> None:
        try:
            from outlook_dashboard.kyc.automation import run_kyc_inspection

            ok, msg = run_kyc_inspection(
                account_name=self._account or None,
                password=self._password or None,
                available_team_members=self._team_members or None,
            )
        except Exception as exc:
            ok, msg = False, str(exc)
        self.finished.emit(bool(ok), str(msg))


class KycReminderWindow(QWidget):
    """Themed floating KYC Inspection Reminder window."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setObjectName("kyc-window")
        self.setWindowTitle("KYC Inspection Reminder")
        self.setMinimumSize(760, 640)
        self.resize(900, 720)

        self._settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        self._timer_running = False
        self._next_reminder: Optional[datetime] = None
        self._missed_count = 0
        self._worker: Optional[_KycWorker] = None

        self._build_ui()
        self._load_settings()

        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._on_tick)
        self._tick.start()
        self._refresh_labels()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        title = QLabel("KYC Inspection Reminder")
        title.setObjectName("kyc-title")
        root.addWidget(title)

        subtitle = QLabel("Track and complete KYC inspection reminders for your shift.")
        subtitle.setObjectName("kyc-subtitle")
        root.addWidget(subtitle)

        self._status_card = self._card("Current Status")
        status_layout = self._status_card.layout()
        self._state_lbl = QLabel("STOPPED")
        self._state_lbl.setObjectName("kyc-state")
        self._next_lbl = QLabel("Next due: Not scheduled")
        self._countdown_lbl = QLabel("Time remaining: --:--")
        self._missed_lbl = QLabel("Missed inspections: 0")
        self._result_lbl = QLabel("")
        self._result_lbl.setWordWrap(True)
        for label in (self._next_lbl, self._countdown_lbl, self._missed_lbl, self._result_lbl):
            label.setObjectName("kyc-body")
        status_layout.addWidget(self._state_lbl)
        status_layout.addWidget(self._next_lbl)
        status_layout.addWidget(self._countdown_lbl)
        status_layout.addWidget(self._missed_lbl)
        status_layout.addWidget(self._result_lbl)
        root.addWidget(self._status_card)

        actions = self._card("Actions")
        actions_layout = actions.layout()

        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        account_lbl = QLabel("Account")
        account_lbl.setObjectName("kyc-field-label")
        self._account_edit = QLineEdit()
        self._account_edit.setPlaceholderText("KYC account")
        password_lbl = QLabel("Password")
        password_lbl.setObjectName("kyc-field-label")
        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("Password")
        completed_lbl = QLabel("Completed by")
        completed_lbl.setObjectName("kyc-field-label")
        self._completed_by = QComboBox()
        self._completed_by.addItems(TEAM_MEMBERS)
        form.addWidget(account_lbl, 0, 0)
        form.addWidget(self._account_edit, 0, 1)
        form.addWidget(password_lbl, 1, 0)
        form.addWidget(self._password_edit, 1, 1)
        form.addWidget(completed_lbl, 2, 0)
        form.addWidget(self._completed_by, 2, 1)
        actions_layout.addLayout(form)

        self._remember_chk = QCheckBox("Remember account and team on this computer")
        actions_layout.addWidget(self._remember_chk)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self._start_btn = QPushButton("Start Timer")
        self._start_btn.setObjectName("secondary-btn")
        self._start_btn.clicked.connect(self._on_start_timer)
        self._ack_btn = QPushButton("Acknowledge")
        self._ack_btn.setObjectName("secondary-btn")
        self._ack_btn.clicked.connect(self._on_acknowledge)
        self._snooze_btn = QPushButton("Snooze")
        self._snooze_btn.setObjectName("secondary-btn")
        self._snooze_btn.clicked.connect(self._on_snooze)
        self._snooze_minutes = QSpinBox()
        self._snooze_minutes.setRange(1, 120)
        self._snooze_minutes.setValue(15)
        self._snooze_minutes.setSuffix(" min")
        self._complete_btn = QPushButton("Complete")
        self._complete_btn.setObjectName("primary-btn")
        self._complete_btn.clicked.connect(self._on_complete)
        self._skip_btn = QPushButton("Skip")
        self._skip_btn.setObjectName("danger-btn")
        self._skip_btn.clicked.connect(self._on_skip)
        self._run_btn = QPushButton("Run Now")
        self._run_btn.setObjectName("primary-btn")
        self._run_btn.clicked.connect(self._on_run_now)
        for widget in (
            self._start_btn,
            self._ack_btn,
            self._snooze_btn,
            self._snooze_minutes,
            self._complete_btn,
            self._skip_btn,
            self._run_btn,
        ):
            button_row.addWidget(widget)
        button_row.addStretch()
        actions_layout.addLayout(button_row)
        root.addWidget(actions)

        settings = self._card("Settings")
        settings_layout = settings.layout()
        self._enabled_chk = QCheckBox("Reminders enabled")
        self._enabled_chk.setChecked(True)
        self._strict_chk = QCheckBox("Strict mode (acknowledgement required)")
        interval_row = QHBoxLayout()
        interval_lbl = QLabel("Reminder interval")
        interval_lbl.setObjectName("kyc-field-label")
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(1, 240)
        self._interval_spin.setValue(_DEFAULT_INTERVAL_MINUTES)
        self._interval_spin.setSuffix(" min")
        interval_row.addWidget(interval_lbl)
        interval_row.addWidget(self._interval_spin)
        interval_row.addStretch()
        settings_layout.addWidget(self._enabled_chk)
        settings_layout.addWidget(self._strict_chk)
        settings_layout.addLayout(interval_row)

        phones_lbl = QLabel("On Phones Today")
        phones_lbl.setObjectName("kyc-field-label")
        settings_layout.addWidget(phones_lbl)
        self._team_checks: dict[str, QCheckBox] = {}
        for name in TEAM_MEMBERS:
            cb = QCheckBox(name)
            cb.setChecked(True)
            self._team_checks[name] = cb
            settings_layout.addWidget(cb)

        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("secondary-btn")
        save_btn.clicked.connect(self._save_settings)
        settings_layout.addWidget(save_btn)
        root.addWidget(settings)

        history = self._card("Inspection History")
        history_layout = history.layout()
        self._history_table = QTableWidget(0, 5)
        self._history_table.setHorizontalHeaderLabels(["Due", "Status", "Team Member", "Completed", "Source"])
        self._history_table.verticalHeader().hide()
        self._history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._history_table.setAlternatingRowColors(False)
        history_layout.addWidget(self._history_table)
        root.addWidget(history, stretch=1)

    def _card(self, title: str) -> QGroupBox:
        card = QGroupBox(title)
        card.setObjectName("kyc-card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 20, 12, 12)
        layout.setSpacing(8)
        return card

    def _load_settings(self) -> None:
        remember = self._settings.value("remember_account", False, type=bool)
        self._remember_chk.setChecked(remember)
        if remember:
            self._account_edit.setText(self._settings.value("account", "", type=str))
        self._enabled_chk.setChecked(self._settings.value("enabled", True, type=bool))
        self._strict_chk.setChecked(self._settings.value("strict", False, type=bool))
        self._interval_spin.setValue(self._settings.value("interval", _DEFAULT_INTERVAL_MINUTES, type=int))
        self._snooze_minutes.setValue(self._settings.value("snooze", 15, type=int))
        completed_by = self._settings.value("completed_by", TEAM_MEMBERS[0], type=str)
        idx = self._completed_by.findText(completed_by)
        if idx >= 0:
            self._completed_by.setCurrentIndex(idx)
        for name, cb in self._team_checks.items():
            cb.setChecked(self._settings.value(f"team/{name.replace(' ', '_')}", True, type=bool))

    def _save_settings(self) -> None:
        remember = self._remember_chk.isChecked()
        self._settings.setValue("remember_account", remember)
        if remember:
            self._settings.setValue("account", self._account_edit.text().strip())
        else:
            self._settings.remove("account")
        self._settings.setValue("enabled", self._enabled_chk.isChecked())
        self._settings.setValue("strict", self._strict_chk.isChecked())
        self._settings.setValue("interval", self._interval_spin.value())
        self._settings.setValue("snooze", self._snooze_minutes.value())
        self._settings.setValue("completed_by", self._completed_by.currentText())
        for name, cb in self._team_checks.items():
            self._settings.setValue(f"team/{name.replace(' ', '_')}", cb.isChecked())
        self._set_result("Settings saved.", ok=True)

    def _on_start_timer(self) -> None:
        self._save_settings()
        self._timer_running = True
        self._next_reminder = datetime.now() + timedelta(minutes=self._interval_spin.value())
        self._start_btn.setText("Timer Running")
        self._start_btn.setEnabled(False)
        self._refresh_labels()

    def _on_acknowledge(self) -> None:
        self._set_result("Reminder acknowledged.", ok=True)

    def _on_snooze(self) -> None:
        self._timer_running = True
        self._next_reminder = datetime.now() + timedelta(minutes=self._snooze_minutes.value())
        self._set_result(f"Snoozed for {self._snooze_minutes.value()} minutes.", ok=True)
        self._refresh_labels()

    def _on_complete(self) -> None:
        self._add_history("complete")
        self._timer_running = True
        self._next_reminder = datetime.now() + timedelta(minutes=self._interval_spin.value())
        self._missed_count = 0
        self._set_result("Inspection marked complete.", ok=True)
        self._refresh_labels()

    def _on_skip(self) -> None:
        self._add_history("skipped")
        self._timer_running = True
        self._next_reminder = datetime.now() + timedelta(minutes=self._interval_spin.value())
        self._set_result("Inspection skipped. Next reminder scheduled.", ok=False)
        self._refresh_labels()

    def _on_tick(self) -> None:
        if not self._timer_running or self._next_reminder is None:
            self._refresh_labels()
            return
        if datetime.now() >= self._next_reminder:
            self._missed_count += 1
            self._add_history("pending")
            self._next_reminder = datetime.now() + timedelta(minutes=self._interval_spin.value())
            if self._enabled_chk.isChecked():
                self._trigger_inspection()
        self._refresh_labels()

    def _refresh_labels(self) -> None:
        if not self._timer_running or self._next_reminder is None:
            self._state_lbl.setText("STOPPED")
            self._state_lbl.setProperty("state", "stopped")
            self._next_lbl.setText("Next due: Not scheduled")
            self._countdown_lbl.setText("Time remaining: --:--")
        else:
            remaining = max(0.0, (self._next_reminder - datetime.now()).total_seconds())
            minutes, seconds = divmod(int(remaining), 60)
            overdue = remaining <= 1 and self._missed_count > 0
            self._state_lbl.setText("INSPECTION OVERDUE - PENDING" if overdue else "RUNNING")
            self._state_lbl.setProperty("state", "overdue" if overdue else "running")
            self._next_lbl.setText(f"Next due: {self._next_reminder.strftime('%m/%d %I:%M %p')}")
            self._countdown_lbl.setText(f"Time remaining: {minutes:02d}:{seconds:02d}")
        self._missed_lbl.setText(f"Missed inspections: {self._missed_count}")
        self._state_lbl.style().unpolish(self._state_lbl)
        self._state_lbl.style().polish(self._state_lbl)

    def _on_run_now(self) -> None:
        self._save_settings()
        self._trigger_inspection()

    def _trigger_inspection(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        account = self._account_edit.text().strip()
        password = self._password_edit.text()
        team = [name for name, cb in self._team_checks.items() if cb.isChecked()]
        self._run_btn.setEnabled(False)
        self._set_result("Running KYC inspection...", neutral=True)
        self._worker = _KycWorker(account, password, team)
        self._worker.finished.connect(self._on_worker_done)
        self._worker.start()

    def _on_worker_done(self, ok: bool, message: str) -> None:
        self._run_btn.setEnabled(True)
        if ok:
            self._add_history("complete")
            self._set_result(f"Automation complete: {message}", ok=True)
        else:
            self._set_result(f"Automation unavailable: {message}", ok=False)

    def _set_result(self, message: str, ok: bool = False, neutral: bool = False) -> None:
        self._result_lbl.setText(message)
        self._result_lbl.setProperty("tone", "neutral" if neutral else "success" if ok else "danger")
        self._result_lbl.style().unpolish(self._result_lbl)
        self._result_lbl.style().polish(self._result_lbl)

    def _add_history(self, status: str) -> None:
        row = self._history_table.rowCount()
        self._history_table.insertRow(row)
        due = self._next_reminder or datetime.now()
        values = [
            due.strftime("%m/%d %I:%M %p"),
            status,
            self._completed_by.currentText() if status == "complete" else "",
            datetime.now().strftime("%I:%M %p") if status == "complete" else "",
            "scheduler" if status == "pending" else "manual",
        ]
        for col, value in enumerate(values):
            self._history_table.setItem(row, col, QTableWidgetItem(value))

    def closeEvent(self, event) -> None:
        self._save_settings()
        super().closeEvent(event)
