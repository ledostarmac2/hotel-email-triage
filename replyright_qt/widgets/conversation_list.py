from __future__ import annotations

# PySide6 is not yet in production requirements.
# This scaffold compiles and imports without PySide6 installed.
try:
    from PySide6.QtWidgets import QListWidget, QListWidgetItem, QWidget
    _PYSIDE6 = True
except ImportError:
    QWidget = object  # type: ignore[assignment,misc]
    _PYSIDE6 = False

from replyright_core.models.email_models import Conversation


class ConversationListWidget(QWidget):  # type: ignore[misc]
    """Scrollable list of conversations for a single queue tab.

    Scaffold only — not yet wired to a viewmodel or selection signal.
    """

    def __init__(self) -> None:
        if not _PYSIDE6:
            raise RuntimeError(
                "ConversationListWidget requires PySide6. "
                "Add PySide6 to requirements when the native slice is ready."
            )
        super().__init__()
        self._list = QListWidget()  # type: ignore[call-arg]

    def populate(self, conversations: list[Conversation]) -> None:
        self._list.clear()  # type: ignore[attr-defined]
        for conv in conversations:
            label = f"{conv.latest_sender_email} — {conv.subject}"
            self._list.addItem(QListWidgetItem(label))  # type: ignore[call-arg]

    def clear(self) -> None:
        self._list.clear()  # type: ignore[attr-defined]
