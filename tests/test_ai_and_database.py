from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from outlook_dashboard import supabase_client
from outlook_dashboard.ai import (
    _arrival_urgency_score,
    _gemini_schema,
    heuristic_analysis,
    infer_feedback_corrections,
    latest_message_text,
    triage_conversation,
    triage_email,
)
from outlook_dashboard.database import (
    cache_classification_rules,
    cache_known_senders,
    cache_prompt_versions,
    consume_reset_token,
    delete_emails_not_in_graph_ids,
    detect_rule_candidates,
    enqueue_feedback_upload,
    get_email,
    initialize_database,
    list_cached_classification_rules,
    list_cached_known_senders,
    list_cached_prompt_versions,
    list_emails,
    list_pending_feedback_uploads,
    list_recent_triage_feedback,
    managed_connect,
    mark_feedback_upload_succeeded,
    save_analysis,
    save_triage_feedback,
    set_rule_candidate_status,
    upsert_email,
)


class EmailDashboardTests(unittest.TestCase):
    def test_heuristic_flags_accessibility_request(self) -> None:
        email = {
            "subject": "Accessible room request",
            "sender_name": "Priya Shah",
            "sender_email": "priya@example.com",
            "body_text": "Please confirm an accessible room with a roll-in shower and shower chair.",
            "importance": "normal",
        }
        analysis = heuristic_analysis(email)
        self.assertEqual(analysis["category"], "Accessibility request")
        self.assertIn("ADA / accessibility", analysis["risk_flags"])
        self.assertIn(analysis["priority_level"], {"High", "Immediate"})

    def test_database_deduplicates_graph_message_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.sqlite3"
            initialize_database(db_path)
            sample = {
                "graph_message_id": "sample-outlook-message-001",
                "subject": "Accessible room request",
                "sender_name": "Priya Shah",
                "sender_email": "priya@example.com",
                "body_text": "Please confirm an accessible room with a roll-in shower.",
                "body_preview": "Please confirm an accessible room with a roll-in shower.",
                "conversation_id": "sample-conversation-001",
                "source": "outlook_desktop",
                "mailbox_mode": "shared",
            }
            first_id, first_inserted = upsert_email(sample, db_path)
            second_id, second_inserted = upsert_email(sample, db_path)
            self.assertEqual(first_id, second_id)
            self.assertTrue(first_inserted)
            self.assertFalse(second_inserted)

            email = get_email(first_id, db_path)
            self.assertIsNotNone(email)
            analysis = heuristic_analysis(email or {})
            save_analysis(first_id, analysis, db_path)
            rows = list_emails(db_path=db_path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["category"], analysis["category"])

    def test_arrival_date_drives_urgency_score(self) -> None:
        today = date(2026, 5, 16)
        self.assertEqual(_arrival_urgency_score("Guest arrival 5/16", today), 5)
        self.assertEqual(_arrival_urgency_score("Checking in tomorrow", today), 5)
        self.assertEqual(_arrival_urgency_score("Arrival May 20", today), 4)
        self.assertEqual(_arrival_urgency_score("Arrival May 30", today), 3)
        self.assertEqual(_arrival_urgency_score("Arrival September 10", today), 2)
        self.assertEqual(_arrival_urgency_score("Arrival January 10 2027", today), 1)
        self.assertEqual(_arrival_urgency_score("Guest Name : May 22-24, 2026", today), 4)

    def test_heuristic_uses_allowed_department_and_contact_type(self) -> None:
        analysis = heuristic_analysis(
            {
                "subject": "Rooming list for group arrival 5/20",
                "sender_name": "Avery Planner",
                "sender_email": "avery@eventagency.example",
                "body_text": "Please see the rooming list for our group block.",
                "importance": "normal",
            }
        )
        self.assertEqual(analysis["recommended_department_owner"], "Sales")
        self.assertEqual(analysis["contact_type"], "Group contact")
        self.assertNotIn(analysis["recommended_department_owner"], {"Management", "Manager"})

    def test_refresh_prune_removes_non_current_outlook_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.sqlite3"
            initialize_database(db_path)
            keep = {
                "graph_message_id": "outlook-current",
                "subject": "Current Outlook email",
                "source": "outlook_desktop",
            }
            stale = {
                "graph_message_id": "mock-stale",
                "subject": "Old mock email",
                "source": "mock",
            }
            upsert_email(keep, db_path)
            upsert_email(stale, db_path)
            deleted = delete_emails_not_in_graph_ids(["outlook-current"], db_path)
            rows = list_emails(db_path=db_path)
            self.assertEqual(deleted, 1)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["graph_message_id"], "outlook-current")

    def test_latest_message_text_ignores_quoted_upset_history(self) -> None:
        body = (
            "Hi Brian,\n\nThank you very much for sending that. I have just completed it.\n"
            "We appreciate your help!\n\nKindest Regards,\nStephanie\n\n"
            "-----Original Message-----\nFrom: Guest\nI am furious and want a manager."
        )
        latest = latest_message_text(body)
        self.assertIn("completed it", latest)
        self.assertNotIn("furious", latest)

        analysis = heuristic_analysis(
            {
                "subject": "Re: Completed form",
                "sender_name": "Alchemy Concierge",
                "sender_email": "stephanie@example.com",
                "body_text": body,
                "importance": "normal",
            }
        )
        self.assertEqual(analysis["guest_sentiment"], "Positive")
        self.assertNotEqual(analysis["category"], "Complaint")

    def test_conversation_feedback_learns_completed_cca_pattern(self) -> None:
        email = {
            "id": 1,
            "subject": "Re: CCA form for guest",
            "sender_name": "Travel Advisor",
            "sender_email": "advisor@example.com",
            "conversation_id": "conv-cca",
            "received_datetime": "2026-05-16T12:00:00Z",
            "body_text": "Thank you, I completed the credit card authorization form.",
            "importance": "normal",
        }
        feedback = {
            "conversation_id": "conv-cca",
            "email_id": 1,
            "feedback_text": "This is just a filled out CCA form; owner Reservations; urgency 3.",
            "corrected_urgency": 3,
        }
        analysis = triage_conversation([email], feedback_entries=[feedback])
        self.assertEqual(analysis["urgency_score"], 3)
        self.assertEqual(analysis["recommended_department_owner"], "Reservations")
        self.assertEqual(analysis["category"], "General inquiry")
        self.assertEqual(analysis["missing_information"], [])
        self.assertTrue(analysis["feedback_applied"])

    def test_triage_feedback_persists_as_long_term_memory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.sqlite3"
            initialize_database(db_path)
            email_id, _ = upsert_email(
                {
                    "graph_message_id": "outlook-current",
                    "subject": "CCA form",
                    "conversation_id": "conv-1",
                    "source": "outlook_desktop",
                },
                db_path,
            )
            feedback_id = save_triage_feedback(
                email_id=email_id,
                conversation_id="conv-1",
                feedback_text="Completed CCA form should be Reservations and urgency 3.",
                corrected_urgency=3,
                corrected_owner="Reservations",
                corrected_status="Completed",
                summary_quality_rating=5,
                reply_quality_rating=4,
                db_path=db_path,
            )
            self.assertGreater(feedback_id, 0)
            delete_emails_not_in_graph_ids(["other-current-id"], db_path)
            feedback = list_recent_triage_feedback(db_path=db_path)
            self.assertEqual(len(feedback), 1)
            self.assertEqual(feedback[0]["corrected_urgency"], 3)
            self.assertEqual(feedback[0]["corrected_status"], "Completed")
            self.assertEqual(feedback[0]["summary_quality_rating"], 5)
            self.assertEqual(feedback[0]["reply_quality_rating"], 4)

    def test_feedback_correction_inference_for_cca(self) -> None:
        corrections = infer_feedback_corrections(
            "This is just a completed CCA form. Apply it to the reservation, not Concierge. Urgency 3."
        )
        self.assertEqual(corrections["corrected_urgency"], 3)
        self.assertEqual(corrections["corrected_owner"], "Reservations")
        self.assertEqual(corrections["corrected_category"], "General inquiry")

    def test_gemini_schema_removes_unsupported_strict_flag(self) -> None:
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {"name": {"type": "string"}},
                    },
                }
            },
        }
        cleaned = _gemini_schema(schema)
        self.assertNotIn("additionalProperties", cleaned)
        self.assertNotIn("additionalProperties", cleaned["properties"]["items"]["items"])

    def test_password_reset_tokens_store_supabase_uuid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.sqlite3"
            initialize_database(db_path)
            user_id = "6f70cf38-5321-4c3e-9b28-20d7b0972f60"
            token = "reset-token"
            with managed_connect(db_path) as db:
                db.execute(
                    """
                    INSERT INTO password_reset_tokens (token, user_id, expires_at, created_at)
                    VALUES (?, ?, datetime('now', '+1 hour'), datetime('now'))
                    """,
                    (token, user_id),
                )
            self.assertEqual(consume_reset_token(token, db_path), user_id)

    def test_rule_candidates_auto_promote_after_five_corrections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.sqlite3"
            initialize_database(db_path)
            for index in range(5):
                email_id, _ = upsert_email(
                    {
                        "graph_message_id": f"travel-agency-{index}",
                        "subject": "Reservation follow-up",
                        "sender_email": f"agent{index}@agency.example",
                        "conversation_id": f"conv-{index}",
                        "source": "outlook_desktop",
                    },
                    db_path,
                )
                save_triage_feedback(
                    email_id=email_id,
                    conversation_id=f"conv-{index}",
                    feedback_text="This agency should route to Reservations.",
                    corrected_owner="Reservations",
                    db_path=db_path,
                )

            candidates = detect_rule_candidates(db_path)
            owner_candidate = next(c for c in candidates if c["type"] == "owner_by_domain")
            self.assertEqual(owner_candidate["correction_count"], 5)
            self.assertEqual(owner_candidate["status"], "auto_promoted")

    def test_rule_candidate_status_override_can_dismiss_bad_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.sqlite3"
            initialize_database(db_path)
            for index in range(3):
                email_id, _ = upsert_email(
                    {
                        "graph_message_id": f"sender-{index}",
                        "subject": "Owner correction",
                        "sender_email": f"agent{index}@agency.example",
                        "conversation_id": f"conv-{index}",
                        "source": "outlook_desktop",
                    },
                    db_path,
                )
                save_triage_feedback(
                    email_id=email_id,
                    conversation_id=f"conv-{index}",
                    feedback_text="Agency routes to Reservations.",
                    corrected_owner="Reservations",
                    db_path=db_path,
                )

            candidate = next(c for c in detect_rule_candidates(db_path) if c["type"] == "owner_by_domain")
            set_rule_candidate_status(
                candidate["key"],
                "dismissed",
                candidate_type=candidate["type"],
                pattern=candidate["pattern"],
                suggestion=candidate["suggestion"],
                db_path=db_path,
            )
            self.assertFalse(any(c["key"] == candidate["key"] for c in detect_rule_candidates(db_path)))

    def test_supabase_rules_and_feedback_queue_are_durable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.sqlite3"
            initialize_database(db_path)
            cache_classification_rules(
                [{"rule_key": "owner_domain_agency", "rule_type": "owner_by_domain", "status": "approved"}],
                db_path=db_path,
            )
            cached = list_cached_classification_rules(db_path=db_path)
            self.assertEqual(cached[0]["rule_key"], "owner_domain_agency")

            enqueue_feedback_upload({"email_fingerprint": "abc", "corrected_owner": "Reservations"}, db_path=db_path)
            pending = list_pending_feedback_uploads(db_path=db_path)
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0]["payload"]["corrected_owner"], "Reservations")
            mark_feedback_upload_succeeded(pending[0]["id"], db_path=db_path)
            self.assertEqual(list_pending_feedback_uploads(db_path=db_path), [])

    def test_supabase_prompt_and_known_sender_cache_are_durable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.sqlite3"
            initialize_database(db_path)
            cache_prompt_versions(
                [{"prompt_key": "refresh_classifier", "version": "v1", "status": "active"}],
                db_path=db_path,
            )
            cache_known_senders(
                [{"sender_domain": "agency.example", "default_owner": "Reservations", "contact_type": "Travel agency"}],
                db_path=db_path,
            )
            self.assertEqual(list_cached_prompt_versions(db_path=db_path)[0]["prompt_key"], "refresh_classifier")
            self.assertEqual(list_cached_known_senders(db_path=db_path)[0]["sender_domain"], "agency.example")

    def test_known_sender_cache_guides_local_triage(self) -> None:
        previous = list(supabase_client._known_senders_cache)
        supabase_client._known_senders_cache[:] = [
            {
                "sender_domain": "agency.example",
                "default_owner": "Reservations",
                "contact_type": "Travel agency",
            }
        ]
        try:
            analysis = triage_email(
                {
                    "subject": "Quick question",
                    "sender_name": "Travel Advisor",
                    "sender_email": "advisor@agency.example",
                    "body_text": "Please confirm the reservation.",
                }
            )
        finally:
            supabase_client._known_senders_cache[:] = previous
        self.assertEqual(analysis["recommended_department_owner"], "Reservations")
        self.assertEqual(analysis["contact_type"], "Travel agency")
        self.assertEqual(analysis["analysis_engine"], "heuristic+rules")


if __name__ == "__main__":
    unittest.main()
