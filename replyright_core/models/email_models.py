from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EmailMessage:
    message_id: str
    sender_email: str
    sender_name: str
    subject: str
    body_preview: str
    received_at: str
    is_read: bool = False


@dataclass(frozen=True)
class TriageResult:
    category: str
    urgency: str
    contact_type: str
    sentiment: str
    confidence: float = 0.0
    ai_draft: str = ""
    risk_flags: tuple[str, ...] = ()


@dataclass
class Conversation:
    conversation_id: str
    subject: str
    latest_sender_email: str
    latest_received_at: str
    message_count: int
    status: str
    triage: TriageResult | None = None
    owner: str = ""
    queue: str = "inbox"


@dataclass
class ConversationDetail:
    conversation: Conversation
    messages: list[EmailMessage] = field(default_factory=list)
    thread_summary: str = ""
