from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from PySide6.QtCore import QSettings, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

TEAM_MEMBERS = ["Hyun Song", "Eleanor Green", "Dakota Weglarz", "Brian Tarabocchia"]
_INTERVAL_MINUTES = 15
_SETTINGS_ORG = "ReplyRight"
_SETTINGS_APP = "KYCAuto"


class _KycWorker(QThread):
    finished = Signal(bool, str)

    def __init__(self, username: str, password: str, team_members: list[str]) -> None:
        super().__init__()
        self._username = username
        self._password = password
        self._team_members = team_members

    def run(self) -> None:
        try:
            from outlook_dashboard.kyc.automation import run_kyc_inspection

            ok, msg = run_kyc_inspection(
                account_name=self._username or None,
                password=self._password or None,
                available_team_members=self._team_members or None,
            )
        except Exception as exc:
            ok, msg = False, str(exc)
        self.finished.emit(bool(ok), str(msg))


class KycReminderWindow(QWidget):
    """KYC Auto control window.

    The historical app called this a reminder, but the active UI is automation:
    either run the KYC browser workflow now or start a 15-minute timer that runs
    the automation in the background.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setObjectName("kyc-window")
        self.setWindowTitle("KYC Auto")
        self.setMinimumSize(560, 420)
        self.resize(640, 500)

        self._settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        self._timer_running = False
        self._next_run_at: Optional[datetime] = None
        self._last_run_text = "Last run: Not run this session"
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

        title = QLabel("KYC Auto")
        title.setObjectName("kyc-title")
        root.addWidget(title)

        subtitle = QLabel("Run the KYC browser automation for the current phone team.")
        subtitle.setObjectName("kyc-subtitle")
        root.addWidget(subtitle)

        status = self._card("Current Status")
        status_layout = status.layout()
        self._state_lbl = QLabel("STOPPED")
        self._state_lbl.setObjectName("kyc-state")
        self._timer_lbl = QLabel("Timer: Not running")
        self._last_run_lbl = QLabel(self._last_run_text)
        self._result_lbl = QLabel("")
        self._result_lbl.setWordWrap(True)
        for label in (self._timer_lbl, self._last_run_lbl, self._result_lbl):
            label.setObjectName("kyc-body")
        status_layout.addWidget(self._state_lbl)
        status_layout.addWidget(self._timer_lbl)
        status_layout.addWidget(self._last_run_lbl)
        status_layout.addWidget(self._result_lbl)
        root.addWidget(status)

        credentials = self._card("Credentials")
        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        username_lbl = QLabel("KYC username")
        username_lbl.setObjectName("kyc-field-label")
        self._username_edit = QLineEdit()
        self._username_edit.setPlaceholderText("KYC username")

        password_lbl = QLabel("KYC password")
        password_lbl.setObjectName("kyc-field-label")
        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("Password")

        form.addWidget(username_lbl, 0, 0)
        form.addWidget(self._username_edit, 0, 1)
        form.addWidget(password_lbl, 1, 0)
        form.addWidget(self._password_edit, 1, 1)
        credentials.layout().addLayout(form)
        root.addWidget(credentials)

        phones = self._card("On Phones Today")
        phones_layout = phones.layout()
        self._team_checks: dict[str, QCheckBox] = {}
        for name in TEAM_MEMBERS:
            cb = QCheckBox(name)
            cb.setObjectName("kyc-check")
            cb.setChecked(True)
            self._team_checks[name] = cb
            phones_layout.addWidget(cb)
        root.addWidget(phones)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self._start_btn = QPushButton("Start Timer")
        self._start_btn.setObjectName("primary-btn")
        self._start_btn.clicked.connect(self._on_start_timer)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("danger-btn")
        self._cancel_btn.clicked.connect(self._on_cancel_timer)
        self._run_btn = QPushButton("Run Now")
        self._run_btn.setObjectName("primary-btn")
        self._run_btn.clicked.connect(self._on_run_now)
        for button in (self._start_btn, self._cancel_btn, self._run_btn):
            button.setMinimumWidth(118)
            button.setFixedHeight(36)
            actions.addWidget(button)
        actions.addStretch()
        root.addLayout(actions)
        root.addStretch()

    def _card(self, title: str) -> QGroupBox:
        card = QGroupBox(title)
        card.setObjectName("kyc-card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 20, 12, 12)
        layout.setSpacing(8)
        return card

    def _load_settings(self) -> None:
        self._username_edit.setText(self._settings.value("username", "", type=str))
        for name, cb in self._team_checks.items():
            cb.setChecked(self._settings.value(f"team/{name.replace(' ', '_')}", True, type=bool))

    def _save_settings(self) -> None:
        self._settings.setValue("username", self._username_edit.text().strip())
        for name, cb in self._team_checks.items():
            self._settings.setValue(f"team/{name.replace(' ', '_')}", cb.isChecked())

    def _on_start_timer(self) -> None:
        self._save_settings()
        self._timer_running = True
        self._next_run_at = datetime.now() + timedelta(minutes=_INTERVAL_MINUTES)
        self._set_result("KYC Auto timer started. Automation will run every 15 minutes.", neutral=True)
        self._refresh_labels()

    def _on_cancel_timer(self) -> None:
        self._timer_running = False
        self._next_run_at = None
        self._set_result("KYC Auto timer cancelled.", neutral=True)
        self._refresh_labels()

    def _on_run_now(self) -> None:
        self._save_settings()
        self._trigger_automation(manual=True)

    def _on_tick(self) -> None:
        if self._timer_running and self._next_run_at is not None and datetime.now() >= self._next_run_at:
            self._trigger_automation(manual=False)
            self._next_run_at = datetime.now() + timedelta(minutes=_INTERVAL_MINUTES)
        self._refresh_labels()

    def _refresh_labels(self) -> None:
        worker_running = self._worker is not None and self._worker.isRunning()
        if worker_running:
            self._state_lbl.setText("RUNNING AUTOMATION")
            self._state_lbl.setProperty("state", "running")
        elif self._timer_running and self._next_run_at is not None:
            remaining = max(0.0, (self._next_run_at - datetime.now()).total_seconds())
            minutes, seconds = divmod(int(remaining), 60)
            self._state_lbl.setText("TIMER RUNNING")
            self._state_lbl.setProperty("state", "running")
            self._timer_lbl.setText(f"Timer: {minutes:02d}:{seconds:02d}")
        else:
            self._state_lbl.setText("STOPPED")
            self._state_lbl.setProperty("state", "stopped")
            self._timer_lbl.setText("Timer: Not running")
        self._last_run_lbl.setText(self._last_run_text)
        self._start_btn.setEnabled(not worker_running)
        self._run_btn.setEnabled(not worker_running)
        self._cancel_btn.setEnabled(self._timer_running)
        self._state_lbl.style().unpolish(self._state_lbl)
        self._state_lbl.style().polish(self._state_lbl)

    def _trigger_automation(self, manual: bool) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        username = self._username_edit.text().strip()
        password = self._password_edit.text()
        team = [name for name, cb in self._team_checks.items() if cb.isChecked()]
        self._set_result("Running KYC Auto...", neutral=True)
        self._worker = _KycWorker(username, password, team)
        self._worker.finished.connect(lambda ok, message, source="manual" if manual else "timer": self._on_worker_done(ok, message, source))
        self._worker.start()
        self._refresh_labels()

    def _on_worker_done(self, ok: bool, message: str, source: str) -> None:
        timestamp = datetime.now().strftime("%I:%M %p").lstrip("0")
        self._last_run_text = f"Last run: {timestamp} ({source})"
        if ok:
            self._set_result(f"KYC Auto completed: {message}", ok=True)
        else:
            self._set_result(f"KYC Auto unavailable: {message}", ok=False)
        self._refresh_labels()

    def _set_result(self, message: str, ok: bool = False, neutral: bool = False) -> None:
        self._result_lbl.setText(message)
        self._result_lbl.setProperty("tone", "neutral" if neutral else "success" if ok else "danger")
        self._result_lbl.style().unpolish(self._result_lbl)
        self._result_lbl.style().polish(self._result_lbl)

    def closeEvent(self, event) -> None:
        self._save_settings()
        super().closeEvent(event)
