from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from outlook_dashboard.taxonomy import RISK_FLAGS, STATUSES
from replyright_qt.display_labels import display_label


class FilterBar(QWidget):
    """Search bar, filters, and Outlook refresh action."""

    filters_changed = Signal(dict)
    sync_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("filter-bar")
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(6)

        # Row 1: search + refresh button
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self._search = QLineEdit()
        self._search.setObjectName("search-box")
        self._search.setPlaceholderText("Search sender, subject, or preview")
        self._search.setFixedHeight(34)
        self._search.textChanged.connect(self._emit)

        # Refresh + "Updated just now" stacked vertically on the right
        refresh_col = QVBoxLayout()
        refresh_col.setSpacing(2)
        refresh_col.setContentsMargins(0, 0, 0, 0)

        self._sync_btn = QPushButton("⟳  Refresh")
        self._sync_btn.setObjectName("primary-btn")
        self._sync_btn.setFixedHeight(34)
        self._sync_btn.setFixedWidth(110)
        self._sync_btn.clicked.connect(self.sync_requested)

        self._status_label = QLabel("Updated just now")
        self._status_label.setObjectName("sync-status-lbl")

        refresh_col.addWidget(self._sync_btn)
        refresh_col.addWidget(self._status_label)

        top_row.addWidget(self._search, stretch=1)
        top_row.addLayout(refresh_col)

        # Row 2: category / status / risk + more filters
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)

        self._category = QComboBox()
        self._category.setObjectName("filter-combo")
        self._category.setFixedHeight(30)
        self._category.addItem("All categories", "")
        self._category.currentIndexChanged.connect(self._emit)

        self._status = QComboBox()
        self._status.setObjectName("filter-combo")
        self._status.setFixedHeight(30)
        self._status.addItem("All statuses", "")
        for status in STATUSES:
            self._status.addItem(display_label(status), status)
        self._status.currentIndexChanged.connect(self._emit)

        self._risk = QComboBox()
        self._risk.setObjectName("filter-combo")
        self._risk.setFixedHeight(30)
        self._risk.addItem("All risks", "")
        for risk in RISK_FLAGS:
            self._risk.addItem(display_label(risk), risk)
        self._risk.currentIndexChanged.connect(self._emit)

        more_btn = QPushButton("More filters")
        more_btn.setObjectName("secondary-btn")
        more_btn.setFixedHeight(30)

        filter_row.addWidget(self._category, stretch=1)
        filter_row.addWidget(self._status, stretch=1)
        filter_row.addWidget(self._risk, stretch=1)
        filter_row.addWidget(more_btn)

        root.addLayout(top_row)
        root.addLayout(filter_row)

    def populate_categories(self, categories: list[str]) -> None:
        self._category.blockSignals(True)
        current = self._category.currentData()
        self._category.clear()
        self._category.addItem("All categories", "")
        for category in categories:
            self._category.addItem(display_label(category), category)
        idx = self._category.findData(current)
        if idx >= 0:
            self._category.setCurrentIndex(idx)
        self._category.blockSignals(False)

    def current_filters(self) -> dict:
        return {
            "q": self._search.text().strip(),
            "category": self._category.currentData() or "",
            "status": self._status.currentData() or "",
            "risk": self._risk.currentData() or "",
        }

    def set_syncing(self, syncing: bool, message: str = "") -> None:
        self._sync_btn.setEnabled(not syncing)
        self._sync_btn.setText("Refreshing..." if syncing else "⟳  Refresh")
        self._status_label.setText(message or ("Syncing Outlook..." if syncing else "Updated just now"))

    def _emit(self) -> None:
        self.filters_changed.emit(self.current_filters())
