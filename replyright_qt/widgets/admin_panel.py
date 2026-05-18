from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
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


class AdminPanel(QWidget):
    """Admin dashboard panel — shows stats, corrections, low-confidence emails, audit log.

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

        # Header row
        header = QHBoxLayout()
        title = QLabel("Admin Dashboard")
        title.setObjectName("admin-title")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #718096; font-size: 12px;")

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setFixedWidth(90)
        self._refresh_btn.clicked.connect(self.load)

        header.addWidget(title)
        header.addWidget(self._status_label)
        header.addStretch()
        header.addWidget(self._refresh_btn)
        root.addLayout(header)

        # Stat cards row
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

        # Tabs
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

        root.addWidget(self._tabs)

    # ── Public API ─────────────────────────────────────────────────────────────

    def load(self) -> None:
        """Fetch admin stats from the API in a background thread."""
        self._refresh_btn.setEnabled(False)
        self._status_label.setText("Loading…")
        self._worker = ApiWorker(self._client.get_admin_stats)
        self._worker.success.connect(self._on_loaded)
        self._worker.failure.connect(self._on_error)
        self._worker.start()

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
        corrections_table = _build_corrections_table(corrections)
        self._tabs.insertTab(0, corrections_table, f"Corrections ({len(corrections)})")
        self._tabs.setCurrentIndex(0)

        low_conf = data.get("low_confidence") or []
        self._tabs.removeTab(1)
        low_conf_table = _build_low_confidence_table(low_conf)
        self._tabs.insertTab(1, low_conf_table, f"Low Confidence ({len(low_conf)})")

        audit = data.get("audit_logs") or []
        self._tabs.removeTab(2)
        audit_table = _build_audit_table(audit)
        self._tabs.insertTab(2, audit_table, f"Audit Log ({len(audit)})")

    def _on_error(self, message: str) -> None:
        self._refresh_btn.setEnabled(True)
        self._status_label.setText(f"Error: {message}")
