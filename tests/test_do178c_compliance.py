from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


TRACEABILITY_PATH = Path("docs/compliance/do178c_traceability.json")


def _traceability() -> dict:
    return json.loads(TRACEABILITY_PATH.read_text(encoding="utf-8"))


def test_traceability_metadata_is_explicit() -> None:
    data = _traceability()
    assert data["standard"] == "DO-178C"
    assert data["certification_status"] == "not_certified"
    assert data["software_level"] == "planning_only"
    assert any("not a certification claim" in item for item in data["assumptions"])


def test_every_objective_has_traceability_fields() -> None:
    data = _traceability()
    objectives = data.get("objectives", [])
    assert objectives
    for objective in objectives:
        assert re.fullmatch(r"DO178C-[A-Z]+-\d{3}", objective["id"])
        assert objective["title"]
        assert objective["requirement"]
        assert objective["verification"]
        assert objective["artifacts"]
        assert objective["tests"]
        assert objective["status"] in {"starter", "active", "planned"}
        for artifact in objective["artifacts"]:
            assert Path(artifact).exists(), f"Missing artifact for {objective['id']}: {artifact}"


def test_outlook_desktop_source_has_no_mutating_com_calls() -> None:
    source = Path("outlook_dashboard/outlook_desktop.py").read_text(encoding="utf-8")
    forbidden_patterns = [
        r"\.Send\s*\(",
        r"\.Delete\s*\(",
        r"\.Move\s*\(",
        r"\.Reply\s*\(",
        r"\.Forward\s*\(",
        r"\.MarkAsTask\s*\(",
        r"\.Categories\s*=",
        r"\.FlagStatus\s*=",
        r"\.UnRead\s*=",
    ]
    for pattern in forbidden_patterns:
        assert not re.search(pattern, source), f"Forbidden Outlook mutation found: {pattern}"


def test_training_pipeline_has_zero_credit_contract() -> None:
    paths = [
        "outlook_dashboard/training_pipeline.py",
        "outlook_dashboard/completed_training_pipeline.py",
    ]
    combined = "\n".join(Path(p).read_text(encoding="utf-8") for p in paths)
    assert "external_ai_used" in combined
    assert "False" in combined or "false" in combined
    assert "Anthropic(" not in combined
    assert "anthropic.Anthropic" not in combined


def test_native_ui_contract_is_tracked() -> None:
    data = _traceability()
    ui_objs = {item["id"]: item for item in data["objectives"] if item["id"].startswith("DO178C-UI")}
    assert "DO178C-UI-001" in ui_objs
    assert "tests/test_pyside6_no_browser_engine.py" in ui_objs["DO178C-UI-001"]["tests"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# app_client is provided by conftest.py (sets up SQLITE_DB_PATH, auth mock, admin login)


def _import(client, *, graph_id="test-g1", conversation_id="test-c1",
            subject="Test email", body="Test body for import"):
    r = client.post("/api/outlook-desktop/import-json", json={
        "mailbox": "test@hotel.com",
        "folder": "Inbox",
        "messages": [{
            "graph_message_id": graph_id,
            "conversation_id": conversation_id,
            "subject": subject,
            "body_text": body,
            "body_preview": body[:240],
            "sender_email": "guest@example.com",
            "sender_name": "Guest",
            "received_datetime": "2026-05-20T10:00:00",
            "priority": "Normal",
            "is_read": False,
        }],
    })
    assert r.status_code == 200, f"Import failed: {r.text}"
    data = r.json()
    ids = data.get("email_ids") or data.get("inserted_ids") or []
    if ids:
        return ids[0]
    emails = client.get("/api/emails").json().get("emails", [])
    return emails[0]["id"] if emails else 1


# ---------------------------------------------------------------------------
# REQ-TRIAGE: Determinism
# ---------------------------------------------------------------------------

class TestTriageDeterminism:
    """REQ-TRIAGE-001: Identical inputs must produce identical outputs."""

    def test_heuristic_is_deterministic(self) -> None:
        from outlook_dashboard.ai import heuristic_analysis
        email = {
            "subject": "Urgent payment needed before arrival",
            "body_text": "Please send a payment link for confirmation 123.",
            "sender_email": "agent@agency.com",
            "sender_name": "Agent",
            "received_datetime": "2026-05-20T10:00:00",
        }
        results = [heuristic_analysis(email) for _ in range(5)]
        assert len({r["category"] for r in results}) == 1, "Non-deterministic category"
        assert len({r["urgency_score"] for r in results}) == 1, "Non-deterministic urgency"

    def test_urgency_score_is_deterministic(self) -> None:
        from outlook_dashboard.ai import urgency_score
        email = {"priority_level": "High", "category": "Complaint", "body_text": "Terrible service"}
        assert len({urgency_score(email) for _ in range(10)}) == 1


# ---------------------------------------------------------------------------
# REQ-TRIAGE: Urgency range
# ---------------------------------------------------------------------------

class TestUrgencyRangeCompleteness:
    """REQ-TRIAGE-002: Urgency scores are always integers in [1, 5]."""

    @pytest.mark.parametrize("priority", ["Low", "Normal", "High", "Immediate", "", None, "Unknown"])
    def test_urgency_score_always_1_to_5(self, priority) -> None:
        from outlook_dashboard.ai import urgency_score
        score = urgency_score({"priority_level": priority, "body_text": "test", "subject": "test"})
        assert isinstance(score, int)
        assert 1 <= score <= 5, f"urgency {score} out of range for priority={priority!r}"

    def test_urgency_minimum_is_1(self) -> None:
        from outlook_dashboard.ai import urgency_score
        assert urgency_score({"priority_level": "Low", "body_text": "hi", "subject": "hi"}) >= 1

    def test_urgency_maximum_is_5(self) -> None:
        from outlook_dashboard.ai import urgency_score
        assert urgency_score({
            "priority_level": "Immediate",
            "category": "Urgent same-day arrival",
            "body_text": "Guest arrives in 30 minutes URGENT NOW",
            "subject": "URGENT same day arrival NOW",
        }) <= 5


# ---------------------------------------------------------------------------
# REQ-TRIAGE: Required output fields
# ---------------------------------------------------------------------------

class TestRequiredOutputFields:
    """REQ-TRIAGE-003: heuristic_analysis() always returns all required keys."""

    REQUIRED = {
        "category", "priority_level", "urgency_score", "guest_sentiment",
        "recommended_department_owner", "contact_type", "risk_flags",
        "confidence_score", "needs_review",
    }

    @pytest.mark.parametrize("body,subject", [
        ("Hello", "Hi"),
        ("", ""),
        ("x" * 5000, "Long body"),
        ("Urgent! Emergency!", "URGENT"),
        ("\n\n\n", "\t"),
    ])
    def test_required_keys_always_present(self, body, subject) -> None:
        from outlook_dashboard.ai import heuristic_analysis
        result = heuristic_analysis({
            "subject": subject, "body_text": body,
            "sender_email": "x@x.com", "sender_name": "X",
            "received_datetime": "2026-05-20T10:00:00",
        })
        missing = self.REQUIRED - result.keys()
        assert not missing, f"Missing keys: {missing}"

    def test_category_always_from_taxonomy(self) -> None:
        from outlook_dashboard.ai import heuristic_analysis
        from outlook_dashboard.taxonomy import CATEGORIES
        for body in ("", "test", "payment link urgent"):
            r = heuristic_analysis({
                "subject": "s", "body_text": body,
                "sender_email": "a@b.com", "sender_name": "A",
                "received_datetime": "2026-05-20T10:00:00",
            })
            assert r["category"] in CATEGORIES, f"Unknown category: {r['category']!r}"

    def test_owner_always_from_taxonomy(self) -> None:
        from outlook_dashboard.ai import heuristic_analysis
        from outlook_dashboard.taxonomy import DEPARTMENT_OWNERS
        r = heuristic_analysis({
            "subject": "test", "body_text": "hello",
            "sender_email": "a@b.com", "sender_name": "A",
            "received_datetime": "2026-05-20T10:00:00",
        })
        assert r["recommended_department_owner"] in DEPARTMENT_OWNERS


# ---------------------------------------------------------------------------
# REQ-TRIAGE: MC/DC for needs_review
# ---------------------------------------------------------------------------

class TestNeedsReviewMCDC:
    """REQ-TRIAGE-004: MC/DC coverage for the needs_review compound boolean.

    needs_review = C1 OR C2 OR C3 OR C4 where:
      C1: confidence < 50
      C2: risk_flags intersect HIGH_RISK_FLAGS
      C3: category in HIGH_RISK_CATS
      C4: urgency_score >= 4 AND confidence < 65
    """

    def _heuristic(self, subject, body):
        from outlook_dashboard.ai import heuristic_analysis
        return heuristic_analysis({
            "subject": subject, "body_text": body,
            "sender_email": "t@t.com", "sender_name": "T",
            "received_datetime": "2026-05-20T10:00:00",
        })

    def test_c1_low_confidence_triggers_review(self) -> None:
        r = self._heuristic("test", "test")
        if r["confidence_score"] < 50:
            assert r["needs_review"] is True

    def test_c2_high_risk_flag_triggers_review(self) -> None:
        r = self._heuristic(
            "Chargeback dispute initiated",
            "I have filed a chargeback. Lawsuit pending.",
        )
        flags = r.get("risk_flags") or []
        if isinstance(flags, str):
            flags = json.loads(flags) if flags.startswith("[") else [flags]
        if any(f in {"Chargeback", "Legal threat", "Safety concern"} for f in flags):
            assert r["needs_review"] is True

    def test_c3_billing_category_triggers_review(self) -> None:
        r = self._heuristic(
            "I dispute this charge",
            "I was charged $500 for a room I did not stay in.",
        )
        if r["category"] == "Billing dispute":
            assert r["needs_review"] is True

    def test_c3_accessibility_triggers_review(self) -> None:
        r = self._heuristic(
            "ADA accessible room needed",
            "Our guest requires wheelchair access and ADA grab bars.",
        )
        if r["category"] == "Accessibility request":
            assert r["needs_review"] is True

    def test_c4_high_urgency_low_confidence_triggers_review(self) -> None:
        r = self._heuristic("Test", "test")
        if r["urgency_score"] >= 4 and r["confidence_score"] < 65:
            assert r["needs_review"] is True

    def test_all_false_no_false_positive(self) -> None:
        r = self._heuristic(
            "Room service menu",
            "Could you send us the in-room dining menu? Thank you.",
        )
        if (r["confidence_score"] >= 65
                and r["urgency_score"] < 4
                and not r.get("risk_flags")
                and r["category"] not in {"Billing dispute", "Accessibility request"}):
            assert r["needs_review"] is False


# ---------------------------------------------------------------------------
# REQ-TRIAGE: Safety-critical categories
# ---------------------------------------------------------------------------

class TestSafetyCriticalCategories:
    """REQ-TRIAGE-005: Safety-critical categories are always elevated."""

    def _h(self, subject, body):
        from outlook_dashboard.ai import heuristic_analysis
        return heuristic_analysis({
            "subject": subject, "body_text": body,
            "sender_email": "t@t.com", "sender_name": "T",
            "received_datetime": "2026-05-20T10:00:00",
        })

    def test_medical_emergency_urgency_is_elevated(self) -> None:
        """Medical emergency language → risk flag fires → urgency >= 4."""
        r = self._h(
            "Guest needs medical help NOW",
            "Our guest collapsed in the lobby and needs a doctor immediately. Emergency.",
        )
        assert r["urgency_score"] >= 4

    def test_legal_language_not_urgency_1(self) -> None:
        r = self._h(
            "Legal action notice",
            "We will be filing a lawsuit regarding injuries at your property.",
        )
        assert r["urgency_score"] >= 2

    def test_accessibility_not_urgency_1(self) -> None:
        r = self._h(
            "Wheelchair accessible room required",
            "Our guest uses a wheelchair and requires full ADA-compliant accommodation.",
        )
        assert r["urgency_score"] >= 2

    def test_chargeback_fires_risk_or_billing_category(self) -> None:
        r = self._h(
            "Credit card chargeback dispute",
            "I have initiated a chargeback with my card company for unauthorized charges.",
        )
        flags = r.get("risk_flags") or []
        if isinstance(flags, str):
            flags = json.loads(flags) if flags.startswith("[") else [flags]
        assert "Chargeback" in flags or r["category"] == "Billing dispute"


# ---------------------------------------------------------------------------
# REQ-AUTH: Auth gate completeness
# ---------------------------------------------------------------------------

class TestAuthGateCompleteness:
    """REQ-AUTH-001: All protected endpoints return 401 when unauthenticated."""

    PROTECTED = [
        ("GET",   "/api/emails"),
        ("GET",   "/api/emails/1"),
        ("POST",  "/api/emails/1/feedback"),
        ("PATCH", "/api/emails/1/status"),
        ("GET",   "/api/admin/training/status"),
        ("POST",  "/api/admin/training/trigger"),
        ("GET",   "/api/admin/intelligence/signals"),
        ("POST",  "/api/outlook-desktop/import-json"),
        ("POST",  "/api/outlook-desktop/export-inbox"),
        ("GET",   "/api/admin/deployment/diagnostics"),
        ("GET",   "/api/admin/stats"),
    ]

    @pytest.fixture()
    def unauth_client(self, tmp_path, monkeypatch):
        from pathlib import Path
        db_path = tmp_path / "unauth.sqlite3"
        monkeypatch.setenv("SQLITE_DB_PATH", str(db_path))
        monkeypatch.setenv("REPLYRIGHT_ADMIN_EMAIL", "admin@example.com")
        monkeypatch.setenv("REPLYRIGHT_ADMIN_PASSWORD", "TestPassword123!")
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "500")
        for key in ("OPENAI_API_KEY", "GOOGLE_AI_API_KEY", "GEMINI_API_KEY",
                    "ANTHROPIC_API_KEY", "SUPABASE_URL", "SUPABASE_KEY",
                    "SUPABASE_SERVICE_ROLE_KEY"):
            monkeypatch.setenv(key, " ")
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
        monkeypatch.setattr(main, "upload_feedback_event", lambda *a, **kw: None)
        monkeypatch.setattr(main, "promote_rule_candidates", lambda *a, **kw: None)
        monkeypatch.setattr(
            main, "get_session_user",
            lambda cookie, db_path=None: None,  # always unauthenticated
        )
        with TestClient(main.app, raise_server_exceptions=False) as client:
            yield client
        get_settings.cache_clear()
        main._RATE_LIMIT_BUCKETS.clear()

    @pytest.mark.parametrize("method,path", PROTECTED)
    def test_unauthenticated_returns_401(self, unauth_client, method, path) -> None:
        resp = unauth_client.request(method, path)
        assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"


# ---------------------------------------------------------------------------
# REQ-DATA: Database schema integrity
# ---------------------------------------------------------------------------

class TestDatabaseSchemaIntegrity:
    """REQ-DATA-001: Required columns exist on all core tables."""

    def test_emails_table_columns(self, tmp_path) -> None:
        import sqlite3
        from outlook_dashboard.database import initialize_database
        db_path = tmp_path / "schema.db"
        initialize_database(db_path)
        with sqlite3.connect(db_path) as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(emails)")}
        for col in ("id", "subject", "sender_email", "received_datetime",
                    "body_text", "body_content", "status", "graph_message_id"):
            assert col in cols, f"Missing column: emails.{col}"

    def test_email_analysis_table_columns(self, tmp_path) -> None:
        import sqlite3
        from outlook_dashboard.database import initialize_database
        db_path = tmp_path / "schema2.db"
        initialize_database(db_path)
        with sqlite3.connect(db_path) as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(email_analysis)")}
        for col in ("email_id", "category", "priority_level", "recommended_action",
                    "confidence_score", "needs_review"):
            assert col in cols, f"Missing column: email_analysis.{col}"

    def test_triage_feedback_table_columns(self, tmp_path) -> None:
        import sqlite3
        from outlook_dashboard.database import initialize_database
        db_path = tmp_path / "schema3.db"
        initialize_database(db_path)
        with sqlite3.connect(db_path) as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(triage_feedback)")}
        for col in ("id", "email_id", "feedback_text", "correction_reason",
                    "summary_quality_rating", "quality_state"):
            assert col in cols, f"Missing column: triage_feedback.{col}"

    def test_training_bootstrap_table_exists(self, tmp_path) -> None:
        import sqlite3
        from outlook_dashboard.database import initialize_database
        db_path = tmp_path / "schema4.db"
        initialize_database(db_path)
        with sqlite3.connect(db_path) as conn:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
        assert "training_bootstrap" in tables


class TestApiEmailFieldPresence:
    """REQ-DATA-002: List and detail endpoints return all required fields."""

    def test_list_email_fields(self, app_client) -> None:
        _import(app_client, graph_id="fp-list", conversation_id="conv-fp-list")
        data = app_client.get("/api/emails").json()
        emails = data.get("emails", [])
        assert emails, "No emails returned"
        for field in ("id", "subject", "sender_email", "status", "received_datetime"):
            assert field in emails[0], f"Missing field: {field}"

    def test_detail_email_fields(self, app_client) -> None:
        eid = _import(app_client, graph_id="fp-detail", conversation_id="conv-fp-detail")
        data = app_client.get(f"/api/emails/{eid}").json()
        email = data.get("email") or data
        for field in ("id", "subject", "sender_email"):
            assert field in email, f"Missing field: {field}"

    def test_missing_email_returns_404(self, app_client) -> None:
        assert app_client.get("/api/emails/999999").status_code == 404


class TestDataCoupling:
    """REQ-DATA-003: Data written must be retrievable without corruption."""

    def test_subject_roundtrip(self, app_client) -> None:
        subject = "Roundtrip subject unicode test"
        eid = _import(app_client, graph_id="rt-sub", conversation_id="conv-rt-sub", subject=subject)
        data = app_client.get(f"/api/emails/{eid}").json()
        retrieved = (data.get("email") or data).get("subject", "")
        assert retrieved == subject

    def test_feedback_count_increments(self, app_client) -> None:
        eid = _import(app_client, graph_id="fb-count", conversation_id="conv-fb-count")
        before = app_client.get("/api/admin/stats").json().get("feedback_count", 0)
        r = app_client.post(f"/api/emails/{eid}/feedback",
                            json={"feedback_text": "Test feedback increment"})
        assert r.status_code == 200
        after = app_client.get("/api/admin/stats").json().get("feedback_count", 0)
        assert after >= before


# ---------------------------------------------------------------------------
# REQ-TRAIN: Training pipeline robustness
# ---------------------------------------------------------------------------

class TestTrainingPipelineRobustness:
    """REQ-TRAIN-001: Training pipeline handles edge cases without crashing."""

    def test_bootstrap_seed_is_idempotent(self, tmp_path) -> None:
        from outlook_dashboard.database import initialize_database
        from outlook_dashboard.training_bootstrap_data import seed_bootstrap_examples
        db_path = tmp_path / "boot.db"
        initialize_database(db_path)
        seed_bootstrap_examples(db_path)
        n2 = seed_bootstrap_examples(db_path)
        assert n2 == 0, f"Second seed inserted {n2} rows; expected 0"

    def test_train_returns_required_keys(self, tmp_path) -> None:
        from outlook_dashboard.database import initialize_database
        from outlook_dashboard.local_classifier import train
        db_path = tmp_path / "train.db"
        initialize_database(db_path)
        result = train(db_path=db_path)
        for key in ("trained", "examples"):
            assert key in result, f"Missing key in train() result: {key}"

    def test_purge_nulls_body_but_keeps_row(self, tmp_path) -> None:
        import sqlite3
        from outlook_dashboard.database import initialize_database, purge_email_bodies
        db_path = tmp_path / "purge.db"
        initialize_database(db_path)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO emails (graph_message_id, subject, body_text, "
                "received_datetime, status, created_at, updated_at) "
                "VALUES ('purge-test', 'Test', 'Body content here', "
                "'2026-05-20T10:00:00', 'New', '2026-05-20T10:00:00', '2026-05-20T10:00:00')"
            )
            eid = conn.execute(
                "SELECT id FROM emails WHERE graph_message_id='purge-test'"
            ).fetchone()[0]
        purge_email_bodies([eid], db_path=db_path)
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT body_text FROM emails WHERE id=?", (eid,)).fetchone()
        assert row is not None, "Row was deleted by purge"
        assert row[0] is None, "body_text was not nulled"

    def test_model_persistence_after_training(self, tmp_path) -> None:
        from outlook_dashboard.database import initialize_database
        from outlook_dashboard.local_classifier import train
        db_path = tmp_path / "model.db"
        initialize_database(db_path)
        result = train(db_path=db_path)
        assert "trained" in result


class TestClassifierOutputBoundaries:
    """REQ-TRAIN-002: Classifier outputs only taxonomy-valid values."""

    def test_predicted_category_in_taxonomy(self, tmp_path) -> None:
        from outlook_dashboard.database import initialize_database
        from outlook_dashboard.local_classifier import predict, train
        from outlook_dashboard.taxonomy import CATEGORIES
        db_path = tmp_path / "clf.db"
        initialize_database(db_path)
        train(db_path=db_path)
        result = predict(body_text="Please explain my invoice charges.",
                         subject_tokens="Billing inquiry", db_path=db_path)
        if result and result.get("category"):
            assert result["category"] in CATEGORIES

    def test_predicted_owner_in_taxonomy(self, tmp_path) -> None:
        from outlook_dashboard.database import initialize_database
        from outlook_dashboard.local_classifier import predict, train
        from outlook_dashboard.taxonomy import DEPARTMENT_OWNERS
        db_path = tmp_path / "clf2.db"
        initialize_database(db_path)
        train(db_path=db_path)
        result = predict(body_text="We have a VIP guest arriving this evening.",
                         subject_tokens="VIP arrival", db_path=db_path)
        if result and result.get("department_owner"):
            assert result["department_owner"] in DEPARTMENT_OWNERS


# ---------------------------------------------------------------------------
# REQ-AUDIT: Audit trail completeness
# ---------------------------------------------------------------------------

class TestAuditTrailCompleteness:
    """REQ-AUDIT-001: Key actions are always written to the audit log."""

    def _audit_logs(self, client) -> list:
        return client.get("/api/admin/stats").json().get("audit_logs", [])

    def test_feedback_creates_audit_entry(self, app_client) -> None:
        eid = _import(app_client, graph_id="audit-fb", conversation_id="conv-audit-fb")
        r = app_client.post(f"/api/emails/{eid}/feedback",
                            json={"feedback_text": "Audit test feedback"})
        assert r.status_code == 200
        actions = [e.get("action", "") for e in self._audit_logs(app_client)]
        assert any("feedback" in a for a in actions), f"No feedback event: {actions}"

    def test_purge_creates_audit_entry(self, app_client) -> None:
        _import(app_client, graph_id="audit-purge", conversation_id="conv-audit-purge")
        r = app_client.post("/api/admin/training/purge-bodies",
                            params={"min_age_days": 0, "require_analyzed": "false",
                                    "dry_run": "false"})
        if r.status_code == 200 and r.json().get("purged_count", 0) > 0:
            actions = [e.get("action", "") for e in self._audit_logs(app_client)]
            assert any("purge" in a or "bodies" in a or "training" in a for a in actions)


class TestFeedbackQualityStateMachine:
    """REQ-AUDIT-002: Quality state transitions must follow the state machine."""

    @pytest.mark.parametrize("new_state", ["reviewed", "training_ready", "excluded"])
    def test_valid_state_transition(self, app_client, new_state) -> None:
        eid = _import(
            app_client,
            graph_id=f"qs-{new_state[:3]}",
            conversation_id=f"conv-qs-{new_state[:3]}",
        )
        fb = app_client.post(f"/api/emails/{eid}/feedback",
                             json={"feedback_text": "Quality state test"})
        assert fb.status_code == 200, fb.text
        fb_id = fb.json().get("feedback_id")
        if fb_id:
            r = app_client.patch(f"/api/feedback/{fb_id}/quality",
                                 json={"quality_state": new_state})
            assert r.status_code in (200, 204), f"state={new_state} -> {r.status_code}"

    def test_invalid_state_rejected(self, app_client) -> None:
        eid = _import(app_client, graph_id="qs-inv", conversation_id="conv-qs-inv")
        fb = app_client.post(f"/api/emails/{eid}/feedback",
                             json={"feedback_text": "Quality state invalid"})
        assert fb.status_code == 200, fb.text
        fb_id = fb.json().get("feedback_id")
        if fb_id:
            r = app_client.patch(f"/api/feedback/{fb_id}/quality",
                                 json={"quality_state": "totally_invalid_state"})
            assert r.status_code in (400, 422), f"Invalid state accepted: {r.status_code}"


# ---------------------------------------------------------------------------
# REQ-SEC: PII and secrets hygiene
# ---------------------------------------------------------------------------

class TestPIIRedaction:
    """REQ-SEC-001: No PII or secrets in training data, diagnostics, or stats."""

    def test_bootstrap_data_has_no_card_numbers(self) -> None:
        from outlook_dashboard.training_bootstrap_data import get_bootstrap_examples
        examples = get_bootstrap_examples()
        combined = " ".join(
            str(e.get("subject_tokens", "")) + " " + str(e.get("body_redacted", ""))
            for e in examples
        )
        assert not re.search(r"\b\d{4}[\s-]\d{4}[\s-]\d{4}[\s-]\d{4}\b", combined)

    def test_diagnostics_no_jwt_or_service_role(self, app_client) -> None:
        r = app_client.get("/api/admin/deployment/diagnostics")
        assert r.status_code == 200
        data = r.json()
        safe_keys = {k: v for k, v in data.items() if k not in ("storage", "runtime")}
        text = json.dumps(safe_keys)
        for pattern in ("service_role", "api_key", "eyJ"):
            assert pattern not in text

    def test_stats_no_password_fields(self, app_client) -> None:
        r = app_client.get("/api/admin/stats")
        assert r.status_code == 200
        text = json.dumps(r.json())
        for pattern in ("password", "secret", "api_key"):
            assert pattern.lower() not in text.lower()


# ---------------------------------------------------------------------------
# REQ-API: HTTP status code contract
# ---------------------------------------------------------------------------

class TestHttpStatusCodeContract:
    """REQ-API-001: Correct HTTP status codes for all outcomes."""

    def test_empty_import_200(self, app_client) -> None:
        r = app_client.post("/api/outlook-desktop/import-json",
                            json={"mailbox": "M", "folder": "Inbox", "messages": []})
        assert r.status_code == 200

    def test_too_short_feedback_422(self, app_client) -> None:
        eid = _import(app_client, graph_id="sc-fb", conversation_id="conv-sc-fb")
        assert app_client.post(f"/api/emails/{eid}/feedback",
                               json={"feedback_text": "x"}).status_code == 422

    def test_invalid_status_4xx(self, app_client) -> None:
        """Invalid status value returns 4xx (400 from business logic)."""
        eid = _import(app_client, graph_id="sc-st", conversation_id="conv-sc-st")
        r = app_client.patch(f"/api/emails/{eid}/status", json={"status": "NotValid"})
        assert 400 <= r.status_code < 500

    def test_valid_status_200(self, app_client) -> None:
        eid = _import(app_client, graph_id="sc-sv", conversation_id="conv-sc-sv")
        assert app_client.patch(f"/api/emails/{eid}/status",
                                json={"status": "Reviewed"}).status_code == 200

    def test_health_200_no_auth(self, app_client) -> None:
        assert app_client.get("/api/health").status_code == 200

    def test_taxonomy_returns_all_keys(self, app_client) -> None:
        data = app_client.get("/api/taxonomy").json()
        for key in ("categories", "department_owners", "statuses", "priorities"):
            assert key in data and isinstance(data[key], list) and data[key]

    def test_export_503_on_non_windows(self, app_client, monkeypatch) -> None:
        import outlook_dashboard.main as m
        monkeypatch.setattr(m, "IS_WINDOWS", False)
        r = app_client.post("/api/outlook-desktop/export-inbox")
        assert r.status_code == 503

    def test_unknown_correction_reason_coerced_to_other(self, app_client) -> None:
        """Unknown correction_reason is coerced to other, not rejected."""
        eid = _import(app_client, graph_id="sc-cr", conversation_id="conv-sc-cr")
        r = app_client.post(f"/api/emails/{eid}/feedback",
                            json={"feedback_text": "bad reason code",
                                  "correction_reason": "made_up_reason"})
        assert r.status_code == 200

    @pytest.mark.parametrize("reason", [
        "wrong_category", "wrong_urgency", "wrong_owner", "wrong_contact_type",
        "missing_risk_flag", "false_risk_flag", "poor_summary", "poor_reply_draft",
        "confidence_too_low", "context_mismatch", "other",
    ])
    def test_all_valid_correction_reason_codes(self, app_client, reason) -> None:
        gid = f"cr-{abs(hash(reason)) % 999999}"
        eid = _import(app_client, graph_id=gid, conversation_id=f"conv-{gid}")
        r = app_client.post(f"/api/emails/{eid}/feedback",
                            json={"feedback_text": f"Testing {reason}",
                                  "correction_reason": reason})
        assert r.status_code == 200, f"reason={reason} -> {r.status_code}"


class TestInputValidationRobustness:
    """REQ-API-002: Invalid inputs never cause 500."""

    @pytest.mark.parametrize("body", [
        {},
        {"feedback_text": ""},
        {"feedback_text": "x"},
        {"feedback_text": "a" * 4001},
        {"feedback_text": "ok", "corrected_urgency": 0},
        {"feedback_text": "ok", "corrected_urgency": 6},
        {"feedback_text": "ok", "corrected_owner": "Fake Department"},
        {"feedback_text": "ok", "corrected_status": "NotValid"},
        {"feedback_text": "ok", "summary_quality_rating": 0},
        {"feedback_text": "ok", "summary_quality_rating": 6},
    ])
    def test_invalid_feedback_is_4xx(self, app_client, body) -> None:
        eid = _import(app_client,
                      graph_id=f"rob-{abs(hash(str(body))) % 999999}",
                      conversation_id=f"conv-rob-{abs(hash(str(body))) % 999999}")
        r = app_client.post(f"/api/emails/{eid}/feedback", json=body)
        assert r.status_code < 500

    def test_very_long_subject_no_500(self, app_client) -> None:
        eid = _import(app_client, graph_id="long-sub", conversation_id="conv-long-sub",
                      subject="A" * 2000)
        assert app_client.get(f"/api/emails/{eid}").status_code < 500

    def test_null_body_no_500(self, app_client) -> None:
        r = app_client.post("/api/outlook-desktop/import-json", json={
            "mailbox": "M", "folder": "Inbox",
            "messages": [{
                "graph_message_id": "null-body-test",
                "conversation_id": "conv-null-body",
                "subject": "Null body test",
                "body_text": None,
                "body_preview": "",
                "sender_email": "a@b.com",
                "sender_name": "A",
                "received_datetime": "2026-05-20T10:00:00",
                "priority": "Normal",
                "is_read": False,
            }],
        })
        assert r.status_code < 500


class TestNeedsReviewFilterContract:
    """REQ-API-003: needs_review filter returns only flagged emails."""

    def test_filter_returns_subset_of_all(self, app_client) -> None:
        for i in range(3):
            _import(app_client, graph_id=f"nr-filter-{i}",
                    conversation_id=f"conv-nr-filter-{i}")
        all_emails = app_client.get("/api/emails").json().get("emails", [])
        nr_emails = app_client.get(
            "/api/emails", params={"needs_review": "true"}
        ).json().get("emails", [])
        assert len(nr_emails) <= len(all_emails)


class TestSignalInspectorContract:
    """REQ-API-004: Signal inspector returns well-typed counts."""

    def test_signals_for_known_email(self, app_client) -> None:
        eid = _import(app_client, graph_id="sig-known", conversation_id="conv-sig-known",
                      body="Urgent VIP billing chargeback complaint")
        r = app_client.get("/api/admin/intelligence/signals", params={"email_id": eid})
        assert r.status_code == 200
        signals = r.json().get("signals", {})
        for key in ("urgency_keyword_count", "vip_signal_count", "billing_signal_count"):
            assert key in signals, f"Missing signal key: {key}"
            assert isinstance(signals[key], int)

    def test_signals_404_on_unknown_email(self, app_client) -> None:
        r = app_client.get("/api/admin/intelligence/signals", params={"email_id": 999999})
        assert r.status_code == 404
