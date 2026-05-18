from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)


class FilterBar(QWidget):
    """Horizontal bar with search box, category/status dropdowns, and sync button."""

    filters_changed = Signal(dict)
    sync_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("filter-bar")
        self.setFixedHeight(46)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        self._search = QLineEdit()
        self._search.setObjectName("search-box")
        self._search.setPlaceholderText("Search…")
        self._search.setFixedHeight(28)
        self._search.textChanged.connect(self._emit)

        self._category = QComboBox()
        self._category.setObjectName("filter-combo")
        self._category.setFixedHeight(28)
        self._category.addItem("All categories", "")
        self._category.currentIndexChanged.connect(self._emit)

        self._status = QComboBox()
        self._status.setObjectName("filter-combo")
        self._status.setFixedHeight(28)
        self._status.addItem("All statuses", "")
        for s in ("new", "in_progress", "resolved", "escalated"):
            self._status.addItem(s.replace("_", " ").title(), s)
        self._status.currentIndexChanged.connect(self._emit)

        self._risk = QComboBox()
        self._risk.setObjectName("filter-combo")
        self._risk.setFixedHeight(28)
        self._risk.addItem("All risks", "")
        for r in ("low", "medium", "high", "critical"):
            self._risk.addItem(r.title(), r)
        self._risk.currentIndexChanged.connect(self._emit)

        sync_btn = QPushButton("Sync")
        sync_btn.setObjectName("secondary-btn")
        sync_btn.setFixedHeight(28)
        sync_btn.clicked.connect(self.sync_requested)

        layout.addWidget(self._search, stretch=2)
        layout.addWidget(QLabel("Category:"))
        layout.addWidget(self._category, stretch=1)
        layout.addWidget(QLabel("Status:"))
        layout.addWidget(self._status, stretch=1)
        layout.addWidget(QLabel("Risk:"))
        layout.addWidget(self._risk, stretch=1)
        layout.addWidget(sync_btn)

    def populate_categories(self, categories: list[str]) -> None:
        self._category.blockSignals(True)
        current = self._category.currentData()
        self._category.clear()
        self._category.addItem("All categories", "")
        for cat in categories:
            self._category.addItem(cat.replace("_", " ").title(), cat)
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

    def _emit(self) -> None:
        self.filters_changed.emit(self.current_filters())
