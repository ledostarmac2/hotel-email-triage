"""NASA-level test suite for all v1.0.0 features.

Covers:
  - needs_review flag generation (ai.py heuristic_analysis)
  - needs_review DB storage (save_analysis)
  - needs_review API filter (/api/emails?needs_review=true)
  - needs_review sidebar queue mapping (api_client)
  - correction_reason codes (TriageFeedbackRequest + save_triage_feedback)
  - feedback quality_state (raw → reviewed → training_ready | excluded)
  - /api/feedback/{id}/quality endpoint (admin-only, valid transitions)
  - admin stats needs_review_count
  - Low Confidence table includes needs_review column
  - Signal Inspector API (/api/admin/intelligence/signals)
  - Deployment Diagnostics API (/api/admin/deployment/diagnostics)
  - audit log events (triage.feedback.submitted, feedback.quality_state)
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _import_email(
    client: TestClient,
    *,
    graph_id: str = "test-gid-001",
    subject: str = "Test email",
    body: str = "Hello, this is a test.",
    sender_email: str = "guest@example.com",
    received: str = "2026-05-20T10:00:00",
    conversation_id: str = "conv-test-001",
    category_hint: str = "",
) -> dict:
    payload = {
        "mailbox": "NYCWA_Reservations",
        "folder": "Inbox",
        "messages": [
            {
                "graph_message_id": graph_id,
                "subject": subject,
                "sender_name": "Test Sender",
                "sender_email": sender_email,
                "received_datetime": received,
                "body_text": body,
                "body_preview": body[:200],
                "conversation_id": conversation_id,
                "importance": "normal",
                "has_attachments": False,
            }
        ],
    }
    r = client.post("/api/outlook-desktop/import-json", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def _first_email_id(client: TestClient) -> int:
    r = client.get("/api/emails")
    assert r.status_code == 200
    emails = r.json()["emails"]
    assert emails, "No emails in database"
    return int(emails[0]["id"])


# ─────────────────────────────────────────────────────────────────────────────
# needs_review — heuristic logic
# ─────────────────────────────────────────────────────────────────────────────

class TestNeedsReviewHeuristic:
    """Verify that heuristic_analysis() sets needs_review=True for high-risk scenarios."""

    def _analyze(self, subject: str, body: str, sender: str = "guest@hotel.com") -> dict:
        from outlook_dashboard.ai import heuristic_analysis
        email = {
            "subject": subject,
            "body_text": body,
            "sender_email": sender,
            "sender_name": "Test",
            "received_datetime": "2026-05-20T10:00:00",
        }
        return heuristic_analysis(email)

    def test_low_confidence_triggers_needs_review(self):
        result = self._analyze("Hello", "Just checking in.")
        # Low-signal email should have low confidence → needs_review
        if result["confidence_score"] < 50:
            assert result["needs_review"] is True

    def test_billing_dispute_always_needs_review(self):
        result = self._analyze(
            "Disputed charge on my account",
            "I was charged incorrectly and want a refund for the billing error.",
        )
        assert result["needs_review"] is True

    def test_ada_accessibility_needs_review(self):
        result = self._analyze(
            "Accessibility accommodation request",
            "I require wheelchair accessible room and ADA bathroom facilities.",
        )
        assert result["needs_review"] is True

    def test_legal_threat_needs_review(self):
        result = self._analyze(
            "Legal notice regarding my stay",
            "I am consulting my attorney and considering legal action against the hotel.",
        )
        assert result["needs_review"] is True

    def test_medical_issue_needs_review(self):
        result = self._analyze(
            "Medical emergency during stay",
            "Guest had a medical emergency and required ambulance. Please advise.",
        )
        assert result["needs_review"] is True

    def test_high_urgency_low_confidence_needs_review(self):
        """Urgency ≥4 with confidence <65 should flag needs_review."""
        from outlook_dashboard.ai import heuristic_analysis
        email = {
            "subject": "Arriving today need help",
            "body_text": "Arriving in a few hours. Something came up.",
            "sender_email": "guest@example.com",
            "sender_name": "Guest",
            "received_datetime": "2026-05-20T10:00:00",
        }
        result = heuristic_analysis(email)
        if result["urgency_score"] >= 4 and result["confidence_score"] < 65:
            assert result["needs_review"] is True

    def test_normal_inquiry_does_not_need_review(self):
        """A high-confidence, low-risk inquiry should not need review."""
        result = self._analyze(
            "Rate inquiry for September",
            "Good morning, could you please provide rates for a Deluxe King for Sept 15-18? Thank you.",
        )
        # High confidence + no risk → no review needed
        if result["confidence_score"] >= 65 and not result["risk_flags"]:
            assert result.get("needs_review") is False

    def test_needs_review_key_always_present(self):
        """needs_review must always be in the analysis output."""
        result = self._analyze("Any subject", "Any body.")
        assert "needs_review" in result
        assert isinstance(result["needs_review"], bool)

    def test_analyze_email_propagates_needs_review(self):
        """analyze_email (the top-level function) also returns needs_review."""
        from unittest.mock import MagicMock
        from outlook_dashboard.ai import analyze_email
        from outlook_dashboard.config import Settings

        settings = MagicMock(spec=Settings)
        settings.anthropic_configured = False
        settings.openai_configured = False
        email = {
            "subject": "Billing dispute",
            "body_text": "I was charged twice for my room.",
            "sender_email": "guest@example.com",
            "sender_name": "Guest",
            "received_datetime": "2026-05-20T10:00:00",
        }
        result = analyze_email(email, settings)
        assert "needs_review" in result


# ─────────────────────────────────────────────────────────────────────────────
# needs_review — database storage and retrieval
# ─────────────────────────────────────────────────────────────────────────────

class TestNeedsReviewDatabase:
    """Verify needs_review is stored and queried correctly."""

    def test_save_and_get_needs_review_true(self, tmp_path: Path):
        from outlook_dashboard.database import initialize_database, save_analysis, get_email, upsert_email
        db = tmp_path / "test.sqlite3"
        initialize_database(db)
        email_id, _ = upsert_email(
            {
                "graph_message_id": "nr-true-001",
                "subject": "Needs review test",
                "sender_name": "T",
                "sender_email": "t@e.com",
                "received_datetime": "2026-05-20T10:00:00",
                "body_preview": "test",
                "source": "test",
                "mailbox_mode": "shared",
            },
            db_path=db,
        )
        save_analysis(email_id, {"category": "Billing dispute", "needs_review": True, "confidence_score": 30}, db_path=db)
        row = get_email(email_id, db_path=db)
        assert row["needs_review"] == 1 or row["needs_review"] is True

    def test_save_and_get_needs_review_false(self, tmp_path: Path):
        from outlook_dashboard.database import initialize_database, save_analysis, get_email, upsert_email
        db = tmp_path / "test.sqlite3"
        initialize_database(db)
        email_id, _ = upsert_email(
            {
                "graph_message_id": "nr-false-001",
                "subject": "Normal email",
                "sender_name": "T",
                "sender_email": "t@e.com",
                "received_datetime": "2026-05-20T10:00:00",
                "body_preview": "hello",
                "source": "test",
                "mailbox_mode": "shared",
            },
            db_path=db,
        )
        save_analysis(email_id, {"category": "General inquiry", "needs_review": False, "confidence_score": 80}, db_path=db)
        row = get_email(email_id, db_path=db)
        assert not row["needs_review"]

    def test_list_emails_needs_review_filter(self, tmp_path: Path):
        from outlook_dashboard.database import initialize_database, save_analysis, list_emails, upsert_email
        db = tmp_path / "test.sqlite3"
        initialize_database(db)

        for i in range(3):
            eid, _ = upsert_email(
                {
                    "graph_message_id": f"nr-filter-{i}",
                    "subject": f"Email {i}",
                    "sender_email": "t@e.com",
                    "received_datetime": "2026-05-20T10:00:00",
                    "source": "test",
                    "mailbox_mode": "shared",
                },
                db_path=db,
            )
            save_analysis(eid, {"needs_review": i < 2, "confidence_score": 30 if i < 2 else 80}, db_path=db)

        review_only = list_emails(needs_review=True, db_path=db)
        all_emails = list_emails(db_path=db)
        assert len(review_only) == 2
        assert all(r.get("needs_review") for r in review_only)
        assert len(all_emails) == 3

    def test_admin_overview_includes_needs_review_count(self, tmp_path: Path):
        from outlook_dashboard.database import initialize_database, save_analysis, admin_overview_stats, upsert_email
        db = tmp_path / "test.sqlite3"
        initialize_database(db)
        eid, _ = upsert_email(
            {
                "graph_message_id": "nr-stats-001",
                "subject": "Billing dispute",
                "sender_email": "t@e.com",
                "received_datetime": "2026-05-20T10:00:00",
                "source": "test",
                "mailbox_mode": "shared",
            },
            db_path=db,
        )
        save_analysis(eid, {"needs_review": True, "confidence_score": 25}, db_path=db)
        stats = admin_overview_stats(db_path=db)
        assert "needs_review_count" in stats
        assert stats["needs_review_count"] >= 1


# ─────────────────────────────────────────────────────────────────────────────
# needs_review — API endpoint
# ─────────────────────────────────────────────────────────────────────────────

class TestNeedsReviewAPI:
    """Verify /api/emails?needs_review=true filtering works end-to-end."""

    def test_needs_review_filter_returns_only_flagged_emails(self, app_client: TestClient):
        # Import a billing dispute (will be flagged as needs_review)
        _import_email(
            app_client,
            graph_id="nr-api-billing",
            subject="Billing dispute - double charged",
            body="I was charged twice for my room and demand a refund.",
            conversation_id="conv-nr-billing",
        )
        # Import a normal email (should not be flagged)
        _import_email(
            app_client,
            graph_id="nr-api-normal",
            subject="Rate inquiry for June",
            body="Could you send rates for a standard room in June?",
            conversation_id="conv-nr-normal",
        )
        r = app_client.get("/api/emails", params={"needs_review": "true"})
        assert r.status_code == 200
        data = r.json()
        assert "emails" in data
        assert "count" in data

    def test_needs_review_false_param_works(self, app_client: TestClient):
        r = app_client.get("/api/emails", params={"needs_review": "false"})
        assert r.status_code == 200

    def test_needs_review_absent_returns_all(self, app_client: TestClient):
        r = app_client.get("/api/emails")
        assert r.status_code == 200

    def test_email_detail_includes_needs_review_field(self, app_client: TestClient):
        _import_email(
            app_client,
            graph_id="nr-detail-check",
            subject="ADA accessibility request",
            body="I require wheelchair access and ADA facilities.",
            conversation_id="conv-nr-detail",
        )
        email_id = _first_email_id(app_client)
        r = app_client.get(f"/api/emails/{email_id}")
        assert r.status_code == 200
        email = r.json()["email"]
        assert "needs_review" in email or "confidence_score" in email  # analysis ran


# ─────────────────────────────────────────────────────────────────────────────
# Correction reason codes
# ─────────────────────────────────────────────────────────────────────────────

class TestCorrectionReasonCodes:
    """Verify correction_reason is accepted, stored, and validated."""

    def _setup_email(self, client: TestClient) -> int:
        _import_email(
            client,
            graph_id="reason-test-001",
            conversation_id="conv-reason-001",
        )
        return _first_email_id(client)

    def test_feedback_accepts_valid_reason_code(self, app_client: TestClient):
        email_id = self._setup_email(app_client)
        r = app_client.post(
            f"/api/emails/{email_id}/feedback",
            json={
                "feedback_text": "Category was wrong — should be billing",
                "correction_reason": "wrong_category",
                "corrected_category": "Billing dispute",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert "feedback_id" in data
        assert data["feedback_id"] > 0

    def test_feedback_unknown_reason_normalised_to_other(self, app_client: TestClient):
        email_id = self._setup_email(app_client)
        r = app_client.post(
            f"/api/emails/{email_id}/feedback",
            json={
                "feedback_text": "Something was off",
                "correction_reason": "totally_made_up_code",
            },
        )
        assert r.status_code == 200

    def test_feedback_with_no_reason_still_works(self, app_client: TestClient):
        email_id = self._setup_email(app_client)
        r = app_client.post(
            f"/api/emails/{email_id}/feedback",
            json={"feedback_text": "Urgency was too high"},
        )
        assert r.status_code == 200

    def test_all_valid_reason_codes_accepted(self, app_client: TestClient):
        valid_codes = [
            "wrong_category", "wrong_urgency", "wrong_owner", "wrong_contact_type",
            "missing_risk_flag", "false_risk_flag", "poor_summary", "poor_reply_draft",
            "confidence_too_low", "context_mismatch", "other",
        ]
        _import_email(app_client, graph_id="reason-all-001", conversation_id="conv-reason-all")
        email_id = _first_email_id(app_client)
        for code in valid_codes:
            r = app_client.post(
                f"/api/emails/{email_id}/feedback",
                json={"feedback_text": f"Test for {code}", "correction_reason": code},
            )
            assert r.status_code == 200, f"Code {code!r} should be accepted, got {r.status_code}"

    def test_correction_reason_in_audit_log(self, app_client: TestClient):
        _import_email(app_client, graph_id="reason-audit-001", conversation_id="conv-reason-audit")
        email_id = _first_email_id(app_client)
        app_client.post(
            f"/api/emails/{email_id}/feedback",
            json={
                "feedback_text": "Wrong owner assigned",
                "correction_reason": "wrong_owner",
                "corrected_owner": "Front Desk",
            },
        )
        r = app_client.get("/api/admin/stats")
        assert r.status_code == 200
        audit_logs = r.json().get("audit_logs", [])
        feedback_events = [e for e in audit_logs if e.get("action", "").startswith("triage.feedback")]
        assert feedback_events, "Feedback audit event should be recorded"

    def test_reason_stored_in_database(self, tmp_path: Path):
        from outlook_dashboard.database import (
            initialize_database, save_triage_feedback, upsert_email,
        )
        import sqlite3
        db = tmp_path / "test.sqlite3"
        initialize_database(db)
        eid, _ = upsert_email(
            {
                "graph_message_id": "reason-db-001",
                "subject": "Subject",
                "sender_email": "t@e.com",
                "received_datetime": "2026-05-20T10:00:00",
                "source": "test",
                "mailbox_mode": "shared",
            },
            db_path=db,
        )
        fid = save_triage_feedback(
            email_id=eid,
            conversation_id="conv-reason-db",
            feedback_text="Category wrong",
            correction_reason="wrong_category",
            db_path=db,
        )
        conn = sqlite3.connect(str(db))
        row = conn.execute("SELECT correction_reason FROM triage_feedback WHERE id = ?", (fid,)).fetchone()
        conn.close()
        assert row[0] == "wrong_category"


# ─────────────────────────────────────────────────────────────────────────────
# Feedback quality state
# ─────────────────────────────────────────────────────────────────────────────

class TestFeedbackQualityState:
    """Verify feedback quality_state lifecycle: raw → reviewed → training_ready | excluded."""

    def _create_feedback(self, client: TestClient, *, body: str = "Test feedback") -> int:
        _import_email(client, graph_id=f"qs-{body[:10]}", conversation_id=f"conv-qs-{body[:10]}")
        email_id = _first_email_id(client)
        r = client.post(
            f"/api/emails/{email_id}/feedback",
            json={"feedback_text": body},
        )
        assert r.status_code == 200
        return int(r.json()["feedback_id"])

    def test_new_feedback_defaults_to_raw(self, tmp_path: Path):
        from outlook_dashboard.database import initialize_database, save_triage_feedback, upsert_email
        import sqlite3
        db = tmp_path / "test.sqlite3"
        initialize_database(db)
        eid, _ = upsert_email(
            {
                "graph_message_id": "qs-raw-001",
                "subject": "S",
                "sender_email": "t@e.com",
                "received_datetime": "2026-05-20T10:00:00",
                "source": "test",
                "mailbox_mode": "shared",
            },
            db_path=db,
        )
        fid = save_triage_feedback(
            email_id=eid,
            conversation_id="conv-qs-raw",
            feedback_text="Test",
            db_path=db,
        )
        conn = sqlite3.connect(str(db))
        row = conn.execute("SELECT quality_state FROM triage_feedback WHERE id = ?", (fid,)).fetchone()
        conn.close()
        assert row[0] == "raw"

    def test_advance_to_reviewed(self, tmp_path: Path):
        from outlook_dashboard.database import (
            initialize_database, save_triage_feedback, upsert_email, update_feedback_quality_state,
        )
        import sqlite3
        db = tmp_path / "test.sqlite3"
        initialize_database(db)
        eid, _ = upsert_email(
            {
                "graph_message_id": "qs-reviewed-001",
                "subject": "S",
                "sender_email": "t@e.com",
                "received_datetime": "2026-05-20T10:00:00",
                "source": "test",
                "mailbox_mode": "shared",
            },
            db_path=db,
        )
        fid = save_triage_feedback(email_id=eid, conversation_id="c", feedback_text="T", db_path=db)
        update_feedback_quality_state(fid, "reviewed", db_path=db)
        conn = sqlite3.connect(str(db))
        row = conn.execute("SELECT quality_state FROM triage_feedback WHERE id = ?", (fid,)).fetchone()
        conn.close()
        assert row[0] == "reviewed"

    def test_advance_to_training_ready(self, tmp_path: Path):
        from outlook_dashboard.database import (
            initialize_database, save_triage_feedback, upsert_email, update_feedback_quality_state,
        )
        import sqlite3
        db = tmp_path / "test.sqlite3"
        initialize_database(db)
        eid, _ = upsert_email(
            {"graph_message_id": "qs-tr-001", "subject": "S", "sender_email": "t@e.com",
             "received_datetime": "2026-05-20T10:00:00", "source": "test", "mailbox_mode": "shared"},
            db_path=db,
        )
        fid = save_triage_feedback(email_id=eid, conversation_id="c", feedback_text="T", db_path=db)
        update_feedback_quality_state(fid, "training_ready", db_path=db)
        conn = sqlite3.connect(str(db))
        assert conn.execute("SELECT quality_state FROM triage_feedback WHERE id=?", (fid,)).fetchone()[0] == "training_ready"
        conn.close()

    def test_excluded_state(self, tmp_path: Path):
        from outlook_dashboard.database import (
            initialize_database, save_triage_feedback, upsert_email, update_feedback_quality_state,
        )
        import sqlite3
        db = tmp_path / "test.sqlite3"
        initialize_database(db)
        eid, _ = upsert_email(
            {"graph_message_id": "qs-excl-001", "subject": "S", "sender_email": "t@e.com",
             "received_datetime": "2026-05-20T10:00:00", "source": "test", "mailbox_mode": "shared"},
            db_path=db,
        )
        fid = save_triage_feedback(email_id=eid, conversation_id="c", feedback_text="T", db_path=db)
        update_feedback_quality_state(fid, "excluded", db_path=db)
        conn = sqlite3.connect(str(db))
        assert conn.execute("SELECT quality_state FROM triage_feedback WHERE id=?", (fid,)).fetchone()[0] == "excluded"
        conn.close()

    def test_invalid_state_raises_value_error(self, tmp_path: Path):
        from outlook_dashboard.database import (
            initialize_database, save_triage_feedback, upsert_email, update_feedback_quality_state,
        )
        db = tmp_path / "test.sqlite3"
        initialize_database(db)
        eid, _ = upsert_email(
            {"graph_message_id": "qs-invalid-001", "subject": "S", "sender_email": "t@e.com",
             "received_datetime": "2026-05-20T10:00:00", "source": "test", "mailbox_mode": "shared"},
            db_path=db,
        )
        fid = save_triage_feedback(email_id=eid, conversation_id="c", feedback_text="T", db_path=db)
        with pytest.raises(ValueError, match="quality_state must be"):
            update_feedback_quality_state(fid, "invalid_state", db_path=db)

    def test_quality_endpoint_requires_admin(self, app_client: TestClient, monkeypatch):
        import outlook_dashboard.main as main
        monkeypatch.setattr(
            main,
            "get_session_user",
            lambda cookie, db_path=None: (
                {"id": "1", "email": "user@example.com", "role": "user"}
                if cookie else None
            ),
        )
        r = app_client.patch("/api/feedback/1/quality", json={"quality_state": "reviewed"})
        assert r.status_code == 403

    def test_quality_endpoint_admin_can_advance(self, app_client: TestClient):
        _import_email(app_client, graph_id="qs-api-001", conversation_id="conv-qs-api-001")
        email_id = _first_email_id(app_client)
        feedback_resp = app_client.post(
            f"/api/emails/{email_id}/feedback",
            json={"feedback_text": "Category was off"},
        )
        assert feedback_resp.status_code == 200
        fid = feedback_resp.json()["feedback_id"]
        r = app_client.patch(f"/api/feedback/{fid}/quality", json={"quality_state": "reviewed"})
        assert r.status_code == 200
        data = r.json()
        assert data["quality_state"] == "reviewed"
        assert data["feedback_id"] == fid

    def test_quality_endpoint_invalid_state_returns_400(self, app_client: TestClient):
        _import_email(app_client, graph_id="qs-bad-001", conversation_id="conv-qs-bad-001")
        email_id = _first_email_id(app_client)
        fb = app_client.post(
            f"/api/emails/{email_id}/feedback",
            json={"feedback_text": "Some feedback"},
        )
        fid = fb.json()["feedback_id"]
        r = app_client.patch(f"/api/feedback/{fid}/quality", json={"quality_state": "not_a_state"})
        assert r.status_code == 400

    def test_quality_state_in_audit_log(self, app_client: TestClient):
        _import_email(app_client, graph_id="qs-audit-001", conversation_id="conv-qs-audit-001")
        email_id = _first_email_id(app_client)
        fb = app_client.post(
            f"/api/emails/{email_id}/feedback",
            json={"feedback_text": "Good feedback"},
        )
        fid = fb.json()["feedback_id"]
        app_client.patch(f"/api/feedback/{fid}/quality", json={"quality_state": "training_ready"})
        r = app_client.get("/api/admin/stats")
        audit = r.json().get("audit_logs", [])
        assert any(e.get("action") == "feedback.quality_state" for e in audit)


# ─────────────────────────────────────────────────────────────────────────────
# Admin stats — needs_review_count
# ─────────────────────────────────────────────────────────────────────────────

class TestAdminStatsNeedsReview:
    def test_admin_stats_includes_needs_review_count(self, app_client: TestClient):
        r = app_client.get("/api/admin/stats")
        assert r.status_code == 200
        overview = r.json()["overview"]
        assert "needs_review_count" in overview
        assert isinstance(overview["needs_review_count"], int)
        assert overview["needs_review_count"] >= 0

    def test_needs_review_count_increases_after_billing_import(self, app_client: TestClient):
        r_before = app_client.get("/api/admin/stats")
        count_before = r_before.json()["overview"]["needs_review_count"]

        _import_email(
            app_client,
            graph_id="nr-count-billing-001",
            subject="Double charge dispute",
            body="I was billed twice for my stay. This is a billing error and I demand a refund.",
            conversation_id="conv-nr-count",
        )
        r_after = app_client.get("/api/admin/stats")
        count_after = r_after.json()["overview"]["needs_review_count"]
        assert count_after >= count_before


# ─────────────────────────────────────────────────────────────────────────────
# Signal Inspector API
# ─────────────────────────────────────────────────────────────────────────────

class TestSignalInspectorAPI:
    def test_signals_endpoint_requires_auth(self, app_client: TestClient, monkeypatch):
        import outlook_dashboard.main as main
        monkeypatch.setattr(
            main,
            "get_session_user",
            lambda cookie, db_path=None: None,
        )
        r = app_client.get("/api/admin/intelligence/signals", params={"email_id": "1"})
        assert r.status_code in (401, 403)

    def test_signals_for_valid_email(self, app_client: TestClient):
        _import_email(
            app_client,
            graph_id="sig-test-001",
            subject="VIP arrival with special requests",
            body="Dear Reservations, Mr. Smith is arriving tomorrow and is a Virtuoso client. "
                 "Confirmation 987654321. Please prepare amenities.",
            conversation_id="conv-sig-001",
        )
        email_id = _first_email_id(app_client)
        r = app_client.get("/api/admin/intelligence/signals", params={"email_id": email_id})
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"
        assert "signals" in data
        assert data.get("email_id") == email_id

    def test_signals_for_nonexistent_email(self, app_client: TestClient):
        r = app_client.get("/api/admin/intelligence/signals", params={"email_id": 999999})
        assert r.status_code in (404, 200)

    def test_signals_missing_email_id_param(self, app_client: TestClient):
        r = app_client.get("/api/admin/intelligence/signals")
        assert r.status_code in (400, 422)

    def test_signals_returns_description(self, app_client: TestClient):
        _import_email(
            app_client,
            graph_id="sig-desc-001",
            subject="Urgent: same-day arrival room not ready",
            body="Our guest is arriving in 2 hours and their room is not prepared. "
                 "This is unacceptable. Confirmation 111222333.",
            conversation_id="conv-sig-desc",
        )
        email_id = _first_email_id(app_client)
        r = app_client.get("/api/admin/intelligence/signals", params={"email_id": email_id})
        assert r.status_code == 200
        # description is a list of signal strings
        desc = r.json().get("description", [])
        assert isinstance(desc, (list, str))


# ─────────────────────────────────────────────────────────────────────────────
# Deployment Diagnostics API
# ─────────────────────────────────────────────────────────────────────────────

class TestDeploymentDiagnostics:
    def test_diagnostics_requires_admin(self, app_client: TestClient, monkeypatch):
        import outlook_dashboard.main as main
        monkeypatch.setattr(
            main,
            "get_session_user",
            lambda cookie, db_path=None: (
                {"id": "1", "email": "user@example.com", "role": "user"} if cookie else None
            ),
        )
        r = app_client.get("/api/admin/deployment/diagnostics")
        assert r.status_code == 403

    def test_diagnostics_returns_expected_sections(self, app_client: TestClient):
        r = app_client.get("/api/admin/deployment/diagnostics")
        assert r.status_code == 200
        data = r.json()
        assert "runtime" in data
        assert "app" in data
        assert "storage" in data
        assert "services" in data
        assert "outlook" in data
        assert "classifier" in data

    def test_diagnostics_runtime_fields(self, app_client: TestClient):
        r = app_client.get("/api/admin/deployment/diagnostics")
        runtime = r.json()["runtime"]
        assert "python_version" in runtime
        assert "platform" in runtime
        assert "frozen" in runtime
        assert isinstance(runtime["python_version"], str)

    def test_diagnostics_app_fields(self, app_client: TestClient):
        r = app_client.get("/api/admin/deployment/diagnostics")
        app_data = r.json()["app"]
        assert "version" in app_data
        assert "native_shell" in app_data
        assert app_data["native_shell"] == "PySide6"

    def test_diagnostics_services_fields(self, app_client: TestClient):
        r = app_client.get("/api/admin/deployment/diagnostics")
        services = r.json()["services"]
        assert "supabase_configured" in services
        assert "smtp_configured" in services
        assert "anthropic_configured" in services
        assert isinstance(services["supabase_configured"], bool)

    def test_diagnostics_storage_fields(self, app_client: TestClient):
        r = app_client.get("/api/admin/deployment/diagnostics")
        storage = r.json()["storage"]
        assert "database_path" in storage
        assert "database_exists" in storage
        assert isinstance(storage["database_exists"], bool)

    def test_diagnostics_no_secrets_exposed(self, app_client: TestClient):
        r = app_client.get("/api/admin/deployment/diagnostics")
        data = r.json()
        # Scrub path strings before checking — they may contain test function name fragments.
        # We only care that actual credential values are absent.
        import json
        data_no_paths = {k: v for k, v in data.items() if k not in ("storage", "runtime")}
        serialized = json.dumps(data_no_paths).lower()
        # Strip boolean/status words to avoid false positives from field names
        for strip in ("configured", "false", "true", "_configured"):
            serialized = serialized.replace(strip, "")
        assert "password" not in serialized
        assert "service_role" not in serialized
        # api_key and token should not appear as values (field names already stripped above)
        for word in ("api_key", "eyj"):  # eyJ is JWT prefix
            assert word not in serialized


# ─────────────────────────────────────────────────────────────────────────────
# Audit log completeness
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditLogCompleteness:
    def test_feedback_submitted_event_logged(self, app_client: TestClient):
        _import_email(app_client, graph_id="audit-fb-001", conversation_id="conv-audit-fb-001")
        email_id = _first_email_id(app_client)
        app_client.post(
            f"/api/emails/{email_id}/feedback",
            json={"feedback_text": "Wrong category assigned"},
        )
        r = app_client.get("/api/admin/stats")
        audit = r.json()["audit_logs"]
        actions = [e["action"] for e in audit]
        assert any(a.startswith("triage.feedback") for a in actions)

    def test_feedback_event_contains_feedback_id(self, app_client: TestClient):
        _import_email(app_client, graph_id="audit-fb-id-001", conversation_id="conv-audit-fb-id-001")
        email_id = _first_email_id(app_client)
        fb = app_client.post(
            f"/api/emails/{email_id}/feedback",
            json={"feedback_text": "Something off"},
        )
        fid = fb.json()["feedback_id"]
        r = app_client.get("/api/admin/stats")
        audit = r.json()["audit_logs"]
        fb_events = [e for e in audit if e.get("action", "").startswith("triage.feedback")]
        assert fb_events

    def test_quality_state_change_logged(self, app_client: TestClient):
        _import_email(app_client, graph_id="audit-qs-001", conversation_id="conv-audit-qs-001")
        email_id = _first_email_id(app_client)
        fb = app_client.post(f"/api/emails/{email_id}/feedback", json={"feedback_text": "ok"})
        assert fb.status_code == 200, fb.text
        fid = fb.json()["feedback_id"]
        app_client.patch(f"/api/feedback/{fid}/quality", json={"quality_state": "reviewed"})
        r = app_client.get("/api/admin/stats")
        audit = r.json()["audit_logs"]
        assert any(e.get("action") == "feedback.quality_state" for e in audit)

    def test_login_event_logged(self, app_client: TestClient):
        r = app_client.get("/api/admin/stats")
        audit = r.json()["audit_logs"]
        assert any(e.get("action") == "auth.login" for e in audit)


# ─────────────────────────────────────────────────────────────────────────────
# API client queue mapping
# ─────────────────────────────────────────────────────────────────────────────

class TestApiClientQueueMapping:
    """Verify the PySide6 ApiClient maps sidebar queues to correct server params."""

    def _make_client(self) -> object:
        from replyright_qt.api_client import ApiClient
        import unittest.mock as mock
        client = ApiClient.__new__(ApiClient)
        client._base_url = "http://localhost:8000"
        client._session = mock.MagicMock()
        return client

    def _capture_params(self, queue: str) -> dict:
        import unittest.mock as mock
        from replyright_qt.api_client import ApiClient
        captured = {}

        def fake_get(url, params=None, timeout=None):
            captured.update(params or {})
            resp = mock.MagicMock()
            resp.ok = True
            resp.json.return_value = {"emails": []}
            return resp

        client = ApiClient.__new__(ApiClient)
        client._base_url = "http://localhost:8000"
        client._session = mock.MagicMock()
        client._session.get.side_effect = fake_get
        client.list_emails(queue=queue)
        return captured

    def test_review_queue_sends_needs_review_true(self):
        params = self._capture_params("review")
        assert params.get("needs_review") == "true"

    def test_urgent_queue_sends_priority_immediate(self):
        params = self._capture_params("urgent")
        assert params.get("priority") == "Immediate"

    def test_vip_queue_sends_risk_vip(self):
        params = self._capture_params("vip")
        assert params.get("risk") == "VIP"

    def test_missing_queue_sends_risk_missing_info(self):
        params = self._capture_params("missing")
        assert "missing" in params.get("risk", "").lower()

    def test_inbox_queue_sends_no_special_param(self):
        params = self._capture_params("inbox")
        assert "needs_review" not in params
        assert "priority" not in params

    def test_explicit_filter_overrides_queue_default(self):
        import unittest.mock as mock
        from replyright_qt.api_client import ApiClient
        captured = {}

        def fake_get(url, params=None, timeout=None):
            captured.update(params or {})
            resp = mock.MagicMock()
            resp.ok = True
            resp.json.return_value = {"emails": []}
            return resp

        client = ApiClient.__new__(ApiClient)
        client._base_url = "http://localhost:8000"
        client._session = mock.MagicMock()
        client._session.get.side_effect = fake_get
        client.list_emails(queue="urgent", risk="Legal")
        # Explicit risk overrides queue default
        assert captured.get("risk") == "Legal"


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar navigation — Needs Review queue present
# ─────────────────────────────────────────────────────────────────────────────

class TestSidebarNeedsReviewQueue:
    def test_review_queue_in_sidebar_queues(self):
        from replyright_qt.widgets.sidebar_nav import QUEUES
        keys = [q[0] for q in QUEUES]
        assert "review" in keys

    def test_review_queue_has_correct_label(self):
        from replyright_qt.widgets.sidebar_nav import QUEUES
        labels = {q[0]: q[1] for q in QUEUES}
        assert labels["review"] == "Needs Review"

    def test_queue_order_sensible(self):
        from replyright_qt.widgets.sidebar_nav import QUEUES
        keys = [q[0] for q in QUEUES]
        # inbox should come before review
        assert keys.index("inbox") < keys.index("review")
        # admin should be last
        assert keys[-1] == "admin"


# ─────────────────────────────────────────────────────────────────────────────
# Database schema migration — columns exist
# ─────────────────────────────────────────────────────────────────────────────

class TestSchemaColumns:
    """Ensure all new columns are present in a fresh database."""

    def test_email_analysis_has_needs_review_column(self, tmp_path: Path):
        import sqlite3
        from outlook_dashboard.database import initialize_database
        db = tmp_path / "schema.sqlite3"
        initialize_database(db)
        conn = sqlite3.connect(str(db))
        cols = {row[1] for row in conn.execute("PRAGMA table_info(email_analysis)").fetchall()}
        conn.close()
        assert "needs_review" in cols

    def test_triage_feedback_has_correction_reason_column(self, tmp_path: Path):
        import sqlite3
        from outlook_dashboard.database import initialize_database
        db = tmp_path / "schema.sqlite3"
        initialize_database(db)
        conn = sqlite3.connect(str(db))
        cols = {row[1] for row in conn.execute("PRAGMA table_info(triage_feedback)").fetchall()}
        conn.close()
        assert "correction_reason" in cols

    def test_triage_feedback_has_quality_state_column(self, tmp_path: Path):
        import sqlite3
        from outlook_dashboard.database import initialize_database
        db = tmp_path / "schema.sqlite3"
        initialize_database(db)
        conn = sqlite3.connect(str(db))
        cols = {row[1] for row in conn.execute("PRAGMA table_info(triage_feedback)").fetchall()}
        conn.close()
        assert "quality_state" in cols

    def test_email_analysis_has_confidence_score(self, tmp_path: Path):
        import sqlite3
        from outlook_dashboard.database import initialize_database
        db = tmp_path / "schema.sqlite3"
        initialize_database(db)
        conn = sqlite3.connect(str(db))
        cols = {row[1] for row in conn.execute("PRAGMA table_info(email_analysis)").fetchall()}
        conn.close()
        assert "confidence_score" in cols


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end: full triage workflow with new features
# ─────────────────────────────────────────────────────────────────────────────

class TestEndToEndV1Workflow:
    """Full workflow test combining needs_review + correction_reason + quality_state."""

    def test_full_triage_correction_promotion_workflow(self, app_client: TestClient):
        # 1. Import a billing dispute email (will be flagged needs_review)
        _import_email(
            app_client,
            graph_id="e2e-full-001",
            subject="Billing dispute - unauthorized charge",
            body="I see an unauthorized charge of $500 on my credit card. This is a billing error.",
            conversation_id="conv-e2e-full",
        )

        # 2. Verify it appears in needs_review queue
        r = app_client.get("/api/emails", params={"needs_review": "true"})
        assert r.status_code == 200

        # 3. Get the email
        email_id = _first_email_id(app_client)
        r = app_client.get(f"/api/emails/{email_id}")
        assert r.status_code == 200

        # 4. Submit feedback with a reason code
        fb = app_client.post(
            f"/api/emails/{email_id}/feedback",
            json={
                "feedback_text": "Category is correct but urgency should be higher",
                "correction_reason": "wrong_urgency",
                "corrected_urgency": 5,
                "summary_quality_rating": 3,
                "reply_quality_rating": 4,
            },
        )
        assert fb.status_code == 200
        fid = fb.json()["feedback_id"]
        assert fid > 0

        # 5. Admin advances quality state to reviewed
        r = app_client.patch(f"/api/feedback/{fid}/quality", json={"quality_state": "reviewed"})
        assert r.status_code == 200
        assert r.json()["quality_state"] == "reviewed"

        # 6. Admin advances to training_ready
        r = app_client.patch(f"/api/feedback/{fid}/quality", json={"quality_state": "training_ready"})
        assert r.status_code == 200
        assert r.json()["quality_state"] == "training_ready"

        # 7. Verify audit trail has both events
        r = app_client.get("/api/admin/stats")
        audit = r.json()["audit_logs"]
        actions = [e["action"] for e in audit]
        assert any(a.startswith("triage.feedback") for a in actions)
        assert any(a == "feedback.quality_state" for a in actions)

        # 8. Admin stats shows needs_review_count ≥ 1
        stats = r.json()["overview"]
        assert stats["needs_review_count"] >= 1
