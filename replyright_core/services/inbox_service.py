from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models.email_models import Conversation, ConversationDetail


@runtime_checkable
class InboxServiceProtocol(Protocol):
    def list_conversations(
        self,
        queue: str = "inbox",
        limit: int = 100,
        offset: int = 0,
    ) -> list[Conversation]:
        """Return conversations for the given queue, most-recent first."""
        ...

    def get_conversation(self, conversation_id: str) -> ConversationDetail | None:
        """Return the full conversation detail including messages, or None."""
        ...

    def get_queue_counts(self) -> dict[str, int]:
        """Return unresolved count per queue name."""
        ...

    def mark_reviewed(self, conversation_id: str, reviewer_email: str) -> None:
        """Record a human-reviewed status update. Read-only Outlook posture preserved."""
        ...
