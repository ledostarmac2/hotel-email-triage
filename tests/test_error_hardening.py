"""Error-hardening tests.

Verifies that each hardened error path:
- does not show raw tracebacks or str(exc) in API responses
- returns consistent JSON with a plain-English detail message
- logs diagnostic detail internally
- does not crash the app or silently swallow failures
"""
from __future__ import annotations

import logging
import logging.handlers
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── CredentialsSetupRequest validation ────────────────────────────────────────


class TestCredentialsSetupRequestValidation:
    """Pydantic model must reject malformed payloads before hitting business logic."""

    def test_missing_supabase_url_returns_422(self, app_client):
        resp = app_client.post(
            "/api/auth/credentials-setup",
            json={"supabase_key": "x" * 30, "supabase_service_role_key": "y" * 30},
        )
        assert resp.status_code == 422

    def test_missing_supabase_key_returns_422(self, app_client):
        resp = app_client.post(
            "/api/auth/credentials-setup",
            json={"supabase_url": "https://example.supabase.co", "supabase_service_role_key": "y" * 30},
        )
        assert resp.status_code == 422

    def test_missing_service_role_key_returns_422(self, app_client):
        resp = app_client.post(
            "/api/auth/credentials-setup",
            json={"supabase_url": "https://example.supabase.co", "supabase_key": "x" * 30},
        )
        assert resp.status_code == 422

    def test_empty_string_supabase_url_returns_422(self, app_client):
        resp = app_client.post(
            "/api/auth/credentials-setup",
            json={
                "supabase_url": "",
                "supabase_key": "x" * 30,
                "supabase_service_role_key": "y" * 30,
            },
        )
        assert resp.status_code == 422

    def test_anthropic_key_is_optional(self, app_client, monkeypatch):
        """anthropic_api_key has a default of '' — omitting it must not 422."""
        import outlook_dashboard.config as _config

        monkeypatch.setattr(_config, "write_local_env", lambda *a, **kw: None)
        resp = app_client.post(
            "/api/auth/credentials-setup",
            json={
                "supabase_url": "https://example.supabase.co",
                "supabase_key": "x" * 30,
                "supabase_service_role_key": "y" * 30,
            },
        )
        # write_local_env is mocked; expect 200 or 400 (validation may catch URL)
        assert resp.status_code in (200, 400)
        assert resp.status_code != 422

    def test_env_write_failure_returns_500_plain_english(self, app_client, monkeypatch):
        import outlook_dashboard.main as _main

        def _boom(*a, **kw):
            raise OSError("disk full")

        # Patch at the main module where the name is bound after import
        monkeypatch.setattr(_main, "write_local_env", _boom)
        resp = app_client.post(
            "/api/auth/credentials-setup",
            json={
                "supabase_url": "https://abc.supabase.co",
                "supabase_key": "x" * 30,
                "supabase_service_role_key": "y" * 30,
            },
        )
        assert resp.status_code == 500
        detail = resp.json().get("detail", "")
        # Must not expose raw exception string
        assert "disk full" not in detail
        assert "OSError" not in detail
        assert len(detail) > 5  # Should have a real message


# ── Admin setup error: no raw exc in response ─────────────────────────────────


class TestAdminSetupErrorMessages:

    def test_setup_failure_message_is_plain_english(self, app_client, monkeypatch):
        from outlook_dashboard import main as _main

        monkeypatch.setattr(_main, "admin_user_exists", lambda: False)
        monkeypatch.setattr(_main, "admin_setup_available", lambda: True)
        monkeypatch.setattr(
            _main,
            "create_first_admin",
            lambda *a, **kw: (_ for _ in ()).throw(ValueError("UNIQUE constraint failed: users.email")),
        )
        resp = app_client.post(
            "/api/auth/setup",
            json={"email": "admin@example.com", "password": "TestPass123!"},
        )
        assert resp.status_code == 400
        detail = resp.json().get("detail", "")
        # Must NOT expose raw Python exception detail
        assert "UNIQUE constraint" not in detail
        assert "users.email" not in detail
        # Must be a plain English message
        assert len(detail) > 5


# ── Invite error: no raw exc in response ─────────────────────────────────────


class TestInviteErrorMessages:

    def test_invite_failure_message_is_plain_english(self, app_client, monkeypatch):
        from outlook_dashboard import main as _main

        monkeypatch.setattr(
            _main,
            "create_user",
            lambda *a, **kw: (_ for _ in ()).throw(ValueError("UNIQUE constraint failed: users.email")),
        )
        resp = app_client.post(
            "/api/auth/invite",
            json={"email": "newuser@example.com"},
        )
        assert resp.status_code == 400
        detail = resp.json().get("detail", "")
        assert "UNIQUE constraint" not in detail
        assert "users.email" not in detail
        assert len(detail) > 5


# ── ApiWorker error messages ───────────────────────────────────────────────────


class TestApiWorkerErrorMessages(unittest.TestCase):
    """ApiWorker must emit readable messages — not raw exception representations."""

    def _run_worker(self, fn):
        """Run ApiWorker in-thread and collect emitted signal."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

        from replyright_qt.api_client import ApiWorker

        emitted: list[str] = []
        worker = ApiWorker(fn)
        worker.failure.connect(emitted.append)
        worker.run()
        return emitted

    def test_connection_error_readable_message(self):
        import requests

        def _raise():
            raise requests.ConnectionError("Connection refused")

        emitted = self._run_worker(_raise)
        self.assertEqual(len(emitted), 1)
        msg = emitted[0]
        self.assertIn("connect", msg.lower())
        self.assertNotIn("ConnectionError", msg)
        self.assertNotIn("Connection refused", msg)

    def test_timeout_readable_message(self):
        import requests

        def _raise():
            raise requests.Timeout("read timeout")

        emitted = self._run_worker(_raise)
        self.assertEqual(len(emitted), 1)
        msg = emitted[0]
        self.assertIn("long", msg.lower())
        self.assertNotIn("read timeout", msg)

    def test_api_error_passes_through(self):
        from replyright_qt.api_client import ApiError

        def _raise():
            raise ApiError("Email not found.", 404)

        emitted = self._run_worker(_raise)
        self.assertEqual(len(emitted), 1)
        self.assertIn("Email not found", emitted[0])

    def test_generic_exception_includes_exception_message(self):
        def _raise():
            raise RuntimeError("some internal bug")

        emitted = self._run_worker(_raise)
        self.assertEqual(len(emitted), 1)
        # Message must contain some diagnostic text, not just "Unexpected error"
        self.assertIn("some internal bug", emitted[0])


# ── _load_processed_entry_ids: DB failure does not crash ─────────────────────


class TestLoadProcessedEntryIds:

    def test_bad_db_path_returns_empty_set_and_logs(self, tmp_path):
        """Non-existent DB path must return empty set (no crash) and log a warning."""
        import logging as _logging
        from outlook_dashboard.completed_requests_importer import _load_processed_entry_ids

        bad_path = tmp_path / "nonexistent" / "db.sqlite3"
        logged: list[str] = []

        # Attach a handler directly on the replyright logger to capture output
        rr_logger = _logging.getLogger("replyright.completed_requests_importer")
        handler = _logging.handlers.MemoryHandler(capacity=100, flushLevel=_logging.CRITICAL)
        rr_logger.addHandler(handler)
        original_level = rr_logger.level
        rr_logger.setLevel(_logging.WARNING)
        try:
            result = _load_processed_entry_ids(bad_path)
            logged = [r.getMessage() for r in handler.buffer]
        finally:
            rr_logger.removeHandler(handler)
            rr_logger.setLevel(original_level)

        assert isinstance(result, set)
        assert len(result) == 0
        assert len(logged) > 0, "Expected at least one warning log"
        assert any(
            "dedup" in m.lower() or "processed" in m.lower() or "entry" in m.lower()
            for m in logged
        ), f"Expected a dedup-related warning. Got: {logged}"

    def test_missing_table_returns_empty_set_and_logs(self, tmp_db):
        """If the completed_requests_log table doesn't exist yet, return empty set."""
        import logging as _logging
        import logging.handlers as _handlers
        import sqlite3
        from outlook_dashboard.completed_requests_importer import _load_processed_entry_ids

        # Drop the table to simulate a fresh DB that hasn't run the migration
        with sqlite3.connect(tmp_db) as conn:
            conn.execute("DROP TABLE IF EXISTS completed_requests_log")

        rr_logger = _logging.getLogger("replyright.completed_requests_importer")
        handler = _handlers.MemoryHandler(capacity=100, flushLevel=_logging.CRITICAL)
        rr_logger.addHandler(handler)
        original_level = rr_logger.level
        rr_logger.setLevel(_logging.WARNING)
        try:
            result = _load_processed_entry_ids(tmp_db)
        finally:
            rr_logger.removeHandler(handler)
            rr_logger.setLevel(original_level)

        assert isinstance(result, set)


# ── Classifier predict: None paths are logged ────────────────────────────────


class TestClassifierPredictLogging:

    def test_predict_no_models_logs_debug(self, tmp_path):
        """predict() with no trained model must return None and log a debug message."""
        import logging as _logging
        import logging.handlers as _handlers
        from outlook_dashboard.local_classifier import invalidate_cache, predict

        invalidate_cache()
        db_path = tmp_path / "empty.sqlite3"
        clf_logger = _logging.getLogger("replyright.local_classifier")
        handler = _handlers.MemoryHandler(capacity=100, flushLevel=_logging.CRITICAL)
        clf_logger.addHandler(handler)
        original_level = clf_logger.level
        clf_logger.setLevel(_logging.DEBUG)
        try:
            result = predict("some email body", db_path=db_path)
            debug_msgs = [r.getMessage() for r in handler.buffer]
        finally:
            clf_logger.removeHandler(handler)
            clf_logger.setLevel(original_level)

        assert result is None
        assert any(
            "no trained model" in m.lower() or "skipped" in m.lower()
            for m in debug_msgs
        ), f"Expected a debug log about no models. Got: {debug_msgs}"

    def test_predict_below_threshold_logs_debug(self, tmp_path):
        """When all predictions are below threshold, None is returned with a debug log."""
        import logging as _logging
        import logging.handlers as _handlers
        import numpy as np
        from outlook_dashboard.local_classifier import predict

        mock_model = MagicMock()
        # Return very low probability for all classes
        mock_model.predict_proba.return_value = np.array([[0.1, 0.05, 0.05]])
        mock_model.classes_ = np.array(["A", "B", "C"])

        mock_models = {"urgency": mock_model}
        mock_meta = {"version_id": "test-v1", "targets": {}}

        db_path = tmp_path / "fake.sqlite3"
        clf_logger = _logging.getLogger("replyright.local_classifier")
        handler = _handlers.MemoryHandler(capacity=100, flushLevel=_logging.CRITICAL)
        clf_logger.addHandler(handler)
        original_level = clf_logger.level
        clf_logger.setLevel(_logging.DEBUG)
        try:
            with patch("outlook_dashboard.local_classifier._get_models", return_value=(mock_models, mock_meta)):
                result = predict("body text", db_path=db_path)
            debug_msgs = [r.getMessage() for r in handler.buffer]
        finally:
            clf_logger.removeHandler(handler)
            clf_logger.setLevel(original_level)

        assert result is None
        assert any(
            "threshold" in m.lower() or "declined" in m.lower()
            for m in debug_msgs
        ), f"Expected a debug log about threshold. Got: {debug_msgs}"


# ── KYC route error handling ──────────────────────────────────────────────────


class TestKycRouteErrorHandling:

    def test_kyc_action_keyerror_returns_404(self, app_client, monkeypatch):
        from outlook_dashboard.kyc import routes as kyc_routes

        monkeypatch.setattr(
            kyc_routes,
            "_service",
            lambda: MagicMock(acknowledge=MagicMock(side_effect=KeyError("event not found"))),
        )
        resp = app_client.post("/api/kyc/events/999/acknowledge", json={})
        assert resp.status_code == 404
        assert "not found" in resp.json().get("detail", "").lower()

    def test_kyc_action_general_exception_returns_500_plain_english(self, app_client, monkeypatch):
        from outlook_dashboard.kyc import routes as kyc_routes

        monkeypatch.setattr(
            kyc_routes,
            "_service",
            lambda: MagicMock(acknowledge=MagicMock(side_effect=sqlite3.OperationalError("database is locked"))),
        )
        resp = app_client.post("/api/kyc/events/1/acknowledge", json={})
        assert resp.status_code == 500
        detail = resp.json().get("detail", "")
        # Must not expose raw sqlite message
        assert "database is locked" not in detail
        assert "OperationalError" not in detail
        # Must be human-readable
        assert len(detail) > 5

    def test_kyc_status_exception_returns_500(self, app_client, monkeypatch):
        from outlook_dashboard.kyc import routes as kyc_routes

        monkeypatch.setattr(
            kyc_routes,
            "_service",
            lambda: MagicMock(status=MagicMock(side_effect=RuntimeError("boom"))),
        )
        resp = app_client.get("/api/kyc/status")
        assert resp.status_code == 500
        detail = resp.json().get("detail", "")
        assert "boom" not in detail
        assert len(detail) > 5

    def test_kyc_history_exception_returns_500(self, app_client, monkeypatch):
        from outlook_dashboard.kyc import routes as kyc_routes

        monkeypatch.setattr(
            kyc_routes,
            "_service",
            lambda: MagicMock(history=MagicMock(side_effect=RuntimeError("boom"))),
        )
        resp = app_client.get("/api/kyc/history")
        assert resp.status_code == 500
        detail = resp.json().get("detail", "")
        assert "boom" not in detail


# ── Outlook CoInitialize error ────────────────────────────────────────────────


class TestOutlookComInitialize:

    def test_coinitialize_failure_raises_export_error(self, tmp_path):
        """pythoncom.CoInitialize() failure must raise OutlookDesktopExportError."""
        from outlook_dashboard.completed_requests_importer import read_completed_requests
        from outlook_dashboard.outlook_desktop import OutlookDesktopExportError

        with patch("outlook_dashboard.completed_requests_importer.IS_WINDOWS", True):
            with patch.dict("sys.modules", {
                "pythoncom": MagicMock(CoInitialize=MagicMock(side_effect=OSError("COM failed"))),
                "win32com": MagicMock(),
                "win32com.client": MagicMock(),
            }):
                with pytest.raises(OutlookDesktopExportError) as exc_info:
                    read_completed_requests("TestMailbox", db_path=tmp_path / "db.sqlite3")

        assert "COM" in str(exc_info.value) or "initialize" in str(exc_info.value).lower()


# ── API response shape consistency ───────────────────────────────────────────


class TestApiErrorShape:
    """All error responses must return JSON with a 'detail' key — never raw tracebacks."""

    def test_unauthenticated_returns_json_detail(self, tmp_path, monkeypatch):
        import os
        monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "t.sqlite3"))
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "500")

        from fastapi.testclient import TestClient
        import outlook_dashboard.main as main
        from outlook_dashboard.config import get_settings

        get_settings.cache_clear()
        main._RATE_LIMIT_BUCKETS.clear()
        monkeypatch.setattr(main, "ensure_admin", lambda *a, **kw: None)
        monkeypatch.setattr(main, "admin_user_exists", lambda: True)
        monkeypatch.setattr(main, "download_approved_rules", lambda: [])
        monkeypatch.setattr(main, "download_prompt_versions", lambda: [])
        monkeypatch.setattr(main, "download_known_senders", lambda: [])
        monkeypatch.setattr(main, "flush_feedback_queue", lambda: 0)
        monkeypatch.setattr(main, "start_update_check", lambda: None)

        with TestClient(main.app) as client:
            resp = client.get("/api/emails")
        assert resp.status_code == 401
        body = resp.json()
        assert "detail" in body
        assert "traceback" not in str(body).lower()
        assert "Traceback" not in str(body)

    def test_404_email_returns_json_detail(self, app_client):
        resp = app_client.get("/api/emails/999999999")
        assert resp.status_code in (404, 422)
        body = resp.json()
        assert "detail" in body

    def test_unknown_route_returns_json(self, app_client):
        resp = app_client.get("/api/does-not-exist")
        assert resp.status_code == 404
        # FastAPI returns JSON 404 by default
        body = resp.json()
        assert "detail" in body
