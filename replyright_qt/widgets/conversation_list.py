from __future__ import annotations

from PySide6.QtWidgets import QListWidget, QListWidgetItem, QWidget, QVBoxLayout
from PySide6.QtCore import Signal

from replyright_core.models.email_models import Conversation


class ConversationListWidget(QWidget):
    """Scrollable list of conversations for a single queue tab.

    Native PySide6 widget wired for conversation selection.
    """
    conversation_selected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_item_changed)
        layout.addWidget(self._list)

    def populate(self, conversations: list[Conversation]) -> None:
        self._list.clear()
        for conv in conversations:
            label = f"{conv.latest_sender_email} — {conv.subject}"
            self._list.addItem(QListWidgetItem(label))
            
    def add_scaffold_items(self, items: list[str]) -> None:
        """Temporary method for scaffold data."""
        self._list.clear()
        self._list.addItems(items)

    def clear(self) -> None:
        self._list.clear()

    def _on_item_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        if current:
            self.conversation_selected.emit(current.text())
