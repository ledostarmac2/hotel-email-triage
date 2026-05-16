from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from datetime import date

from outlook_dashboard.ai import (
    _arrival_urgency_score,
    heuristic_analysis,
    infer_feedback_corrections,
    latest_message_text,
    triage_conversation,
)
from outlook_dashboard.database import (
    delete_emails_not_in_graph_ids,
    get_email,
    initialize_database,
    list_recent_triage_feedback,
    list_emails,
    save_analysis,
    save_triage_feedback,
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
                db_path=db_path,
            )
            self.assertGreater(feedback_id, 0)
            delete_emails_not_in_graph_ids(["other-current-id"], db_path)
            feedback = list_recent_triage_feedback(db_path=db_path)
            self.assertEqual(len(feedback), 1)
            self.assertEqual(feedback[0]["corrected_urgency"], 3)

    def test_feedback_correction_inference_for_cca(self) -> None:
        corrections = infer_feedback_corrections(
            "This is just a completed CCA form. Apply it to the reservation, not Concierge. Urgency 3."
        )
        self.assertEqual(corrections["corrected_urgency"], 3)
        self.assertEqual(corrections["corrected_owner"], "Reservations")
        self.assertEqual(corrections["corrected_category"], "General inquiry")


if __name__ == "__main__":
    unittest.main()
