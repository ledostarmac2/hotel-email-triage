from __future__ import annotations

from dataclasses import dataclass, field

from replyright_core.models.email_models import Conversation


@dataclass
class InboxViewModel:
    """Presentation state for the inbox conversation list.

    Scaffold only — not yet connected to a real InboxServiceProtocol.
    Signal/slot wiring belongs in the concrete Qt layer; this class
    stays framework-neutral so it can be unit-tested without PySide6.
    """

    queue: str = "inbox"
    conversations: list[Conversation] = field(default_factory=list)
    selected_id: str = ""
    loading: bool = False
    error_message: str = ""

    @property
    def selected_conversation(self) -> Conversation | None:
        for c in self.conversations:
            if c.conversation_id == self.selected_id:
                return c
        return None

    def apply_conversations(self, rows: list[Conversation]) -> None:
        self.conversations = rows
        self.loading = False
        self.error_message = ""

    def apply_error(self, message: str) -> None:
        self.loading = False
        self.error_message = message

    def select(self, conversation_id: str) -> None:
        self.selected_id = conversation_id
