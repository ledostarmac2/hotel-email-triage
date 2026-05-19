from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from replyright_core.models.email_models import (
    Conversation,
    ConversationDetail,
    EmailMessage,
    TriageResult,
)

# Queue name -> SQL WHERE clause fragment (applied to email status column)
_QUEUE_FILTERS: dict[str, str] = {
    "inbox": "e.status IN ('New', 'Reviewed', 'Escalated')",
    "drafting": "e.status = 'Drafted'",
    "completed": "e.status = 'Completed'",
    "all": "1=1",
}


def _decode_json_list(value: object) -> list:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        decoded = json.loads(str(value))
        return decoded if isinstance(decoded, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def _row_to_triage(row: sqlite3.Row) -> TriageResult | None:
    keys = row.keys()
    if "category" not in keys or not row["category"]:
        return None
    risk_flags = tuple(_decode_json_list(row["risk_flags"] if "risk_flags" in keys else None))
    return TriageResult(
        category=row["category"] or "General inquiry",
        urgency=row["priority_level"] or "Normal",
        contact_type=row["contact_type"] or "",
        sentiment=row["guest_sentiment"] or "Neutral",
        confidence=float(row["confidence_score"] or 0) if "confidence_score" in keys else 0.0,
        ai_draft=row["suggested_reply_draft"] or "" if "suggested_reply_draft" in keys else "",
        risk_flags=risk_flags,
    )


def _row_to_message(row: sqlite3.Row) -> EmailMessage:
    return EmailMessage(
        message_id=str(row["graph_message_id"] or row["id"]),
        sender_email=row["sender_email"] or row["from_email"] or "",
        sender_name=row["sender_name"] or row["from_name"] or "",
        subject=row["subject"] or "(no subject)",
        body_preview=row["body_preview"] or "",
        received_at=row["received_datetime"] or "",
        is_read=bool(row["status"] != "New") if "status" in row.keys() else False,
    )


class SqliteInboxAdapter:
    """InboxServiceProtocol backed by the local hotel_email_triage.sqlite3 database."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def list_conversations(
        self,
        queue: str = "inbox",
        limit: int = 100,
        offset: int = 0,
    ) -> list[Conversation]:
        where = _QUEUE_FILTERS.get(queue, _QUEUE_FILTERS["inbox"])
        query = f"""
            WITH latest AS (
                SELECT
                    COALESCE(conversation_id, graph_message_id) AS conv_id,
                    MAX(id) AS latest_id,
                    COUNT(*) AS message_count
                FROM emails
                GROUP BY conv_id
            )
            SELECT
                l.conv_id           AS conversation_id,
                e.subject,
                COALESCE(e.sender_email, e.from_email, '') AS latest_sender_email,
                e.received_datetime AS latest_received_at,
                l.message_count,
                e.status,
                a.category,
                a.priority_level,
                a.guest_sentiment,
                a.contact_type,
                a.risk_flags,
                a.suggested_reply_draft,
                a.confidence_score
            FROM latest l
            JOIN emails e ON e.id = l.latest_id
            LEFT JOIN email_analysis a ON a.email_id = e.id
            WHERE {where}
            ORDER BY e.received_datetime DESC
            LIMIT ? OFFSET ?
        """
        with self._connect() as conn:
            rows = conn.execute(query, (limit, offset)).fetchall()

        result: list[Conversation] = []
        for row in rows:
            triage = _row_to_triage(row)
            result.append(
                Conversation(
                    conversation_id=str(row["conversation_id"] or ""),
                    subject=row["subject"] or "(no subject)",
                    latest_sender_email=row["latest_sender_email"] or "",
                    latest_received_at=row["latest_received_at"] or "",
                    message_count=int(row["message_count"] or 1),
                    status=row["status"] or "New",
                    triage=triage,
                    queue=queue,
                )
            )
        return result

    def get_conversation(self, conversation_id: str) -> ConversationDetail | None:
        if not conversation_id:
            return None

        # Fetch all messages in the conversation thread
        msg_query = """
            SELECT e.*, a.category, a.priority_level, a.guest_sentiment,
                   a.contact_type, a.risk_flags, a.suggested_reply_draft,
                   a.ai_summary, a.confidence_score
            FROM emails e
            LEFT JOIN email_analysis a ON a.email_id = e.id
            WHERE COALESCE(e.conversation_id, e.graph_message_id) = ?
            ORDER BY e.received_datetime ASC, e.id ASC
        """
        with self._connect() as conn:
            rows = conn.execute(msg_query, (conversation_id,)).fetchall()

        if not rows:
            return None

        messages = [_row_to_message(r) for r in rows]

        # Build the Conversation header from the latest (last) message row
        latest_row = rows[-1]
        triage = _row_to_triage(latest_row)

        # Use AI summary from the most-analysed row (first one with a summary)
        thread_summary = ""
        for r in reversed(rows):
            summary = r["ai_summary"] if "ai_summary" in r.keys() else None
            if summary:
                thread_summary = summary
                break

        conv = Conversation(
            conversation_id=conversation_id,
            subject=latest_row["subject"] or "(no subject)",
            latest_sender_email=(
                latest_row["sender_email"] or latest_row["from_email"] or ""
            ),
            latest_received_at=latest_row["received_datetime"] or "",
            message_count=len(messages),
            status=latest_row["status"] or "New",
            triage=triage,
        )
        return ConversationDetail(
            conversation=conv,
            messages=messages,
            thread_summary=thread_summary,
        )

    def get_queue_counts(self) -> dict[str, int]:
        query = """
            SELECT status, COUNT(DISTINCT COALESCE(conversation_id, graph_message_id)) AS cnt
            FROM emails
            GROUP BY status
        """
        with self._connect() as conn:
            rows = conn.execute(query).fetchall()

        raw: dict[str, int] = {r["status"]: int(r["cnt"]) for r in rows}
        return {
            "inbox": sum(raw.get(s, 0) for s in ("New", "Reviewed", "Escalated")),
            "drafting": raw.get("Drafted", 0),
            "completed": raw.get("Completed", 0),
        }

    def mark_reviewed(self, conversation_id: str, reviewer_email: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE emails SET status = 'Reviewed', updated_at = datetime('now')
                WHERE COALESCE(conversation_id, graph_message_id) = ?
                  AND status = 'New'
                """,
                (conversation_id,),
            )
            conn.commit()
