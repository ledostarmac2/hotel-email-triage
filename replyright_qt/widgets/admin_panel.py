from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from replyright_qt.api_client import ApiClient, ApiWorker


class _StatCard(QWidget):
    """Small key/value card displayed in the overview stats bar."""

    def __init__(self, title: str, value: str = "—") -> None:
        super().__init__()
        self.setObjectName("stat-card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self._value_label = QLabel(value)
        self._value_label.setObjectName("stat-value")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel(title)
        title_label.setObjectName("stat-title")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self._value_label)
        layout.addWidget(title_label)

    def set_value(self, value: str) -> None:
        self._value_label.setText(value)


def _read_only_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


def _build_corrections_table(rows: list[dict]) -> QTableWidget:
    table = QTableWidget(len(rows), 3)
    table.setHorizontalHeaderLabels(["Type", "Label", "Count"])
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().setVisible(False)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    for i, row in enumerate(rows):
        table.setItem(i, 0, _read_only_item(row.get("type", "")))
        table.setItem(i, 1, _read_only_item(row.get("label", "")))
        table.setItem(i, 2, _read_only_item(str(row.get("count", ""))))
    return table


def _build_low_confidence_table(rows: list[dict]) -> QTableWidget:
    cols = ["Subject", "Sender", "Category", "Confidence"]
    table = QTableWidget(len(rows), len(cols))
    table.setHorizontalHeaderLabels(cols)
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().setVisible(False)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    for i, row in enumerate(rows):
        table.setItem(i, 0, _read_only_item(row.get("subject", "") or "(no subject)"))
        table.setItem(i, 1, _read_only_item(row.get("sender_email", "")))
        table.setItem(i, 2, _read_only_item(row.get("category", "")))
        conf = row.get("confidence_score")
        table.setItem(i, 3, _read_only_item(f"{conf:.0f}%" if conf is not None else "—"))
    return table


def _build_audit_table(rows: list[dict]) -> QTableWidget:
    cols = ["Time", "Action", "Actor", "Detail"]
    table = QTableWidget(len(rows), len(cols))
    table.setHorizontalHeaderLabels(cols)
    table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().setVisible(False)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    for i, row in enumerate(rows):
        ts = row.get("created_at", "")[:16].replace("T", " ")
        table.setItem(i, 0, _read_only_item(ts))
        table.setItem(i, 1, _read_only_item(row.get("action", "")))
        table.setItem(i, 2, _read_only_item(row.get("actor_email", "") or row.get("actor", "")))
        detail = row.get("detail") or row.get("metadata") or ""
        if isinstance(detail, dict):
            detail = ", ".join(f"{k}={v}" for k, v in list(detail.items())[:3])
        table.setItem(i, 3, _read_only_item(str(detail)[:120]))
    return table


class _UsersTab(QWidget):
    """Users management tab: list, invite, delete."""

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self._client = client
        self._users: list[dict] = []
        self._worker: ApiWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        invite_btn = QPushButton("Invite user")
        invite_btn.setObjectName("secondary-btn")
        invite_btn.setFixedHeight(28)
        invite_btn.clicked.connect(self._on_invite)

        self._delete_btn = QPushButton("Delete selected")
        self._delete_btn.setObjectName("danger-btn")
        self._delete_btn.setFixedHeight(28)
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete)

        self._user_status = QLabel("")
        self._user_status.setStyleSheet("color: #718096; font-size: 12px;")

        toolbar.addWidget(invite_btn)
        toolbar.addWidget(self._delete_btn)
        toolbar.addWidget(self._user_status)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Email", "Role", "Created", "ID"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.selectionModel().selectionChanged.connect(self._on_selection)
        layout.addWidget(self._table)

    def load(self) -> None:
        self._user_status.setText("Loading…")
        self._worker = ApiWorker(self._client.list_users)
        self._worker.success.connect(self._on_loaded)
        self._worker.failure.connect(self._on_error)
        self._worker.start()

    def _on_loaded(self, users: list) -> None:
        self._users = users
        self._user_status.setText("")
        self._table.setRowCount(len(users))
        for i, u in enumerate(users):
            self._table.setItem(i, 0, _read_only_item(u.get("email", "")))
            self._table.setItem(i, 1, _read_only_item(u.get("role", "")))
            ts = (u.get("created_at") or "")[:10]
            self._table.setItem(i, 2, _read_only_item(ts))
            self._table.setItem(i, 3, _read_only_item(str(u.get("id", ""))))

    def _on_error(self, message: str) -> None:
        self._user_status.setText(f"Error: {message}")

    def _on_selection(self) -> None:
        self._delete_btn.setEnabled(bool(self._table.selectedItems()))

    def _on_invite(self) -> None:
        email, ok = QInputDialog.getText(self, "Invite User", "Email address to invite:")
        if not ok or not email.strip():
            return
        self._user_status.setText("Sending invite…")
        worker = ApiWorker(self._client.invite_user, email.strip())
        worker.success.connect(lambda _: self._user_status.setText(f"Invite sent to {email.strip()}."))
        worker.failure.connect(lambda msg: self._user_status.setText(f"Error: {msg}"))
        worker.start()
        self._invite_worker = worker

    def _on_delete(self) -> None:
        rows = {idx.row() for idx in self._table.selectedIndexes()}
        if not rows:
            return
        row = next(iter(rows))
        if row >= len(self._users):
            return
        user = self._users[row]
        reply = QMessageBox.question(
            self,
            "Delete user",
            f"Delete {user.get('email', '')}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._user_status.setText("Deleting…")
        worker = ApiWorker(self._client.delete_user, str(user["id"]))
        worker.success.connect(lambda _: self.load())
        worker.failure.connect(lambda msg: self._user_status.setText(f"Error: {msg}"))
        worker.start()
        self._delete_worker = worker


class _TrainingTab(QWidget):
    """Training tab: pipeline status + trigger training / classifier rebuild."""

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self._client = client
        self._worker: ApiWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        status_group = QGroupBox("Pipeline Status")
        sg_layout = QVBoxLayout(status_group)
        self._status_label = QLabel("Click Refresh to load status.")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("font-size: 13px; color: #4a5568;")
        sg_layout.addWidget(self._status_label)
        layout.addWidget(status_group)

        actions_group = QGroupBox("Actions")
        ag_layout = QVBoxLayout(actions_group)

        pipeline_row = QHBoxLayout()
        self._run_pipeline_btn = QPushButton("Run training pipeline")
        self._run_pipeline_btn.setObjectName("primary-btn")
        self._run_pipeline_btn.setFixedHeight(34)
        self._run_pipeline_btn.clicked.connect(self._on_run_pipeline)
        pipeline_desc = QLabel("Process new feedback examples from Supabase (batch_size=10)")
        pipeline_desc.setStyleSheet("color: #718096; font-size: 12px;")
        pipeline_row.addWidget(self._run_pipeline_btn)
        pipeline_row.addWidget(pipeline_desc)
        pipeline_row.addStretch()
        ag_layout.addLayout(pipeline_row)

        classifier_row = QHBoxLayout()
        self._run_classifier_btn = QPushButton("Rebuild local classifier")
        self._run_classifier_btn.setObjectName("secondary-btn")
        self._run_classifier_btn.setFixedHeight(34)
        self._run_classifier_btn.clicked.connect(self._on_run_classifier)
        classifier_desc = QLabel("Retrain scikit-learn model from stored training examples")
        classifier_desc.setStyleSheet("color: #718096; font-size: 12px;")
        classifier_row.addWidget(self._run_classifier_btn)
        classifier_row.addWidget(classifier_desc)
        classifier_row.addStretch()
        ag_layout.addLayout(classifier_row)

        layout.addWidget(actions_group)

        refresh_btn = QPushButton("Refresh status")
        refresh_btn.setObjectName("secondary-btn")
        refresh_btn.setFixedWidth(130)
        refresh_btn.clicked.connect(self.load)
        layout.addWidget(refresh_btn)

        self._action_status = QLabel("")
        self._action_status.setStyleSheet("font-size: 12px; color: #38a169;")
        layout.addWidget(self._action_status)

        layout.addStretch()

    def load(self) -> None:
        self._status_label.setText("Loading…")
        self._worker = ApiWorker(self._client.get_training_status)
        self._worker.success.connect(self._on_status_loaded)
        self._worker.failure.connect(lambda msg: self._status_label.setText(f"Error: {msg}"))
        self._worker.start()

    def _on_status_loaded(self, data: dict) -> None:
        lines = []
        for key, val in data.items():
            lines.append(f"{key.replace('_', ' ').title()}: {val}")
        self._status_label.setText("\n".join(lines) if lines else "No status available.")

    def _on_run_pipeline(self) -> None:
        self._set_busy(True)
        self._action_status.setText("Running pipeline…")
        worker = ApiWorker(self._client.run_training_pipeline)
        worker.success.connect(self._on_pipeline_done)
        worker.failure.connect(self._on_action_error)
        worker.start()
        self._pipeline_worker = worker

    def _on_pipeline_done(self, result: dict) -> None:
        self._set_busy(False)
        processed = result.get("processed", "?")
        self._action_status.setText(f"Pipeline complete — {processed} examples processed.")
        self.load()

    def _on_run_classifier(self) -> None:
        self._set_busy(True)
        self._action_status.setText("Training classifier…")
        worker = ApiWorker(self._client.run_classifier_train)
        worker.success.connect(self._on_classifier_done)
        worker.failure.connect(self._on_action_error)
        worker.start()
        self._classifier_worker = worker

    def _on_classifier_done(self, result: dict) -> None:
        self._set_busy(False)
        accuracy = result.get("accuracy")
        msg = "Classifier trained."
        if accuracy is not None:
            msg += f"  Accuracy: {float(accuracy):.1%}"
        self._action_status.setText(msg)

    def _on_action_error(self, message: str) -> None:
        self._set_busy(False)
        self._action_status.setStyleSheet("font-size: 12px; color: #e53e3e;")
        self._action_status.setText(f"Error: {message}")

    def _set_busy(self, busy: bool) -> None:
        self._run_pipeline_btn.setEnabled(not busy)
        self._run_classifier_btn.setEnabled(not busy)
        if not busy:
            self._action_status.setStyleSheet("font-size: 12px; color: #38a169;")


class AdminPanel(QWidget):
    """Admin dashboard panel — stats, corrections, low-confidence, audit log, users, training.

    Loaded lazily when the user selects the Admin queue in the sidebar.
    """

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self._client = client
        self._worker: ApiWorker | None = None
        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Admin Dashboard")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #718096; font-size: 12px;")

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setObjectName("secondary-btn")
        self._refresh_btn.setFixedWidth(90)
        self._refresh_btn.clicked.connect(self.load)

        header.addWidget(title)
        header.addWidget(self._status_label)
        header.addStretch()
        header.addWidget(self._refresh_btn)
        root.addLayout(header)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self._card_emails = _StatCard("Total Emails")
        self._card_feedback = _StatCard("Feedback Submitted")
        self._card_users = _StatCard("Users")
        self._card_low_conf = _StatCard("Low Confidence")
        for card in (self._card_emails, self._card_feedback, self._card_users, self._card_low_conf):
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            card.setStyleSheet(
                "QWidget#stat-card { background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 6px; }"
                "QLabel#stat-value { font-size: 28px; font-weight: bold; color: #2d3748; }"
                "QLabel#stat-title { font-size: 11px; color: #718096; }"
            )
            stats_row.addWidget(card)
        root.addLayout(stats_row)

        self._tabs = QTabWidget()
        self._tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._corrections_placeholder = QLabel("Loading…")
        self._corrections_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tabs.addTab(self._corrections_placeholder, "Corrections")

        self._low_conf_placeholder = QLabel("Loading…")
        self._low_conf_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tabs.addTab(self._low_conf_placeholder, "Low Confidence")

        self._audit_placeholder = QLabel("Loading…")
        self._audit_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tabs.addTab(self._audit_placeholder, "Audit Log")

        self._users_tab = _UsersTab(self._client)
        self._tabs.addTab(self._users_tab, "Users")

        self._training_tab = _TrainingTab(self._client)
        self._tabs.addTab(self._training_tab, "Training")

        root.addWidget(self._tabs)

    # ── Public API ─────────────────────────────────────────────────────────────

    def load(self) -> None:
        self._refresh_btn.setEnabled(False)
        self._status_label.setText("Loading…")
        self._worker = ApiWorker(self._client.get_admin_stats)
        self._worker.success.connect(self._on_loaded)
        self._worker.failure.connect(self._on_error)
        self._worker.start()
        self._users_tab.load()
        self._training_tab.load()

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _on_loaded(self, data: dict) -> None:
        self._refresh_btn.setEnabled(True)
        self._status_label.setText("")

        overview = data.get("overview") or {}
        self._card_emails.set_value(str(overview.get("total_emails", "—")))
        self._card_feedback.set_value(str(overview.get("total_feedback", "—")))
        self._card_users.set_value(str(overview.get("total_users", "—")))
        self._card_low_conf.set_value(str(overview.get("low_confidence_count", "—")))

        last_sync = overview.get("last_sync")
        if last_sync:
            ts = (last_sync.get("created_at") or "")[:16].replace("T", " ")
            src = last_sync.get("source", "")
            cnt = last_sync.get("fetched_count", "")
            self._status_label.setText(f"Last sync: {ts}  ·  {src}  ·  {cnt} fetched")

        corrections = data.get("corrections") or []
        self._tabs.removeTab(0)
        self._tabs.insertTab(0, _build_corrections_table(corrections), f"Corrections ({len(corrections)})")
        self._tabs.setCurrentIndex(0)

        low_conf = data.get("low_confidence") or []
        self._tabs.removeTab(1)
        self._tabs.insertTab(1, _build_low_confidence_table(low_conf), f"Low Confidence ({len(low_conf)})")

        audit = data.get("audit_logs") or []
        self._tabs.removeTab(2)
        self._tabs.insertTab(2, _build_audit_table(audit), f"Audit Log ({len(audit)})")

    def _on_error(self, message: str) -> None:
        self._refresh_btn.setEnabled(True)
        self._status_label.setText(f"Error: {message}")
