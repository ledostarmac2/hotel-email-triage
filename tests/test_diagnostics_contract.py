"""Contract tests for admin diagnostic, classifier status, and rollback endpoints.

These tests verify response shape, field types, and security invariants for the
hardened endpoints added in the v1 readiness push.  They do NOT test the full
classifier training cycle — that lives in test_training_pipeline.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ── Shared helpers ────────────────────────────────────────────────────────────

_SECRET_SENTINELS = ("service_role", "eyJ", "api_key")


def _assert_no_secrets(data: dict) -> None:
    serialised = json.dumps(data)
    for sentinel in _SECRET_SENTINELS:
        assert sentinel not in serialised, (
            f"Diagnostics response contains sensitive sentinel {sentinel!r}"
        )


# ── /api/admin/deployment/diagnostics ────────────────────────────────────────


class TestDiagnosticsEndpoint:
    def test_returns_200(self, app_client: TestClient) -> None:
        r = app_client.get("/api/admin/deployment/diagnostics")
        assert r.status_code == 200

    def test_top_level_keys(self, app_client: TestClient) -> None:
        data = app_client.get("/api/admin/deployment/diagnostics").json()
        for key in ("runtime", "app", "storage", "services", "outlook", "classifier", "warnings"):
            assert key in data, f"Missing top-level key: {key!r}"

    def test_runtime_keys(self, app_client: TestClient) -> None:
        runtime = app_client.get("/api/admin/deployment/diagnostics").json()["runtime"]
        for key in ("frozen", "python_version", "platform", "executable"):
            assert key in runtime, f"Missing runtime key: {key!r}"
        assert isinstance(runtime["frozen"], bool)

    def test_services_keys(self, app_client: TestClient) -> None:
        services = app_client.get("/api/admin/deployment/diagnostics").json()["services"]
        for key in (
            "supabase_configured",
            "openai_configured",
            "google_ai_configured",
            "anthropic_configured",
            "graph_configured",
        ):
            assert key in services, f"Missing services key: {key!r}"
            assert isinstance(services[key], bool), f"{key!r} must be bool"

    def test_classifier_section_required_keys(self, app_client: TestClient) -> None:
        classifier = app_client.get("/api/admin/deployment/diagnostics").json()["classifier"]
        for key in (
            "has_model",
            "version_id",
            "trained_at",
            "targets",
            "examples_at_train_time",
            "examples_supabase",
            "examples_local",
            "accuracy_per_target",
        ):
            assert key in classifier, f"Missing classifier key: {key!r}"

    def test_classifier_section_types(self, app_client: TestClient) -> None:
        classifier = app_client.get("/api/admin/deployment/diagnostics").json()["classifier"]
        assert isinstance(classifier["has_model"], bool)
        assert isinstance(classifier["version_id"], str)
        assert isinstance(classifier["targets"], list)
        assert isinstance(classifier["accuracy_per_target"], dict)
        assert isinstance(classifier["examples_at_train_time"], int)
        assert isinstance(classifier["examples_supabase"], int)
        assert isinstance(classifier["examples_local"], int)

    def test_warnings_is_list(self, app_client: TestClient) -> None:
        data = app_client.get("/api/admin/deployment/diagnostics").json()
        assert isinstance(data["warnings"], list)

    def test_no_secrets_in_response(self, app_client: TestClient) -> None:
        data = app_client.get("/api/admin/deployment/diagnostics").json()
        _assert_no_secrets(data)

    def test_unauthenticated_returns_401(self) -> None:
        from outlook_dashboard import main
        from fastapi.testclient import TestClient as FreshClient
        with FreshClient(main.app) as c:
            r = c.get("/api/admin/deployment/diagnostics")
        assert r.status_code in (401, 403)

    def test_storage_has_database_path(self, app_client: TestClient) -> None:
        storage = app_client.get("/api/admin/deployment/diagnostics").json()["storage"]
        assert "database_path" in storage
        assert "database_exists" in storage
        assert isinstance(storage["database_exists"], bool)

    def test_outlook_section_present(self, app_client: TestClient) -> None:
        outlook = app_client.get("/api/admin/deployment/diagnostics").json()["outlook"]
        assert "windows" in outlook
        assert isinstance(outlook["windows"], bool)


# ── /api/admin/classifier/status ─────────────────────────────────────────────


class TestClassifierStatusEndpoint:
    def test_returns_200(self, app_client: TestClient) -> None:
        r = app_client.get("/api/admin/classifier/status")
        assert r.status_code == 200

    def test_required_keys(self, app_client: TestClient) -> None:
        data = app_client.get("/api/admin/classifier/status").json()
        for key in (
            "has_model",
            "version_id",
            "trained_at",
            "total_examples_at_train_time",
            "examples_supabase",
            "examples_local",
            "available_training_examples",
            "targets_trained",
            "targets",
            "data_sources",
            "rollback_available",
            "warnings",
            "needs_training",
        ):
            assert key in data, f"Missing classifier status key: {key!r}"

    def test_field_types(self, app_client: TestClient) -> None:
        data = app_client.get("/api/admin/classifier/status").json()
        assert isinstance(data["has_model"], bool)
        assert isinstance(data["rollback_available"], bool)
        assert isinstance(data["needs_training"], bool)
        assert isinstance(data["warnings"], list)
        assert isinstance(data["data_sources"], list)
        assert isinstance(data["targets_trained"], list)
        assert isinstance(data["targets"], dict)
        assert isinstance(data["version_id"], str)
        assert isinstance(data["trained_at"], str)

    def test_no_model_state(self, app_client: TestClient) -> None:
        data = app_client.get("/api/admin/classifier/status").json()
        # With a fresh empty DB there's no trained model
        if not data["has_model"]:
            assert data["needs_training"] is True
            assert any("No trained model" in w for w in data["warnings"])

    def test_unauthenticated_returns_401(self) -> None:
        from outlook_dashboard import main
        from fastapi.testclient import TestClient as FreshClient
        with FreshClient(main.app) as c:
            r = c.get("/api/admin/classifier/status")
        assert r.status_code in (401, 403)

    def test_data_sources_values_are_strings(self, app_client: TestClient) -> None:
        data = app_client.get("/api/admin/classifier/status").json()
        for source in data["data_sources"]:
            assert isinstance(source, str)
            assert source in ("supabase", "local_feedback", "bootstrap"), (
                f"Unexpected data_source value: {source!r}"
            )


# ── /api/admin/classifier/rollback ───────────────────────────────────────────


class TestClassifierRollbackEndpoint:
    def test_returns_200(self, app_client: TestClient) -> None:
        r = app_client.post("/api/admin/classifier/rollback")
        assert r.status_code == 200

    def test_response_keys(self, app_client: TestClient) -> None:
        data = app_client.post("/api/admin/classifier/rollback").json()
        assert "rolled_back" in data, "Missing key: rolled_back"
        assert "version_id" in data, "Missing key: version_id"
        assert "reason" in data, "Missing key: reason"

    def test_field_types(self, app_client: TestClient) -> None:
        data = app_client.post("/api/admin/classifier/rollback").json()
        assert isinstance(data["rolled_back"], bool)
        assert isinstance(data["version_id"], str)
        assert isinstance(data["reason"], str)

    def test_no_previous_model_rolled_back_false(self, app_client: TestClient) -> None:
        # Fresh DB has no previous model blob → rolled_back must be False
        data = app_client.post("/api/admin/classifier/rollback").json()
        assert data["rolled_back"] is False
        assert data["reason"]  # must explain why

    def test_unauthenticated_returns_401(self) -> None:
        from outlook_dashboard import main
        from fastapi.testclient import TestClient as FreshClient
        with FreshClient(main.app) as c:
            r = c.post("/api/admin/classifier/rollback")
        assert r.status_code in (401, 403)


# ── Security: diagnostics must never leak secrets ─────────────────────────────


class TestClassifierPersistenceContract:
    def test_rollback_restores_previous_metadata_with_model(self, tmp_path: Path) -> None:
        from outlook_dashboard import local_classifier

        db_path = tmp_path / "classifier.sqlite"
        previous_meta = {
            "version_id": "previous-version",
            "trained_at": "2026-05-01T00:00:00+00:00",
            "total_examples_downloaded": 20,
            "examples_supabase": 5,
            "examples_local": 15,
            "targets": {"urgency": {"examples": 20, "classes": 2, "cv_accuracy": 0.75}},
        }
        current_meta = {
            "version_id": "current-version",
            "trained_at": "2026-05-02T00:00:00+00:00",
            "total_examples_downloaded": 30,
            "examples_supabase": 10,
            "examples_local": 20,
            "targets": {"urgency": {"examples": 30, "classes": 2, "cv_accuracy": 0.85}},
        }

        local_classifier.invalidate_cache()
        local_classifier._save_models({"urgency": "previous"}, previous_meta, db_path=db_path)
        local_classifier._save_models({"urgency": "current"}, current_meta, db_path=db_path)

        local_classifier.invalidate_cache()
        status_before = local_classifier.get_classifier_status(db_path=db_path)
        assert status_before["rollback_available"] is True
        assert status_before["version_id"] == "current-version"

        result = local_classifier.rollback_model(db_path=db_path)
        assert result["rolled_back"] is True
        assert result["version_id"] == "previous-version"

        local_classifier.invalidate_cache()
        status_after = local_classifier.get_classifier_status(db_path=db_path)
        assert status_after["version_id"] == "previous-version"
        assert status_after["examples_supabase"] == 5
        assert status_after["examples_local"] == 15

    def test_status_rollback_unavailable_without_previous_metadata(self, tmp_path: Path) -> None:
        from outlook_dashboard import local_classifier
        from outlook_dashboard.database import managed_connect
        from outlook_dashboard.text_utils import utc_now_iso

        db_path = tmp_path / "classifier.sqlite"
        local_classifier.invalidate_cache()
        local_classifier._save_models(
            {"urgency": "current"},
            {
                "version_id": "current-version",
                "trained_at": "2026-05-02T00:00:00+00:00",
                "total_examples_downloaded": 20,
                "targets": {},
            },
            db_path=db_path,
        )
        with managed_connect(db_path) as db:
            db.execute(
                "INSERT INTO app_kv (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (local_classifier._MODELS_KEY_PREV, b"model-only", utc_now_iso()),
            )

        status = local_classifier.get_classifier_status(db_path=db_path)
        assert status["rollback_available"] is False

        result = local_classifier.rollback_model(db_path=db_path)
        assert result["rolled_back"] is False
        assert "metadata" in result["reason"].lower()

    def test_train_persists_source_counts_in_metadata(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from outlook_dashboard import local_classifier

        owners = list(local_classifier.DEPARTMENT_OWNERS)[:2]
        categories = list(local_classifier.CATEGORIES)[:2]
        assert len(owners) >= 2
        assert len(categories) >= 2

        def make_example(index: int) -> dict:
            label_index = index % 2
            return {
                "subject_tokens": f"booking confirmation shared token {label_index}",
                "body_redacted": (
                    f"shared reservation training text pattern {label_index} "
                    f"guest asks about stay details sample {index}"
                ),
                "label_urgency": 1 if label_index == 0 else 3,
                "label_owner": owners[label_index],
                "label_category": categories[label_index],
            }

        supabase_examples = [make_example(i) for i in range(12)]
        local_examples = [make_example(i + 100) for i in range(12)]
        monkeypatch.setattr(local_classifier, "_download_training_examples", lambda: supabase_examples)
        monkeypatch.setattr(local_classifier, "_load_local_examples", lambda db_path=None: local_examples)

        db_path = tmp_path / "classifier.sqlite"
        local_classifier.invalidate_cache()
        result = local_classifier.train(db_path=db_path)
        assert result["trained"] is True
        assert result["examples_supabase"] == 12
        assert result["examples_local"] == 12

        local_classifier.invalidate_cache()
        meta = local_classifier.get_model_meta(db_path=db_path)
        assert meta["examples_supabase"] == 12
        assert meta["examples_local"] == 12


class TestDiagnosticsSecretRedaction:
    """Belt-and-suspenders: even if a setting value leaks into the response
    shape, the paranoid JSON-scan guard in the endpoint must add a warning."""

    def test_no_jwt_bearer_token_in_response(self, app_client: TestClient) -> None:
        # eyJhbGci... is the base64-encoded JWT header — a real Supabase service-role
        # key always starts with this prefix.  The test env sets all keys to " " (space),
        # so no such prefix should appear in the diagnostics payload.
        data = app_client.get("/api/admin/deployment/diagnostics").json()
        text = json.dumps(data)
        assert "eyJhbGci" not in text, "JWT bearer token prefix found in diagnostics response"

    def test_no_jwt_prefix_in_response(self, app_client: TestClient) -> None:
        data = app_client.get("/api/admin/deployment/diagnostics").json()
        text = json.dumps(data)
        assert "eyJ" not in text

    def test_warning_key_is_a_list_not_a_string(self, app_client: TestClient) -> None:
        data = app_client.get("/api/admin/deployment/diagnostics").json()
        assert isinstance(data["warnings"], list), (
            "warnings must be a list so the sentinel-redaction guard can append without error"
        )

    def test_secret_like_warning_value_is_redacted(
        self,
        app_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from outlook_dashboard import main

        real_settings = main.get_settings()

        class SettingsProxy:
            def __getattr__(self, name: str):
                return getattr(real_settings, name)

            @property
            def runtime_warnings(self) -> list[str]:
                return ["misconfigured api_key value eyJ should not leave diagnostics"]

        monkeypatch.setattr(main, "get_settings", lambda: SettingsProxy())

        data = app_client.get("/api/admin/deployment/diagnostics").json()
        text = json.dumps(data)
        assert "api_key" not in text
        assert "eyJ" not in text
        assert "[redacted]" in text
        assert any("sensitive-looking content was removed" in warning for warning in data["warnings"])
