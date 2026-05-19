from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal

from replyright_core.models.email_models import Conversation, ConversationDetail
from replyright_core.models.user_models import Session


# ---------------------------------------------------------------------------
# Generic helper
# ---------------------------------------------------------------------------

def _run_in_thread(worker: QObject, parent_thread_holder: list) -> None:
    """Start a worker in a new QThread. Stores the thread in parent_thread_holder[0]."""
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    worker.error.connect(thread.quit)
    worker.error.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    parent_thread_holder.append(thread)
    thread.start()


# ---------------------------------------------------------------------------
# Auth worker
# ---------------------------------------------------------------------------

class AuthWorker(QObject):
    """Runs Supabase authentication off the main thread."""

    finished = Signal(object)   # Session | None
    error = Signal(str)

    def __init__(self, auth_service, email: str, password: str) -> None:
        super().__init__()
        self._auth = auth_service
        self._email = email
        self._password = password

    def run(self) -> None:
        try:
            session: Session | None = self._auth.authenticate(self._email, self._password)
            self.finished.emit(session)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Inbox list worker
# ---------------------------------------------------------------------------

class InboxWorker(QObject):
    """Loads conversation list from the local database off the main thread."""

    finished = Signal(list)   # list[Conversation]
    error = Signal(str)

    def __init__(self, inbox_service, queue: str = "inbox", limit: int = 200) -> None:
        super().__init__()
        self._inbox = inbox_service
        self._queue = queue
        self._limit = limit

    def run(self) -> None:
        try:
            conversations: list[Conversation] = self._inbox.list_conversations(
                queue=self._queue, limit=self._limit
            )
            self.finished.emit(conversations)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Conversation detail worker
# ---------------------------------------------------------------------------

class ConversationDetailWorker(QObject):
    """Loads full conversation detail off the main thread."""

    finished = Signal(object)   # ConversationDetail | None
    error = Signal(str)

    def __init__(self, inbox_service, conversation_id: str) -> None:
        super().__init__()
        self._inbox = inbox_service
        self._conversation_id = conversation_id

    def run(self) -> None:
        try:
            detail: ConversationDetail | None = self._inbox.get_conversation(
                self._conversation_id
            )
            self.finished.emit(detail)
        except Exception as exc:
            self.error.emit(str(exc))
