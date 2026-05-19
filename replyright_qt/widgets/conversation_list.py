from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from replyright_core.models.email_models import Conversation


class ConversationListWidget(QWidget):
    """Scrollable list of conversations — emits conversation_id on selection."""

    conversation_selected = Signal(str)   # conversation_id

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_item_changed)
        layout.addWidget(self._list)

        # conversation_id -> Conversation lookup
        self._id_map: dict[str, Conversation] = {}

    def populate(self, conversations: list[Conversation]) -> None:
        self._list.clear()
        self._id_map = {}
        for conv in conversations:
            urgency = ""
            if conv.triage:
                urgency = f"[{conv.triage.urgency}] "
            label = f"{urgency}{conv.subject}  ·  {conv.latest_sender_email}"
            item = QListWidgetItem(label)
            item.setData(256, conv.conversation_id)   # Qt.UserRole = 256
            self._list.addItem(item)
            self._id_map[conv.conversation_id] = conv

    def add_scaffold_items(self, items: list[str]) -> None:
        """Temporary scaffold helper — populate() is preferred for real data."""
        self._list.clear()
        self._id_map = {}
        for text in items:
            item = QListWidgetItem(text)
            item.setData(256, text)
            self._list.addItem(item)

    def clear(self) -> None:
        self._list.clear()
        self._id_map = {}

    def _on_item_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        if current:
            conversation_id = current.data(256)
            self.conversation_selected.emit(str(conversation_id or ""))
