from __future__ import annotations

import textwrap
from datetime import datetime, timezone

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


def _fmt_time(iso: str) -> str:
    """Format an ISO datetime string to a short relative label."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - dt
        if delta.days == 0:
            return dt.strftime("%H:%M")
        if delta.days == 1:
            return "Yesterday"
        if delta.days < 7:
            return dt.strftime("%a")
        return dt.strftime("%b %d")
    except Exception:
        return ""


def _urgency_label(priority: int | str | None) -> str:
    try:
        p = int(priority or 0)
    except (ValueError, TypeError):
        return ""
    labels = {1: "Low", 2: "Routine", 3: "Moderate", 4: "High", 5: "Critical"}
    return labels.get(p, "")


class ConversationRow(QWidget):
    """Custom widget rendered inside each QListWidgetItem."""

    def __init__(self, email: dict) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(3)

        triage = email.get("analysis") or {}
        priority = triage.get("priority_level") or triage.get("urgency")
        urgency_str = _urgency_label(priority)
        time_str = _fmt_time(email.get("received_datetime", ""))

        top_row = QWidget()
        top_layout = QVBoxLayout(top_row)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)

        sender = QLabel(email.get("sender_name") or email.get("sender_email", "Unknown"))
        sender.setStyleSheet("font-weight: bold; font-size: 13px;")

        subject = QLabel(textwrap.shorten(email.get("subject", "(no subject)"), width=60, placeholder="…"))
        subject.setStyleSheet("font-size: 12px; color: #4a5568;")

        meta_parts = []
        if urgency_str:
            meta_parts.append(urgency_str)
        if time_str:
            meta_parts.append(time_str)
        category = triage.get("category", "")
        if category:
            meta_parts.append(category.replace("_", " ").title())

        meta = QLabel("  ·  ".join(meta_parts))
        meta.setStyleSheet("font-size: 11px; color: #718096;")

        layout.addWidget(sender)
        layout.addWidget(subject)
        layout.addWidget(meta)


class ConversationListWidget(QWidget):
    """Scrollable list of email conversations for the current queue."""

    conversation_selected = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("list-panel")
        self._email_ids: list[str] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._list = QListWidget()
        self._list.setUniformItemSizes(False)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._list.currentRowChanged.connect(self._on_row_changed)

        self._empty_label = QLabel("No emails in this queue.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #a0aec0; font-size: 13px;")
        self._empty_label.hide()

        layout.addWidget(self._list)
        layout.addWidget(self._empty_label)

    def populate(self, emails: list[dict]) -> None:
        self._list.clear()
        self._email_ids = []

        if not emails:
            self._list.hide()
            self._empty_label.show()
            return

        self._empty_label.hide()
        self._list.show()

        for email in emails:
            email_id = email.get("id") or email.get("email_id", "")
            self._email_ids.append(email_id)

            item = QListWidgetItem()
            row_widget = ConversationRow(email)
            item.setSizeHint(row_widget.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, row_widget)

    def set_loading(self, loading: bool) -> None:
        self._list.setEnabled(not loading)

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < len(self._email_ids):
            self.conversation_selected.emit(self._email_ids[row])

    def clear(self) -> None:
        self._list.clear()
        self._email_ids = []
