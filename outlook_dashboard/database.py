from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import get_settings
from .taxonomy import STATUSES
from .text_utils import utc_now_iso


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or get_settings().database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def managed_connect(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    connection = connect(db_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(db_path: Path | None = None) -> None:
    with managed_connect(db_path) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                graph_message_id TEXT NOT NULL UNIQUE,
                subject TEXT,
                sender_name TEXT,
                sender_email TEXT,
                from_name TEXT,
                from_email TEXT,
                received_datetime TEXT,
                body_preview TEXT,
                body_content_type TEXT,
                body_content TEXT,
                body_text TEXT,
                conversation_id TEXT,
                importance TEXT,
                has_attachments INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT 'outlook',
                mailbox_mode TEXT NOT NULL DEFAULT 'shared',
                status TEXT NOT NULL DEFAULT 'New',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS email_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER NOT NULL UNIQUE,
                ai_summary TEXT,
                category TEXT,
                priority_level TEXT,
                guest_sentiment TEXT,
                internal_next_steps TEXT,
                missing_information TEXT,
                risk_flags TEXT,
                recommended_department_owner TEXT,
                contact_type TEXT,
                suggested_reply_draft TEXT,
                model TEXT,
                analysis_engine TEXT,
                analysis_error TEXT,
                redaction_counts TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(email_id) REFERENCES emails(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS oauth_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                mailbox_mode TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                expires_at INTEGER NOT NULL,
                scopes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(provider, mailbox_mode, tenant_id)
            );

            CREATE TABLE IF NOT EXISTS oauth_states (
                state TEXT PRIMARY KEY,
                mailbox_mode TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                mailbox_mode TEXT NOT NULL,
                fetched_count INTEGER NOT NULL DEFAULT 0,
                inserted_count INTEGER NOT NULL DEFAULT 0,
                updated_count INTEGER NOT NULL DEFAULT 0,
                analyzed_count INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS triage_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                email_id INTEGER,
                feedback_text TEXT NOT NULL,
                corrected_urgency INTEGER,
                corrected_category TEXT,
                corrected_owner TEXT,
                corrected_contact_type TEXT,
                corrected_sentiment TEXT,
                applied_short_term INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY(email_id) REFERENCES emails(id) ON DELETE SET NULL
            );
            """
        )
        _ensure_column(db, "email_analysis", "contact_type", "TEXT")


def _ensure_column(db: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    for key in ("internal_next_steps", "missing_information", "risk_flags", "redaction_counts"):
        if key in data:
            data[key] = _decode_json(data[key])
    return data


def _decode_json(value: Any) -> Any:
    if value in (None, ""):
        return [] if value != "{}" else {}
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def _encode_json(value: Any) -> str:
    if value is None:
        value = []
    return json.dumps(value, ensure_ascii=True)


def email_count(db_path: Path | None = None) -> int:
    with managed_connect(db_path) as db:
        return int(db.execute("SELECT COUNT(*) FROM emails").fetchone()[0])


def upsert_email(email: dict[str, Any], db_path: Path | None = None) -> tuple[int, bool]:
    now = utc_now_iso()
    with managed_connect(db_path) as db:
        existing = db.execute(
            "SELECT id FROM emails WHERE graph_message_id = ?",
            (email["graph_message_id"],),
        ).fetchone()
        values = (
            email.get("subject"),
            email.get("sender_name"),
            email.get("sender_email"),
            email.get("from_name"),
            email.get("from_email"),
            email.get("received_datetime"),
            email.get("body_preview"),
            email.get("body_content_type"),
            email.get("body_content"),
            email.get("body_text"),
            email.get("conversation_id"),
            email.get("importance"),
            1 if email.get("has_attachments") else 0,
            email.get("source", "outlook"),
            email.get("mailbox_mode", "shared"),
            now,
        )
        if existing:
            db.execute(
                """
                UPDATE emails
                SET subject = ?, sender_name = ?, sender_email = ?, from_name = ?,
                    from_email = ?, received_datetime = ?, body_preview = ?,
                    body_content_type = ?, body_content = ?, body_text = ?,
                    conversation_id = ?, importance = ?, has_attachments = ?,
                    source = ?, mailbox_mode = ?, updated_at = ?
                WHERE id = ?
                """,
                values + (existing["id"],),
            )
            return int(existing["id"]), False

        cursor = db.execute(
            """
            INSERT INTO emails (
                graph_message_id, subject, sender_name, sender_email, from_name,
                from_email, received_datetime, body_preview, body_content_type,
                body_content, body_text, conversation_id, importance,
                has_attachments, source, mailbox_mode, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'New', ?, ?)
            """,
            (email["graph_message_id"],) + values[:-1] + (now, now),
        )
        return int(cursor.lastrowid), True


def save_analysis(email_id: int, analysis: dict[str, Any], db_path: Path | None = None) -> None:
    now = utc_now_iso()
    values = (
        email_id,
        analysis.get("ai_summary", ""),
        analysis.get("category", "General inquiry"),
        analysis.get("priority_level", "Normal"),
        analysis.get("guest_sentiment", "Neutral"),
        _encode_json(analysis.get("internal_next_steps", [])),
        _encode_json(analysis.get("missing_information", [])),
        _encode_json(analysis.get("risk_flags", [])),
        analysis.get("recommended_department_owner", "Reservations"),
        analysis.get("contact_type", "Direct guest"),
        analysis.get("suggested_reply_draft", ""),
        analysis.get("model", ""),
        analysis.get("analysis_engine", ""),
        analysis.get("analysis_error", ""),
        _encode_json(analysis.get("redaction_counts", {})),
        now,
        now,
    )
    with managed_connect(db_path) as db:
        existing = db.execute(
            "SELECT id FROM email_analysis WHERE email_id = ?",
            (email_id,),
        ).fetchone()
        if existing:
            db.execute(
                """
                UPDATE email_analysis
                SET ai_summary = ?, category = ?, priority_level = ?,
                    guest_sentiment = ?, internal_next_steps = ?,
                    missing_information = ?, risk_flags = ?,
                    recommended_department_owner = ?, contact_type = ?,
                    suggested_reply_draft = ?,
                    model = ?, analysis_engine = ?, analysis_error = ?,
                    redaction_counts = ?, updated_at = ?
                WHERE email_id = ?
                """,
                values[1:-2] + (now, email_id),
            )
            return
        db.execute(
            """
            INSERT INTO email_analysis (
                email_id, ai_summary, category, priority_level, guest_sentiment,
                internal_next_steps, missing_information, risk_flags,
                recommended_department_owner, contact_type, suggested_reply_draft, model,
                analysis_engine, analysis_error, redaction_counts, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )


def get_email(email_id: int, db_path: Path | None = None) -> dict[str, Any] | None:
    with managed_connect(db_path) as db:
        row = db.execute(
            """
            SELECT e.*, a.ai_summary, a.category, a.priority_level, a.guest_sentiment,
                   a.internal_next_steps, a.missing_information, a.risk_flags,
                   a.recommended_department_owner, a.contact_type, a.suggested_reply_draft,
                   a.model, a.analysis_engine, a.analysis_error, a.redaction_counts,
                   a.created_at AS analysis_created_at, a.updated_at AS analysis_updated_at
            FROM emails e
            LEFT JOIN email_analysis a ON a.email_id = e.id
            WHERE e.id = ?
            """,
            (email_id,),
        ).fetchone()
    return row_to_dict(row)


def list_emails(
    *,
    category: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    risk: str | None = None,
    query: str | None = None,
    limit: int = 100,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if category:
        clauses.append("a.category = ?")
        params.append(category)
    if priority:
        clauses.append("a.priority_level = ?")
        params.append(priority)
    if status:
        clauses.append("e.status = ?")
        params.append(status)
    if risk:
        clauses.append("a.risk_flags LIKE ?")
        params.append(f"%{risk}%")
    if query:
        clauses.append(
            "(e.subject LIKE ? OR e.sender_email LIKE ? OR e.sender_name LIKE ? OR e.body_preview LIKE ?)"
        )
        pattern = f"%{query}%"
        params.extend([pattern, pattern, pattern, pattern])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, min(limit, 500)))
    with managed_connect(db_path) as db:
        rows = db.execute(
            f"""
            SELECT e.id, e.graph_message_id, e.subject, e.sender_name, e.sender_email,
                   e.received_datetime, e.body_preview, e.importance, e.has_attachments,
                   e.source, e.mailbox_mode, e.status, a.ai_summary, a.category,
                   a.priority_level, a.guest_sentiment, a.internal_next_steps,
                   a.missing_information, a.risk_flags, a.recommended_department_owner,
                   a.contact_type, a.suggested_reply_draft, a.analysis_engine,
                   e.conversation_id
            FROM emails e
            LEFT JOIN email_analysis a ON a.email_id = e.id
            {where}
            ORDER BY e.received_datetime DESC, e.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [row_to_dict(row) or {} for row in rows]


def list_conversation_emails(conversation_id: str, db_path: Path | None = None) -> list[dict[str, Any]]:
    if not conversation_id:
        return []
    with managed_connect(db_path) as db:
        rows = db.execute(
            """
            SELECT e.*, a.ai_summary, a.category, a.priority_level, a.guest_sentiment,
                   a.internal_next_steps, a.missing_information, a.risk_flags,
                   a.recommended_department_owner, a.contact_type, a.suggested_reply_draft,
                   a.model, a.analysis_engine, a.analysis_error, a.redaction_counts,
                   a.created_at AS analysis_created_at, a.updated_at AS analysis_updated_at
            FROM emails e
            LEFT JOIN email_analysis a ON a.email_id = e.id
            WHERE e.conversation_id = ?
            ORDER BY e.received_datetime DESC, e.id DESC
            """,
            (conversation_id,),
        ).fetchall()
    return [row_to_dict(row) or {} for row in rows]


def delete_emails_not_in_graph_ids(
    graph_message_ids: list[str],
    db_path: Path | None = None,
) -> int:
    with managed_connect(db_path) as db:
        if not graph_message_ids:
            cursor = db.execute("DELETE FROM emails")
            return int(cursor.rowcount)

        db.execute("CREATE TEMP TABLE IF NOT EXISTS current_import_ids (graph_message_id TEXT PRIMARY KEY)")
        db.execute("DELETE FROM current_import_ids")
        db.executemany(
            "INSERT OR IGNORE INTO current_import_ids (graph_message_id) VALUES (?)",
            [(graph_message_id,) for graph_message_id in graph_message_ids],
        )
        cursor = db.execute(
            """
            DELETE FROM emails
            WHERE NOT EXISTS (
                SELECT 1
                FROM current_import_ids current
                WHERE current.graph_message_id = emails.graph_message_id
            )
            """
        )
        db.execute("DROP TABLE current_import_ids")
        return int(cursor.rowcount)


def save_triage_feedback(
    *,
    email_id: int,
    conversation_id: str | None,
    feedback_text: str,
    corrected_urgency: int | None = None,
    corrected_category: str | None = None,
    corrected_owner: str | None = None,
    corrected_contact_type: str | None = None,
    corrected_sentiment: str | None = None,
    db_path: Path | None = None,
) -> int:
    with managed_connect(db_path) as db:
        cursor = db.execute(
            """
            INSERT INTO triage_feedback (
                conversation_id, email_id, feedback_text, corrected_urgency,
                corrected_category, corrected_owner, corrected_contact_type,
                corrected_sentiment, applied_short_term, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                conversation_id,
                email_id,
                feedback_text.strip(),
                corrected_urgency,
                corrected_category,
                corrected_owner,
                corrected_contact_type,
                corrected_sentiment,
                utc_now_iso(),
            ),
        )
        return int(cursor.lastrowid)


def list_recent_triage_feedback(limit: int = 100, db_path: Path | None = None) -> list[dict[str, Any]]:
    with managed_connect(db_path) as db:
        rows = db.execute(
            """
            SELECT *
            FROM triage_feedback
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 500)),),
        ).fetchall()
    return [row_to_dict(row) or {} for row in rows]


def list_feedback_for_conversation(
    conversation_id: str,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    if not conversation_id:
        return []
    with managed_connect(db_path) as db:
        rows = db.execute(
            """
            SELECT *
            FROM triage_feedback
            WHERE conversation_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (conversation_id,),
        ).fetchall()
    return [row_to_dict(row) or {} for row in rows]


def emails_without_analysis(limit: int = 25, db_path: Path | None = None) -> list[dict[str, Any]]:
    with managed_connect(db_path) as db:
        rows = db.execute(
            """
            SELECT e.*
            FROM emails e
            LEFT JOIN email_analysis a ON a.email_id = e.id
            WHERE a.id IS NULL
            ORDER BY e.received_datetime DESC, e.id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        ).fetchall()
    return [row_to_dict(row) or {} for row in rows]


def update_status(email_id: int, status: str, db_path: Path | None = None) -> None:
    if status not in STATUSES:
        raise ValueError(f"Unsupported status: {status}")
    with managed_connect(db_path) as db:
        cursor = db.execute(
            "UPDATE emails SET status = ?, updated_at = ? WHERE id = ?",
            (status, utc_now_iso(), email_id),
        )
        if cursor.rowcount == 0:
            raise KeyError(email_id)


def save_oauth_state(state: str, mailbox_mode: str, db_path: Path | None = None) -> None:
    with managed_connect(db_path) as db:
        db.execute(
            "INSERT OR REPLACE INTO oauth_states (state, mailbox_mode, created_at) VALUES (?, ?, ?)",
            (state, mailbox_mode, utc_now_iso()),
        )


def consume_oauth_state(state: str, db_path: Path | None = None) -> str | None:
    with managed_connect(db_path) as db:
        row = db.execute(
            "SELECT mailbox_mode FROM oauth_states WHERE state = ?",
            (state,),
        ).fetchone()
        db.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
    return row["mailbox_mode"] if row else None


def save_oauth_token(
    *,
    mailbox_mode: str,
    tenant_id: str,
    access_token: str,
    refresh_token: str | None,
    expires_at: int,
    scopes: str,
    db_path: Path | None = None,
) -> None:
    now = utc_now_iso()
    with managed_connect(db_path) as db:
        db.execute(
            """
            INSERT INTO oauth_tokens (
                provider, mailbox_mode, tenant_id, access_token, refresh_token,
                expires_at, scopes, created_at, updated_at
            )
            VALUES ('microsoft', ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider, mailbox_mode, tenant_id)
            DO UPDATE SET
                access_token = excluded.access_token,
                refresh_token = COALESCE(excluded.refresh_token, oauth_tokens.refresh_token),
                expires_at = excluded.expires_at,
                scopes = excluded.scopes,
                updated_at = excluded.updated_at
            """,
            (mailbox_mode, tenant_id, access_token, refresh_token, expires_at, scopes, now, now),
        )


def get_oauth_token(
    mailbox_mode: str,
    tenant_id: str,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    with managed_connect(db_path) as db:
        row = db.execute(
            """
            SELECT * FROM oauth_tokens
            WHERE provider = 'microsoft' AND mailbox_mode = ? AND tenant_id = ?
            """,
            (mailbox_mode, tenant_id),
        ).fetchone()
    return row_to_dict(row)


def record_sync_run(
    *,
    source: str,
    mailbox_mode: str,
    fetched_count: int,
    inserted_count: int,
    updated_count: int,
    analyzed_count: int,
    error: str | None = None,
    db_path: Path | None = None,
) -> None:
    with managed_connect(db_path) as db:
        db.execute(
            """
            INSERT INTO sync_runs (
                source, mailbox_mode, fetched_count, inserted_count, updated_count,
                analyzed_count, error, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source,
                mailbox_mode,
                fetched_count,
                inserted_count,
                updated_count,
                analyzed_count,
                error,
                utc_now_iso(),
            ),
        )
