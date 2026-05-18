from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class SqliteAdapterProtocol(Protocol):
    """Read-only query interface over the local hotel_email_triage.sqlite3 database."""

    def fetch_conversations(
        self,
        queue: str,
        limit: int,
        offset: int,
    ) -> list[dict]:
        """Return rows from the conversations view as plain dicts."""
        ...

    def fetch_conversation_detail(self, conversation_id: str) -> dict | None:
        """Return conversation header dict or None."""
        ...

    def fetch_messages(self, conversation_id: str) -> list[dict]:
        """Return message rows for a conversation, oldest first."""
        ...

    def fetch_queue_counts(self) -> dict[str, int]:
        """Return {queue_name: unresolved_count} from the local db."""
        ...

    @property
    def db_path(self) -> Path:
        """Absolute path to the SQLite database file."""
        ...
