from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from outlook_dashboard.ai import heuristic_analysis
from outlook_dashboard.database import get_email, initialize_database, list_emails, save_analysis, upsert_email
from outlook_dashboard.mock_data import build_mock_emails


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
            sample = build_mock_emails()[0]
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


if __name__ == "__main__":
    unittest.main()
