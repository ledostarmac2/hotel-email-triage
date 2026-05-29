"""Contract tests: SQLite schema is reachable from fresh DB.

Each test migrates a fresh temp database and runs a representative query
against one table.  A failure means initialize_database() no longer creates
that table, or the expected columns have been renamed.
"""
from __future__ import annotations

from pathlib import Path

import pytest


# ── helpers ───────────────────────────────────────────────────────────────────


def _init(tmp_path: Path) -> Path:
    """Return a path to a freshly migrated main database."""
    from outlook_dashboard.database import initialize_database
    db_path = tmp_path / "test.sqlite"
    initialize_database(db_path=db_path)
    return db_path


def _q(db_path: Path, sql: str) -> list:
    from outlook_dashboard.database import managed_connect
    with managed_connect(db_path) as db:
        return db.execute(sql).fetchall()


# ── core tables (created by database.initialize_database) ─────────────────────


def test_emails_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT id, graph_message_id, subject, sender_email, status, created_at FROM emails LIMIT 0")


def test_email_analysis_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT id, email_id, category, analysis_engine, confidence_score, needs_review FROM email_analysis LIMIT 0")


def test_oauth_tokens_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT id, provider, access_token, refresh_token, expires_at FROM oauth_tokens LIMIT 0")


def test_oauth_states_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT state, mailbox_mode, created_at FROM oauth_states LIMIT 0")


def test_sync_runs_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT id, source, mailbox_mode, fetched_count, created_at FROM sync_runs LIMIT 0")


def test_triage_feedback_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT id, email_id, conversation_id, feedback_text, created_at FROM triage_feedback LIMIT 0")


def test_rule_candidates_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT id, candidate_key, candidate_type, pattern, status FROM rule_candidates LIMIT 0")


def test_supabase_rule_cache_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT rule_key, payload, cached_at FROM supabase_rule_cache LIMIT 0")


def test_supabase_feedback_queue_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT id, payload, attempt_count, created_at, updated_at FROM supabase_feedback_queue LIMIT 0")


def test_supabase_prompt_cache_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT prompt_key, payload, cached_at FROM supabase_prompt_cache LIMIT 0")


def test_supabase_known_sender_cache_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT sender_domain, payload, cached_at FROM supabase_known_sender_cache LIMIT 0")


def test_audit_logs_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT id, actor_user_id, actor_email, action, entity_type, created_at FROM audit_logs LIMIT 0")


def test_users_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT id, email, role, created_at FROM users LIMIT 0")


def test_sessions_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT session_id, user_id, created_at, expires_at FROM sessions LIMIT 0")


def test_password_reset_tokens_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT token, user_id, expires_at, used, created_at FROM password_reset_tokens LIMIT 0")


def test_training_pipeline_log_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT id, email_id, fingerprint, status, created_at FROM training_pipeline_log LIMIT 0")


def test_training_bootstrap_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT id, subject_tokens, body_redacted, label_urgency, label_owner, label_category FROM training_bootstrap LIMIT 0")


def test_completed_requests_log_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT id, outlook_entry_id, import_key, result, processed_at FROM completed_requests_log LIMIT 0")


def test_property_knowledge_items_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT id, item_type, item_value, item_context, created_at FROM property_knowledge_items LIMIT 0")


# ── KYC tables (created by initialize_database via ensure_kyc_schema) ─────────


def test_kyc_settings_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT id, enabled, reminder_interval_minutes, active_hours_start, updated_at FROM kyc_settings LIMIT 0")


def test_kyc_inspection_events_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT id, due_at, status, source FROM kyc_inspection_events LIMIT 0")


def test_kyc_acknowledgements_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT id FROM kyc_acknowledgements LIMIT 0")


def test_kyc_audit_log_table(tmp_path: Path) -> None:
    db = _init(tmp_path)
    _q(db, "SELECT id FROM kyc_audit_log LIMIT 0")


# ── app_kv (created lazily by local_classifier on first model save) ───────────


def test_app_kv_table_created_on_first_save(tmp_path: Path) -> None:
    from outlook_dashboard import local_classifier
    db_path = tmp_path / "cls.sqlite"
    local_classifier.invalidate_cache()
    local_classifier._save_models(
        {"urgency": "dummy"},
        {
            "version_id": "test-v1",
            "trained_at": "2026-01-01T00:00:00+00:00",
            "total_examples_downloaded": 0,
            "targets": {},
        },
        db_path=db_path,
    )
    _q(db_path, "SELECT key, value, updated_at FROM app_kv LIMIT 0")
