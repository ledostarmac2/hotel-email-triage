from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

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
                corrected_status TEXT,
                summary_quality_rating INTEGER,
                reply_quality_rating INTEGER,
                applied_short_term INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY(email_id) REFERENCES emails(id) ON DELETE SET NULL
            );
            """
        )
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS rule_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_key TEXT NOT NULL UNIQUE,
                candidate_type TEXT NOT NULL,
                pattern TEXT NOT NULL,
                suggestion TEXT NOT NULL,
                correction_count INTEGER NOT NULL DEFAULT 0,
                confidence INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending_review',
                latest_feedback_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS supabase_rule_cache (
                rule_key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                cached_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS supabase_feedback_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT NOT NULL,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS supabase_prompt_cache (
                prompt_key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                cached_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS supabase_known_sender_cache (
                sender_domain TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                cached_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_user_id INTEGER,
                actor_email TEXT,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'user')),
                invited_by_id INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL,
                last_login TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            """
        )
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """
        )
        _ensure_password_reset_tokens_supabase_schema(db)
        _ensure_column(db, "email_analysis", "contact_type", "TEXT")
        _ensure_column(db, "email_analysis", "confidence_score", "INTEGER")
        _ensure_column(db, "email_analysis", "confidence_reason", "TEXT")
        _ensure_column(db, "email_analysis", "needs_review", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(db, "triage_feedback", "corrected_status", "TEXT")
        _ensure_column(db, "triage_feedback", "summary_quality_rating", "INTEGER")
        _ensure_column(db, "triage_feedback", "reply_quality_rating", "INTEGER")
        _ensure_column(db, "triage_feedback", "correction_reason", "TEXT")
        _ensure_column(db, "triage_feedback", "quality_state", "TEXT NOT NULL DEFAULT 'raw'")
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS training_pipeline_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id    INTEGER NOT NULL,
                fingerprint TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'pending',
                error       TEXT,
                created_at  TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_tpl_email_id ON training_pipeline_log (email_id);
            CREATE INDEX IF NOT EXISTS idx_tpl_status ON training_pipeline_log (status);
            """
        )
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS completed_requests_log (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                outlook_entry_id TEXT NOT NULL UNIQUE,
                subject_tokens   TEXT,
                sender_domain    TEXT,
                result           TEXT NOT NULL DEFAULT 'pending',
                processed_at     TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_crl_result ON completed_requests_log (result);

            CREATE TABLE IF NOT EXISTS property_knowledge_items (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                item_type        TEXT NOT NULL,
                item_value       TEXT NOT NULL,
                item_context     TEXT,
                source_email_id  INTEGER,
                occurrence_count INTEGER NOT NULL DEFAULT 1,
                created_at       TEXT NOT NULL,
                updated_at       TEXT NOT NULL,
                UNIQUE(item_type, item_value)
            );
            CREATE INDEX IF NOT EXISTS idx_pki_type ON property_knowledge_items (item_type);
            """
        )
        from .kyc.repository import ensure_kyc_schema

        ensure_kyc_schema(db)


def _ensure_column(db: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _ensure_password_reset_tokens_supabase_schema(db: sqlite3.Connection) -> None:
    """Migrate legacy local-user reset tokens to Supabase UUID-safe storage."""
    columns = {
        row["name"]: str(row["type"] or "").upper()
        for row in db.execute("PRAGMA table_info(password_reset_tokens)").fetchall()
    }
    foreign_keys = db.execute("PRAGMA foreign_key_list(password_reset_tokens)").fetchall()
    if columns.get("user_id") == "TEXT" and not foreign_keys:
        return

    db.execute("ALTER TABLE password_reset_tokens RENAME TO password_reset_tokens_legacy")
    db.execute(
        """
        CREATE TABLE password_reset_tokens (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        INSERT OR IGNORE INTO password_reset_tokens (token, user_id, expires_at, used, created_at)
        SELECT token, CAST(user_id AS TEXT), expires_at, used, created_at
        FROM password_reset_tokens_legacy
        """
    )
    db.execute("DROP TABLE password_reset_tokens_legacy")


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
    needs_review = 1 if analysis.get("needs_review") else 0
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
        analysis.get("confidence_score"),
        analysis.get("confidence_reason", ""),
        needs_review,
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
                    redaction_counts = ?, confidence_score = ?, confidence_reason = ?,
                    needs_review = ?, updated_at = ?
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
                analysis_engine, analysis_error, redaction_counts,
                confidence_score, confidence_reason, needs_review, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                   a.confidence_score, a.confidence_reason, a.needs_review,
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
    needs_review: bool | None = None,
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
    if needs_review is True:
        clauses.append("a.needs_review = 1")
    if query:
        clauses.append("(e.subject LIKE ? OR e.sender_email LIKE ? OR e.sender_name LIKE ? OR e.body_preview LIKE ?)")
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
                   a.confidence_score, a.needs_review, e.conversation_id
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
    corrected_status: str | None = None,
    summary_quality_rating: int | None = None,
    reply_quality_rating: int | None = None,
    correction_reason: str | None = None,
    db_path: Path | None = None,
) -> int:
    with managed_connect(db_path) as db:
        cursor = db.execute(
            """
            INSERT INTO triage_feedback (
                conversation_id, email_id, feedback_text, corrected_urgency,
                corrected_category, corrected_owner, corrected_contact_type,
                corrected_sentiment, corrected_status, summary_quality_rating,
                reply_quality_rating, correction_reason, quality_state,
                applied_short_term, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'raw', 1, ?)
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
                corrected_status,
                summary_quality_rating,
                reply_quality_rating,
                correction_reason,
                utc_now_iso(),
            ),
        )
        return int(cursor.lastrowid)


def update_feedback_quality_state(
    feedback_id: int,
    quality_state: str,
    db_path: Path | None = None,
) -> None:
    """Advance a feedback row's quality_state (raw → reviewed → training_ready | excluded)."""
    allowed = {"raw", "reviewed", "training_ready", "excluded"}
    if quality_state not in allowed:
        raise ValueError(f"quality_state must be one of {allowed}")
    with managed_connect(db_path) as db:
        db.execute(
            "UPDATE triage_feedback SET quality_state = ? WHERE id = ?",
            (quality_state, feedback_id),
        )


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


def detect_rule_candidates(db_path: Path | None = None) -> list[dict[str, Any]]:
    """Mine triage_feedback for repeated correction patterns.

    Returns rule candidates when 3+ corrections share the same direction.
    Candidates are ordered by correction_count descending.
    """
    candidates: list[dict[str, Any]] = []
    with managed_connect(db_path) as db:
        # Pattern 1 — same sender domain repeatedly routed to same owner
        rows = db.execute(
            """
            SELECT
                LOWER(SUBSTR(e.sender_email, INSTR(e.sender_email, '@') + 1)) AS domain,
                tf.corrected_owner,
                COUNT(*) AS correction_count,
                MAX(tf.created_at) AS latest_feedback_at
            FROM triage_feedback tf
            JOIN emails e ON e.id = tf.email_id
            WHERE tf.corrected_owner IS NOT NULL
              AND e.sender_email LIKE '%@%'
            GROUP BY domain, tf.corrected_owner
            HAVING COUNT(*) >= 3
            ORDER BY COUNT(*) DESC
            LIMIT 20
            """
        ).fetchall()
        for row in rows:
            domain = dict(row)["domain"]
            owner = dict(row)["corrected_owner"]
            count = dict(row)["correction_count"]
            candidates.append(
                {
                    "key": f"owner_domain_{domain}_{owner.lower().replace(' ', '_')}",
                    "type": "owner_by_domain",
                    "pattern": f"Sender @{domain}",
                    "suggestion": f"Route to {owner}",
                    "correction_count": count,
                    "latest_feedback_at": dict(row)["latest_feedback_at"],
                    "confidence": min(95, 50 + count * 8),
                    "status": "auto_promoted" if count >= 5 else "candidate",
                }
            )

        # Pattern 2 — category repeatedly corrected to the same value
        rows = db.execute(
            """
            SELECT
                tf.corrected_category,
                COUNT(*) AS correction_count,
                MAX(tf.created_at) AS latest_feedback_at
            FROM triage_feedback tf
            WHERE tf.corrected_category IS NOT NULL
            GROUP BY tf.corrected_category
            HAVING COUNT(*) >= 3
            ORDER BY COUNT(*) DESC
            LIMIT 10
            """
        ).fetchall()
        for row in rows:
            cat = dict(row)["corrected_category"]
            count = dict(row)["correction_count"]
            candidates.append(
                {
                    "key": f"category_{cat.lower().replace(' ', '_').replace('/', '_')}",
                    "type": "category_correction",
                    "pattern": f"Category frequently corrected to: {cat}",
                    "suggestion": f"Improve {cat.lower()} detection rules",
                    "correction_count": count,
                    "latest_feedback_at": dict(row)["latest_feedback_at"],
                    "confidence": min(95, 45 + count * 8),
                    "status": "auto_promoted" if count >= 5 else "candidate",
                }
            )

        # Pattern 3 — urgency systematically over- or under-scored
        rows = db.execute(
            """
            SELECT
                corrected_urgency,
                COUNT(*) AS correction_count
            FROM triage_feedback
            WHERE corrected_urgency IS NOT NULL
            GROUP BY corrected_urgency
            HAVING COUNT(*) >= 3
            ORDER BY COUNT(*) DESC
            """
        ).fetchall()
        for row in rows:
            level = dict(row)["corrected_urgency"]
            count = dict(row)["correction_count"]
            candidates.append(
                {
                    "key": f"urgency_to_{level}",
                    "type": "urgency_correction",
                    "pattern": f"Urgency repeatedly corrected to level {level}",
                    "suggestion": "Review scoring rules that may be over- or under-scoring urgency",
                    "correction_count": count,
                    "latest_feedback_at": None,
                    "confidence": min(95, 40 + count * 8),
                    "status": "auto_promoted" if count >= 5 else "candidate",
                }
            )

    statuses = _rule_candidate_statuses(db_path)
    for candidate in candidates:
        override = statuses.get(candidate["key"])
        if override:
            candidate["status"] = override
    candidates = [candidate for candidate in candidates if candidate.get("status") != "dismissed"]
    candidates.sort(key=lambda c: c["correction_count"], reverse=True)
    return candidates


def _rule_candidate_statuses(db_path: Path | None = None) -> dict[str, str]:
    try:
        with managed_connect(db_path) as db:
            rows = db.execute("SELECT candidate_key, status FROM rule_candidates").fetchall()
    except sqlite3.OperationalError:
        return {}
    return {str(row["candidate_key"]): str(row["status"]) for row in rows}


def set_rule_candidate_status(
    candidate_key: str,
    status: str,
    *,
    candidate_type: str = "manual",
    pattern: str = "",
    suggestion: str = "",
    db_path: Path | None = None,
) -> None:
    if status not in {"candidate", "auto_promoted", "rejected", "dismissed"}:
        raise ValueError(f"Unsupported rule candidate status: {status}")
    now = utc_now_iso()
    with managed_connect(db_path) as db:
        db.execute(
            """
            INSERT INTO rule_candidates (
                candidate_key, candidate_type, pattern, suggestion,
                correction_count, confidence, status, latest_feedback_at,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 0, 0, ?, NULL, ?, ?)
            ON CONFLICT(candidate_key)
            DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at
            """,
            (candidate_key, candidate_type, pattern, suggestion, status, now, now),
        )


def cache_classification_rules(rules: list[dict[str, Any]], db_path: Path | None = None) -> None:
    now = utc_now_iso()
    with managed_connect(db_path) as db:
        for rule in rules:
            rule_key = str(rule.get("rule_key") or rule.get("key") or "")
            if not rule_key:
                continue
            db.execute(
                """
                INSERT INTO supabase_rule_cache (rule_key, payload, cached_at)
                VALUES (?, ?, ?)
                ON CONFLICT(rule_key)
                DO UPDATE SET payload = excluded.payload, cached_at = excluded.cached_at
                """,
                (rule_key, _encode_json(rule), now),
            )


def list_cached_classification_rules(db_path: Path | None = None) -> list[dict[str, Any]]:
    try:
        with managed_connect(db_path) as db:
            rows = db.execute("SELECT payload FROM supabase_rule_cache ORDER BY cached_at DESC").fetchall()
    except sqlite3.OperationalError:
        return []
    rules: list[dict[str, Any]] = []
    for row in rows:
        payload = _decode_json(row["payload"])
        if isinstance(payload, dict):
            rules.append(payload)
    return rules


def cache_prompt_versions(prompts: list[dict[str, Any]], db_path: Path | None = None) -> None:
    now = utc_now_iso()
    with managed_connect(db_path) as db:
        for prompt in prompts:
            prompt_key = str(prompt.get("prompt_key") or prompt.get("name") or prompt.get("id") or "")
            if not prompt_key:
                continue
            db.execute(
                """
                INSERT INTO supabase_prompt_cache (prompt_key, payload, cached_at)
                VALUES (?, ?, ?)
                ON CONFLICT(prompt_key)
                DO UPDATE SET payload = excluded.payload, cached_at = excluded.cached_at
                """,
                (prompt_key, _encode_json(prompt), now),
            )


def list_cached_prompt_versions(db_path: Path | None = None) -> list[dict[str, Any]]:
    try:
        with managed_connect(db_path) as db:
            rows = db.execute("SELECT payload FROM supabase_prompt_cache ORDER BY cached_at DESC").fetchall()
    except sqlite3.OperationalError:
        return []
    return [payload for row in rows if isinstance((payload := _decode_json(row["payload"])), dict)]


def cache_known_senders(senders: list[dict[str, Any]], db_path: Path | None = None) -> None:
    now = utc_now_iso()
    with managed_connect(db_path) as db:
        for sender in senders:
            domain = str(sender.get("sender_domain") or "").lower().strip()
            if not domain:
                continue
            db.execute(
                """
                INSERT INTO supabase_known_sender_cache (sender_domain, payload, cached_at)
                VALUES (?, ?, ?)
                ON CONFLICT(sender_domain)
                DO UPDATE SET payload = excluded.payload, cached_at = excluded.cached_at
                """,
                (domain, _encode_json({**sender, "sender_domain": domain}), now),
            )


def list_cached_known_senders(db_path: Path | None = None) -> list[dict[str, Any]]:
    try:
        with managed_connect(db_path) as db:
            rows = db.execute("SELECT payload FROM supabase_known_sender_cache ORDER BY sender_domain").fetchall()
    except sqlite3.OperationalError:
        return []
    return [payload for row in rows if isinstance((payload := _decode_json(row["payload"])), dict)]


def enqueue_feedback_upload(
    payload: dict[str, Any],
    *,
    error: str | None = None,
    db_path: Path | None = None,
) -> None:
    now = utc_now_iso()
    with managed_connect(db_path) as db:
        db.execute(
            """
            INSERT INTO supabase_feedback_queue (payload, attempt_count, last_error, created_at, updated_at)
            VALUES (?, 0, ?, ?, ?)
            """,
            (_encode_json(payload), (error or "")[:500], now, now),
        )


def list_pending_feedback_uploads(
    *,
    limit: int = 25,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    with managed_connect(db_path) as db:
        rows = db.execute(
            """
            SELECT id, payload, attempt_count, last_error, created_at, updated_at
            FROM supabase_feedback_queue
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        ).fetchall()
    pending: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["payload"] = _decode_json(item["payload"])
        pending.append(item)
    return pending


def mark_feedback_upload_succeeded(upload_id: int, db_path: Path | None = None) -> None:
    with managed_connect(db_path) as db:
        db.execute("DELETE FROM supabase_feedback_queue WHERE id = ?", (upload_id,))


def mark_feedback_upload_failed(
    upload_id: int,
    error: str,
    db_path: Path | None = None,
) -> None:
    with managed_connect(db_path) as db:
        db.execute(
            """
            UPDATE supabase_feedback_queue
            SET attempt_count = attempt_count + 1, last_error = ?, updated_at = ?
            WHERE id = ?
            """,
            ((error or "")[:500], utc_now_iso(), upload_id),
        )


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


def admin_overview_stats(db_path: Path | None = None) -> dict[str, Any]:
    with managed_connect(db_path) as db:
        total_emails = db.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
        total_feedback = db.execute("SELECT COUNT(*) FROM triage_feedback").fetchone()[0]
        total_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        last_sync = db.execute(
            "SELECT created_at, source, fetched_count FROM sync_runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        engine_rows = db.execute(
            """
            SELECT analysis_engine, COUNT(*) AS cnt
            FROM email_analysis WHERE analysis_engine IS NOT NULL
            GROUP BY analysis_engine ORDER BY cnt DESC
            """
        ).fetchall()
        low_conf = db.execute(
            "SELECT COUNT(*) FROM email_analysis WHERE confidence_score IS NOT NULL AND confidence_score < 50"
        ).fetchone()[0]
        needs_review_count = db.execute(
            "SELECT COUNT(*) FROM email_analysis WHERE needs_review = 1"
        ).fetchone()[0]
        feedback_trend = db.execute(
            """
            SELECT DATE(created_at) AS day, COUNT(*) AS cnt
            FROM triage_feedback
            WHERE created_at >= DATE('now', '-30 days')
            GROUP BY day ORDER BY day
            """
        ).fetchall()
    return {
        "total_emails": total_emails,
        "total_feedback": total_feedback,
        "total_users": total_users,
        "low_confidence_count": low_conf,
        "needs_review_count": needs_review_count,
        "last_sync": dict(last_sync) if last_sync else None,
        "engine_breakdown": [dict(r) for r in engine_rows],
        "feedback_trend": [dict(r) for r in feedback_trend],
    }


def admin_correction_stats(db_path: Path | None = None) -> list[dict[str, Any]]:
    with managed_connect(db_path) as db:
        cats = db.execute(
            """
            SELECT corrected_category AS label, COUNT(*) AS count
            FROM triage_feedback WHERE corrected_category IS NOT NULL
            GROUP BY corrected_category ORDER BY count DESC LIMIT 10
            """
        ).fetchall()
        owners = db.execute(
            """
            SELECT corrected_owner AS label, COUNT(*) AS count
            FROM triage_feedback WHERE corrected_owner IS NOT NULL
            GROUP BY corrected_owner ORDER BY count DESC LIMIT 10
            """
        ).fetchall()
        urgency = db.execute(
            """
            SELECT 'Urgency → ' || corrected_urgency AS label, COUNT(*) AS count
            FROM triage_feedback WHERE corrected_urgency IS NOT NULL
            GROUP BY corrected_urgency ORDER BY count DESC
            """
        ).fetchall()
    return (
        [{"type": "Category", **dict(r)} for r in cats]
        + [{"type": "Owner", **dict(r)} for r in owners]
        + [{"type": "Urgency", **dict(r)} for r in urgency]
    )


def admin_misclassification_drilldowns(db_path: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    with managed_connect(db_path) as db:
        owner_by_domain = db.execute(
            """
            SELECT
                LOWER(SUBSTR(e.sender_email, INSTR(e.sender_email, '@') + 1)) AS sender_domain,
                COALESCE(a.recommended_department_owner, '') AS original_owner,
                tf.corrected_owner,
                COUNT(*) AS count
            FROM triage_feedback tf
            JOIN emails e ON e.id = tf.email_id
            LEFT JOIN email_analysis a ON a.email_id = e.id
            WHERE tf.corrected_owner IS NOT NULL
              AND e.sender_email LIKE '%@%'
            GROUP BY sender_domain, original_owner, tf.corrected_owner
            ORDER BY count DESC
            LIMIT 15
            """
        ).fetchall()
        urgency = db.execute(
            """
            SELECT
                COALESCE(a.priority_level, '') AS original_priority,
                tf.corrected_urgency,
                COUNT(*) AS count
            FROM triage_feedback tf
            LEFT JOIN email_analysis a ON a.email_id = tf.email_id
            WHERE tf.corrected_urgency IS NOT NULL
            GROUP BY original_priority, tf.corrected_urgency
            ORDER BY count DESC
            LIMIT 15
            """
        ).fetchall()
    return {
        "owner_by_domain": [dict(row) for row in owner_by_domain],
        "urgency": [dict(row) for row in urgency],
    }


def admin_low_confidence_emails(limit: int = 20, db_path: Path | None = None) -> list[dict[str, Any]]:
    with managed_connect(db_path) as db:
        rows = db.execute(
            """
            SELECT e.id, e.subject, e.sender_name, e.sender_email, e.received_datetime,
                   a.category, a.confidence_score, a.confidence_reason, a.analysis_engine,
                   a.needs_review
            FROM email_analysis a JOIN emails e ON e.id = a.email_id
            WHERE a.confidence_score IS NOT NULL AND a.confidence_score < 50
            ORDER BY a.confidence_score ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def record_audit_event(
    *,
    action: str,
    actor_user_id: str | int | None = None,
    actor_email: str | None = None,
    entity_type: str | None = None,
    entity_id: str | int | None = None,
    metadata: dict[str, Any] | None = None,
    db_path: Path | None = None,
) -> None:
    safe_metadata = metadata or {}
    with managed_connect(db_path) as db:
        db.execute(
            """
            INSERT INTO audit_logs (
                actor_user_id, actor_email, action, entity_type,
                entity_id, metadata, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                actor_user_id,
                actor_email,
                action,
                entity_type,
                str(entity_id) if entity_id is not None else None,
                _encode_json(safe_metadata),
                utc_now_iso(),
            ),
        )


def admin_recent_audit_logs(limit: int = 25, db_path: Path | None = None) -> list[dict[str, Any]]:
    with managed_connect(db_path) as db:
        rows = db.execute(
            """
            SELECT id, actor_user_id, actor_email, action, entity_type,
                   entity_id, metadata, created_at
            FROM audit_logs
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        ).fetchall()
    logs: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["metadata"] = _decode_json(item.get("metadata"))
        logs.append(item)
    return logs


def consume_reset_token(token: str, db_path: Path | None = None) -> str | None:
    """Validate and mark a password-reset token used. Returns user_id or None."""
    with managed_connect(db_path) as db:
        row = db.execute(
            "SELECT user_id FROM password_reset_tokens "
            "WHERE token = ? AND expires_at > datetime('now') AND used = 0",
            (token,),
        ).fetchone()
        if not row:
            return None
        user_id = str(row["user_id"])
        db.execute("UPDATE password_reset_tokens SET used = 1 WHERE token = ?", (token,))
    return user_id


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


# ── Training pipeline helpers ─────────────────────────────────────────────────

def log_training_example(
    email_id: int,
    fingerprint: str,
    status: str,
    error: str | None = None,
    db_path: Path | None = None,
) -> None:
    """Insert or replace a training pipeline log entry for this email."""
    with managed_connect(db_path) as db:
        db.execute(
            """
            INSERT INTO training_pipeline_log (email_id, fingerprint, status, error, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(email_id) DO UPDATE SET status=excluded.status, error=excluded.error
            """,
            (email_id, fingerprint, status, error, utc_now_iso()),
        )


def get_training_pipeline_status(db_path: Path | None = None) -> dict:
    """Return counts of emails by training pipeline status."""
    with managed_connect(db_path) as db:
        rows = db.execute(
            "SELECT status, COUNT(*) AS n FROM training_pipeline_log GROUP BY status"
        ).fetchall()
        counts = {row["status"]: row["n"] for row in rows}
        total_completed = db.execute(
            "SELECT COUNT(*) FROM emails WHERE status = 'Completed'"
        ).fetchone()[0]
        processed = sum(counts.values())
        return {
            "uploaded": counts.get("uploaded", 0),
            "skipped": counts.get("skipped", 0),
            "failed": counts.get("failed", 0),
            "processed": processed,
            "pending": max(0, total_completed - processed),
        }


def list_unprocessed_completed_emails(
    batch_size: int = 10,
    db_path: Path | None = None,
) -> list[dict]:
    """Return completed emails not yet in the training pipeline log."""
    with managed_connect(db_path) as db:
        rows = db.execute(
            """
            SELECT e.id, e.subject, e.sender_email, e.body_text, e.received_datetime,
                   ea.category, ea.recommended_department_owner, ea.guest_sentiment,
                   ea.priority_level, ea.missing_information, ea.analysis_engine,
                   ea.confidence_score
            FROM emails e
            JOIN email_analysis ea ON ea.email_id = e.id
            LEFT JOIN training_pipeline_log tl ON tl.email_id = e.id
            WHERE e.status = 'Completed'
              AND tl.email_id IS NULL
            ORDER BY e.received_datetime DESC
            LIMIT ?
            """,
            (batch_size,),
        ).fetchall()
        return [dict(row) for row in rows]


def list_property_knowledge(db_path: Path | None = None) -> list[dict[str, Any]]:
    """Return all property knowledge items ordered by type and occurrence."""
    try:
        with managed_connect(db_path) as db:
            rows = db.execute(
                """
                SELECT item_type, item_value, item_context, occurrence_count,
                       created_at, updated_at
                FROM property_knowledge_items
                ORDER BY item_type, occurrence_count DESC, item_value
                """
            ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(row) for row in rows]


# ── Import→train→delete (body purge) ─────────────────────────────────────────

def purge_email_bodies(email_ids: list[int], db_path: Path | None = None) -> int:
    """Null out body_text and body_content for the given email IDs.

    Safe to call repeatedly; returns the number of rows actually updated.
    Used by the import→train→delete workflow to free storage once emails
    have been analyzed and their training features extracted.
    """
    if not email_ids:
        return 0
    with managed_connect(db_path) as db:
        placeholders = ",".join("?" * len(email_ids))
        cur = db.execute(
            f"UPDATE emails SET body_text = NULL, body_content = NULL WHERE id IN ({placeholders})",
            email_ids,
        )
        return cur.rowcount


def get_purgeable_email_ids(
    min_age_days: int = 0,
    require_analyzed: bool = True,
    db_path: Path | None = None,
) -> list[int]:
    """Return email IDs whose body can be safely purged.

    Criteria:
    - body_text or body_content is not already NULL
    - Optional: email has a completed analysis record
    - Optional: received more than min_age_days ago
    """
    from .text_utils import utc_now_iso  # local import to avoid circular
    clauses = ["(e.body_text IS NOT NULL OR e.body_content IS NOT NULL)"]
    params: list[Any] = []
    if require_analyzed:
        clauses.append("EXISTS (SELECT 1 FROM email_analysis a WHERE a.email_id = e.id AND a.ai_summary IS NOT NULL)")
    if min_age_days > 0:
        clauses.append("e.received_datetime < datetime('now', ?)")
        params.append(f"-{min_age_days} days")
    where = " AND ".join(clauses)
    with managed_connect(db_path) as db:
        rows = db.execute(f"SELECT e.id FROM emails e WHERE {where}", params).fetchall()
    return [row[0] for row in rows]


def get_local_training_examples(limit: int = 5000, db_path: Path | None = None) -> list[dict[str, Any]]:
    """Return training examples derived from local triage_feedback corrections.

    Used as fallback when Supabase is unreachable. Joins feedback with emails and
    analysis to produce the same schema as _download_training_examples().
    Only includes feedback rows where a corrected_owner or corrected_status was set
    (i.e., the human made a meaningful correction).
    """
    with managed_connect(db_path) as db:
        rows = db.execute(
            """
            SELECT
                e.subject,
                e.body_text,
                e.body_preview,
                a.category         AS label_category,
                a.urgency_score    AS label_urgency,
                a.recommended_department_owner AS label_owner,
                tf.corrected_owner AS corrected_owner,
                tf.corrected_status AS corrected_status,
                tf.summary_quality_rating,
                tf.reply_quality_rating
            FROM triage_feedback tf
            JOIN emails e ON e.id = tf.email_id
            LEFT JOIN email_analysis a ON a.email_id = tf.email_id
            WHERE tf.corrected_owner IS NOT NULL
               OR tf.corrected_status IS NOT NULL
            ORDER BY tf.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    results = []
    for row in rows:
        d = dict(row)
        # Use corrected labels when available
        if d.get("corrected_owner"):
            d["label_owner"] = d["corrected_owner"]
        d["body_redacted"] = d.get("body_text") or d.get("body_preview") or ""
        d["subject_tokens"] = d.get("subject") or ""
        d["labeling_engine"] = "local_feedback"
        results.append(d)
    return results
