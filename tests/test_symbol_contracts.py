"""Contract tests: symbols that are imported across module boundaries actually exist.

Each assertion here corresponds to a real import statement elsewhere in the codebase.
If a symbol is renamed or deleted, this test fails before any runtime call does.
"""
from __future__ import annotations

import importlib


def _sym(module_path: str, *names: str) -> None:
    mod = importlib.import_module(module_path)
    for name in names:
        assert hasattr(mod, name), (
            f"{module_path} is missing symbol {name!r} — "
            "update the exporting module or fix the importing reference"
        )


# ── outlook_dashboard.config ──────────────────────────────────────────────────

def test_config_symbols() -> None:
    _sym("outlook_dashboard.config", "get_settings", "DATA_DIR", "Settings")


# ── outlook_dashboard.ai ──────────────────────────────────────────────────────

def test_ai_symbols() -> None:
    _sym(
        "outlook_dashboard.ai",
        "analyze_email",
        "triage_email",
        "triage_conversation",
        "heuristic_analysis",
        "infer_feedback_corrections",
        "latest_message_text",
        "urgency_score",
    )


# ── outlook_dashboard.taxonomy ────────────────────────────────────────────────

def test_taxonomy_symbols() -> None:
    _sym(
        "outlook_dashboard.taxonomy",
        "CATEGORIES",
        "CONTACT_TYPES",
        "DEPARTMENT_OWNERS",
        "PRIORITY_LEVELS",
        "RISK_FLAGS",
        "STATUSES",
    )


# ── outlook_dashboard.database ────────────────────────────────────────────────

def test_database_symbols() -> None:
    _sym(
        "outlook_dashboard.database",
        "managed_connect",
        "initialize_database",
        "row_to_dict",
        "get_training_pipeline_status",
        "list_unprocessed_completed_emails",
        "log_training_example",
        "enqueue_feedback_upload",
        "list_pending_feedback_uploads",
        "mark_feedback_upload_failed",
        "mark_feedback_upload_succeeded",
        "cache_classification_rules",
        "cache_known_senders",
        "cache_prompt_versions",
        "list_cached_classification_rules",
        "list_cached_known_senders",
        "list_cached_prompt_versions",
        "list_property_knowledge",
    )


# ── outlook_dashboard.local_classifier ───────────────────────────────────────

def test_local_classifier_symbols() -> None:
    _sym(
        "outlook_dashboard.local_classifier",
        "train",
        "get_classifier_status",
        "get_model_meta",
        "rollback_model",
        "invalidate_cache",
        "feature_importance",
        "_save_models",
        "_download_training_examples",
        "_load_local_examples",
        "CATEGORIES",
        "DEPARTMENT_OWNERS",
        "MIN_TRAINING_EXAMPLES",
    )


# ── outlook_dashboard.training_pipeline ──────────────────────────────────────

def test_training_pipeline_symbols() -> None:
    _sym(
        "outlook_dashboard.training_pipeline",
        "run_pipeline",
        "pipeline_status",
        "_build_example",
        "_fingerprint",
        "_subject_tokens",
        "_upload_example",
    )


# ── outlook_dashboard.supabase_client ────────────────────────────────────────

def test_supabase_client_symbols() -> None:
    _sym(
        "outlook_dashboard.supabase_client",
        "upload_feedback_event",
        "flush_feedback_queue",
        "download_approved_rules",
        "download_prompt_versions",
        "download_known_senders",
        "get_cached_rules",
        "get_cached_known_senders",
        "get_cached_prompt_versions",
        "promote_rule_candidates",
    )


# ── outlook_dashboard.auth ────────────────────────────────────────────────────

def test_auth_symbols() -> None:
    _sym(
        "outlook_dashboard.auth",
        "authenticate_user",
        "get_session_user",
        "create_session",
        "delete_session",
        "encode_session",
        "create_first_admin",
        "create_user",
        "create_reset_token",
        "list_users",
        "reset_password",
        "delete_user",
        "ensure_admin",
        "needs_credentials_setup",
        "admin_setup_available",
        "admin_user_exists",
        "send_invite_email",
        "send_reset_email",
    )


# ── outlook_dashboard.platform_compat ────────────────────────────────────────

def test_platform_compat_symbols() -> None:
    _sym("outlook_dashboard.platform_compat", "IS_WINDOWS", "HAS_OUTLOOK_COM")


# ── outlook_dashboard.kyc.models ─────────────────────────────────────────────

def test_kyc_models_symbols() -> None:
    _sym("outlook_dashboard.kyc.models", "KycEvent", "KycSettings")


# ── outlook_dashboard.kyc.routes ─────────────────────────────────────────────

def test_kyc_routes_symbols() -> None:
    _sym("outlook_dashboard.kyc.routes", "router")


# ── outlook_dashboard.redaction ───────────────────────────────────────────────

def test_redaction_symbols() -> None:
    _sym("outlook_dashboard.redaction", "redact_sensitive_text")


# ── outlook_dashboard.text_utils ─────────────────────────────────────────────

def test_text_utils_symbols() -> None:
    _sym(
        "outlook_dashboard.text_utils",
        "utc_now_iso",
        "graph_email_address",
        "html_to_text",
    )


# ── outlook_dashboard.runtime_log ────────────────────────────────────────────

def test_runtime_log_symbols() -> None:
    _sym("outlook_dashboard.runtime_log", "get_logger", "configure", "safe_log", "scrub_log_value")


# ── outlook_dashboard.completed_training_pipeline ────────────────────────────

def test_completed_training_pipeline_symbols() -> None:
    _sym(
        "outlook_dashboard.completed_training_pipeline",
        "run_completed_pipeline",
        "completed_pipeline_status",
    )


# ── outlook_dashboard.sender_intelligence ────────────────────────────────────

def test_sender_intelligence_symbols() -> None:
    _sym("outlook_dashboard.sender_intelligence", "get_sender_profile", "refresh_profiles")


def test_active_learning_symbols() -> None:
    _sym("outlook_dashboard.active_learning", "rank_training_candidates")


def test_threading_symbols() -> None:
    _sym(
        "outlook_dashboard.threading",
        "normalize_subject",
        "subject_similarity",
        "thread_match_score",
        "is_likely_followup_text",
    )
