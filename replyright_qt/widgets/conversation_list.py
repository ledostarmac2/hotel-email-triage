from __future__ import annotations

import textwrap
from datetime import datetime, timezone

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


def _fmt_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - dt
        if delta.days == 0:
            local = dt.astimezone()
            return local.strftime("%I:%M %p").lstrip("0")
        if delta.days == 1:
            return "Yesterday"
        if delta.days < 7:
            return dt.strftime("%a")
        return dt.strftime("%b %d")
    except Exception:
        return ""


def _urgency_value(email: dict) -> int:
    triage = email.get("analysis") or {}
    value = email.get("urgency_score") or email.get("priority_level") or triage.get("priority_level")
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


class ConversationRow(QWidget):
    """A single email row: avatar + content + right-side meta."""

    def __init__(self, email: dict) -> None:
        super().__init__()
        self.setObjectName("conversation-row")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(10)

        triage = email.get("analysis") or {}
        priority = _urgency_value(email)
        time_str = _fmt_time(email.get("received_datetime", ""))

        # Avatar
        sender_name = email.get("sender_name") or email.get("sender_email", "Unknown")
        parts = str(sender_name).replace(".", " ").replace("_", " ").split()
        initials = "".join(p[:1] for p in parts[:2]).upper() or "?"
        avatar = QLabel(initials[:2])
        avatar.setObjectName("avatar")
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFixedSize(QSize(36, 36))

        # Center content column
        content_col = QVBoxLayout()
        content_col.setContentsMargins(0, 0, 0, 0)
        content_col.setSpacing(2)

        sender = QLabel(sender_name)
        sender.setObjectName("row-sender")
        sender.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        subject = QLabel(textwrap.shorten(email.get("subject", "(no subject)"), width=70, placeholder="..."))
        subject.setObjectName("row-subject")

        content_col.addWidget(sender)
        content_col.addWidget(subject)

        preview = email.get("ai_summary") or email.get("body_preview") or ""
        if preview:
            summary = QLabel(textwrap.shorten(preview, width=110, placeholder="..."))
            summary.setObjectName("row-preview")
            summary.setWordWrap(True)
            content_col.addWidget(summary)

        # Category chips
        category = email.get("category") or triage.get("category", "")
        contact = email.get("contact_type") or triage.get("contact_type", "")
        chip_texts = [t.replace("_", " ").title() for t in (category, contact) if t]
        if chip_texts:
            chips_row = QHBoxLayout()
            chips_row.setContentsMargins(0, 3, 0, 0)
            chips_row.setSpacing(5)
            for text in chip_texts[:3]:
                chip = QLabel(text)
                chip.setObjectName("row-chip")
                chips_row.addWidget(chip)
            chips_row.addStretch()
            content_col.addLayout(chips_row)

        # Right column: time, urgency badge, unread dot
        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(4)

        if time_str:
            time_lbl = QLabel(time_str)
            time_lbl.setObjectName("row-time")
            time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            right_col.addWidget(time_lbl)

        if priority:
            badge = QLabel(f"U{priority}")
            badge.setObjectName(f"badge-urgency-{min(max(priority, 1), 5)}")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedSize(QSize(30, 22))
            right_col.addWidget(badge, alignment=Qt.AlignmentFlag.AlignRight)

        if not email.get("is_read", True):
            dot = QLabel("")
            dot.setObjectName("unread-dot")
            dot.setFixedSize(10, 10)
            right_col.addWidget(dot, alignment=Qt.AlignmentFlag.AlignRight)

        right_col.addStretch()

        outer.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)
        outer.addLayout(content_col, stretch=1)
        outer.addLayout(right_col)


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

        # Count + sort header bar
        self._list_header = QWidget()
        self._list_header.setObjectName("list-header")
        header_row = QHBoxLayout(self._list_header)
        header_row.setContentsMargins(14, 6, 14, 6)
        header_row.setSpacing(8)

        self._count_lbl = QLabel("0 messages")
        self._count_lbl.setObjectName("list-count-lbl")

        sort_combo = QComboBox()
        sort_combo.setObjectName("sort-combo")
        sort_combo.addItem("Newest")
        sort_combo.addItem("Oldest")
        sort_combo.setFixedHeight(26)
        sort_combo.setFixedWidth(90)

        header_row.addWidget(self._count_lbl, stretch=1)
        header_row.addWidget(sort_combo)

        self._list = QListWidget()
        self._list.setUniformItemSizes(False)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.currentRowChanged.connect(self._on_row_changed)

        self._empty_label = QLabel("No conversations match this view.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #a0aec0; font-size: 13px;")
        self._empty_label.hide()

        layout.addWidget(self._list_header)
        layout.addWidget(self._list)
        layout.addWidget(self._empty_label)

    def populate(self, emails: list[dict]) -> None:
        self._list.clear()
        self._email_ids = []

        count = len(emails)
        self._count_lbl.setText(f"{count} message{'s' if count != 1 else ''}")

        if not emails:
            self._list.hide()
            self._empty_label.show()
            return

        self._empty_label.hide()
        self._list.show()

        for email in emails:
            email_id = str(email.get("id") or email.get("email_id", ""))
            self._email_ids.append(email_id)
            item = QListWidgetItem()
            row_widget = ConversationRow(email)
            item.setSizeHint(row_widget.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, row_widget)
        self._list.setCurrentRow(0)
        self._sync_row_selection(0)

    def set_loading(self, loading: bool) -> None:
        self._list.setEnabled(not loading)
        if loading:
            self._empty_label.setText("Loading conversations...")
            self._empty_label.show()
            self._count_lbl.setText("Loading...")
        else:
            self._empty_label.setText("No conversations match this view.")

    def _on_row_changed(self, row: int) -> None:
        self._sync_row_selection(row)
        if 0 <= row < len(self._email_ids):
            self.conversation_selected.emit(self._email_ids[row])

    def _sync_row_selection(self, selected_row: int) -> None:
        for idx in range(self._list.count()):
            item = self._list.item(idx)
            widget = self._list.itemWidget(item)
            if not widget:
                continue
            widget.setProperty("selected", "true" if idx == selected_row else "false")
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def clear(self) -> None:
        self._list.clear()
        self._email_ids = []
