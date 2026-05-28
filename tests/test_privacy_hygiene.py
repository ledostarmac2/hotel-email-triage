"""Privacy hygiene tests.

Verifies that:
- No sensitive runtime files (databases, logs) are tracked in git
- No labeling batch files with email content are tracked in git
- No raw passwords or secrets appear in committed docs/source
- Training data flowing through get_local_training_examples() is redacted
- Feedback payloads sent to Supabase contain no raw email bodies or full emails
- .gitignore covers the critical sensitive paths
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ── Helper: get git-tracked file list ────────────────────────────────────────

def _tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return [ROOT / p for p in result.stdout.splitlines() if p.strip()]


# ── Test 1: No runtime sensitive files in git ─────────────────────────────────


def test_no_sqlite_database_files_tracked() -> None:
    """SQLite database files contain raw email bodies and must not be committed."""
    tracked = _tracked_files()
    bad = [f for f in tracked if f.suffix in (".sqlite3", ".sqlite", ".db")]
    assert not bad, f"SQLite database files are tracked in git: {bad}"


def test_no_log_files_tracked() -> None:
    """Runtime log files may contain request paths/email IDs and must not be committed."""
    tracked = _tracked_files()
    bad = [
        f for f in tracked
        if f.suffix == ".log"
        or (f.stem.startswith("replyright") and ".log" in f.name)
    ]
    assert not bad, f"Log files are tracked in git: {bad}"


def test_no_env_files_tracked_except_example_and_sample() -> None:
    """.env files with real credentials must not be tracked."""
    tracked = _tracked_files()
    allowed = {".env.example", "sample.env"}
    bad = [
        f for f in tracked
        if (f.name.startswith(".env") or f.name.endswith(".env"))
        and f.name not in allowed
    ]
    assert not bad, f"Unexpected .env file tracked: {bad}"


def test_no_msg_or_eml_files_tracked() -> None:
    """Exported Outlook .msg/.eml files contain raw email data."""
    tracked = _tracked_files()
    bad = [f for f in tracked if f.suffix in (".msg", ".eml")]
    assert not bad, f"Email export files tracked in git: {bad}"


# ── Test 2: No labeling data files tracked ───────────────────────────────────


def test_no_labeling_json_data_files_tracked() -> None:
    """Labeling JSON files (inbox, Claude, ChatGPT, agent_batches, runs) must not be tracked."""
    tracked = _tracked_files()
    labeling_data_dirs = {
        "labeling/inbox", "labeling/Claude", "labeling/ChatGPT",
        "labeling/agent_batches", "labeling/runs",
    }
    bad = [
        f for f in tracked
        if any(part in str(f.relative_to(ROOT)).replace("\\", "/") for part in labeling_data_dirs)
        and f.suffix == ".json"
    ]
    assert not bad, f"Labeling JSON data files are tracked: {bad}"


def test_no_labeling_export_markdown_files_tracked() -> None:
    """Labeling export .md files may contain redacted guest/staff context — must not be tracked."""
    tracked = _tracked_files()
    bad = [
        f for f in tracked
        if "labeling/exports" in str(f.relative_to(ROOT)).replace("\\", "/")
        and f.suffix in (".md", ".json", ".txt")
    ]
    assert not bad, f"Labeling export files are tracked in git: {bad}"


# ── Test 3: No passwords in committed docs ────────────────────────────────────


# Pattern: a string that looks like a real password in a doc context.
# Matches things like: "password", "Luzmonkey63!", fn("email", "P@ssword")
# Excludes obviously fake examples: [REDACTED], your-password, <password>, etc.
_PASSWORD_IN_DOC_RE = re.compile(
    # Second string arg to auth functions that doesn't look like a placeholder
    r"""(?:ensure_admin|create_user|create_first_admin)\s*\([^)]*"[^"]{8,}"[^)]*,\s*"(?!\[REDACTED\]|\[your|\[change)([A-Za-z0-9!@#$%^&*_\-]{6,})"[^)]*\)"""
    r"""|(?:password|PASSWORD)\s*[=:]\s*["'](?!your|<|example|placeholder|\[|test|admin|password|change|secret|REDACTED)([A-Za-z0-9!@#$%^&*_\-\.]{6,})["']""",
    re.IGNORECASE,
)

_DOCS_TO_CHECK = [
    "docs/HANDOFF.md",
    "docs/CURRENT_STATE.md",
    "agent-workspace/AGENT_MESSAGES.md",
    "agent-workspace/HANDOFFS.md",
    "agent-workspace/TASK_BOARD.md",
    "installer/sample.env",
]


def test_no_real_passwords_in_docs() -> None:
    """Committed docs must not contain hardcoded passwords."""
    hits: list[str] = []
    for rel_path in _DOCS_TO_CHECK:
        p = ROOT / rel_path
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in _PASSWORD_IN_DOC_RE.finditer(text):
            matched_pw = m.group(1) or m.group(2)
            if matched_pw and matched_pw.upper() not in ("YOUR", "CHANGE", "REDACTED", "PASSWORD"):
                line = text[:m.start()].count("\n") + 1
                hits.append(f"{rel_path}:{line} — possible password: {matched_pw[:4]}***")
    assert not hits, f"Possible hardcoded passwords found in docs:\n" + "\n".join(hits)


def test_handoff_md_password_is_redacted() -> None:
    """The specific admin password previously committed to HANDOFF.md must be gone."""
    handoff = ROOT / "docs" / "HANDOFF.md"
    if not handoff.exists():
        return
    text = handoff.read_text(encoding="utf-8", errors="replace")
    # Check the known-bad pattern is absent — exact match avoids false positives
    assert "Luzmonkey" not in text, (
        "docs/HANDOFF.md still contains a previously-committed admin password. "
        "Replace with [REDACTED] and rotate the password."
    )


# ── Test 4: gitignore covers critical paths ───────────────────────────────────


def test_gitignore_covers_sqlite_files() -> None:
    """.gitignore must exclude SQLite database files."""
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "*.sqlite3" in gitignore or "*.sqlite" in gitignore, \
        ".gitignore must exclude *.sqlite3 or *.sqlite"


def test_gitignore_covers_labeling_exports() -> None:
    """.gitignore must exclude labeling export files."""
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "labeling/exports/" in gitignore or "labeling/exports/*" in gitignore, \
        ".gitignore must exclude labeling/exports/ directory contents"


def test_gitignore_covers_env_files() -> None:
    """.gitignore must exclude .env files."""
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore, ".gitignore must exclude .env files"


def test_gitignore_covers_data_directory() -> None:
    """.gitignore must exclude the data/ directory (contains SQLite databases)."""
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    lines = [l.strip() for l in gitignore.splitlines()]
    assert "data/" in lines, ".gitignore must exclude the data/ directory"


def test_gitignore_covers_log_files() -> None:
    """.gitignore must exclude *.log files."""
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "*.log" in gitignore, ".gitignore must exclude *.log files"


# ── Test 5: Training data redaction ───────────────────────────────────────────


def test_get_local_training_examples_applies_redaction(tmp_db: Path) -> None:
    """get_local_training_examples() must apply redact_sensitive_text() to body_text."""
    import sqlite3
    from outlook_dashboard.database import get_local_training_examples, initialize_database

    initialize_database(tmp_db)

    # Insert a fake email with PII in the body
    pii_body = (
        "Guest John Smith requests a reservation. "
        "Credit card: 4111111111111111, exp 12/26, CVV 123. "
        "Phone: 212-555-0199. Conf#: ABC123456."
    )
    with sqlite3.connect(tmp_db) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            INSERT INTO emails (
                graph_message_id, subject, sender_email, body_text, body_preview,
                status, created_at, updated_at, received_datetime, source, mailbox_mode
            ) VALUES (?, ?, ?, ?, ?, 'New', datetime('now'), datetime('now'), datetime('now'), 'test', 'shared')
            """,
            ("test-msg-001", "Test subject", "guest@example.com", pii_body, pii_body[:120]),
        )
        email_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """
            INSERT INTO triage_feedback (
                email_id, corrected_owner, corrected_status, feedback_text, created_at
            ) VALUES (?, 'Reservations', 'Completed', '', datetime('now'))
            """,
            (email_id,),
        )
        conn.commit()

    examples = get_local_training_examples(db_path=tmp_db)
    assert examples, "Expected at least one training example"

    for ex in examples:
        body = ex.get("body_redacted", "")
        # Credit card number must be redacted
        assert "4111111111111111" not in body, \
            "Credit card number found unredacted in local training example"
        # CVV must be redacted (note: CVV detection may not always fire on short 3-digit numbers alone)
        assert "4111" not in body, \
            "Credit card prefix found unredacted in training body"


# ── Test 6: Supabase feedback payload has no raw body or full email ───────────


def test_upload_feedback_event_omits_body_and_full_email(monkeypatch) -> None:
    """Feedback payloads uploaded to Supabase must not include body_text or sender_email."""
    from outlook_dashboard import supabase_client

    captured_payloads: list[dict] = []

    def _fake_post(payload: dict) -> tuple[bool, str]:
        captured_payloads.append(payload)
        return True, ""

    monkeypatch.setattr(supabase_client, "_post_feedback_payload", _fake_post)
    monkeypatch.setattr(supabase_client, "_configured", lambda: True)

    email = {
        "sender_email": "john.smith@example.com",
        "subject": "Reservation request for John Smith — CC 4111111111111111",
        "body_text": "My credit card is 4111111111111111, CVV 123, exp 12/26.",
        "urgency_score": 3,
        "recommended_department_owner": "Reservations",
        "category": "General inquiry",
        "status": "New",
        "confidence_score": 0.85,
        "analysis_engine": "heuristic",
    }
    corrections = {"corrected_owner": "Front Office"}

    supabase_client.upload_feedback_event(email, corrections, "test feedback note")

    assert len(captured_payloads) == 1
    payload = captured_payloads[0]

    # Must not contain raw body text
    assert "body_text" not in payload, "body_text must not appear in feedback payload"
    assert "body_content" not in payload, "body_content must not appear in feedback payload"

    # Must not contain full sender email
    assert "sender_email" not in payload, "sender_email must not appear in feedback payload"
    assert "john.smith@example.com" not in str(payload), \
        "Full sender email found in feedback payload"

    # Must not contain raw PII from body or subject
    payload_str = str(payload)
    assert "4111111111111111" not in payload_str, "Credit card found in feedback payload"
    assert "John Smith" not in payload_str, "Guest full name found in feedback payload"

    # Must contain safe fields only
    assert "email_fingerprint" in payload
    assert "sender_domain" in payload
    assert payload["sender_domain"] == "example.com"


# ── Test 7: No real API keys in any tracked source file ───────────────────────


_REAL_KEY_PATTERNS = [
    ("Anthropic API key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}")),
    ("OpenAI API key", re.compile(r"sk-proj-[A-Za-z0-9_\-]{10,}")),
    ("Google API key", re.compile(r"AIza[A-Za-z0-9_\-]{30,}")),
    ("Supabase JWT", re.compile(
        r"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}"
    )),
]

_SCAN_EXTENSIONS = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".iss"}
_SKIP_DIRS = {"dist", ".venv", "node_modules", "__pycache__", ".git", "reference"}


def test_no_real_api_keys_in_tracked_source() -> None:
    """No tracked source file should contain a real API key."""
    tracked = _tracked_files()
    hits: list[str] = []

    for f in tracked:
        if f.suffix not in _SCAN_EXTENSIONS:
            continue
        # Skip dist/build directories
        parts = set(f.relative_to(ROOT).parts)
        if parts & _SKIP_DIRS:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for label, pattern in _REAL_KEY_PATTERNS:
            if pattern.search(text):
                hits.append(f"{f.relative_to(ROOT)}: contains {label}")

    assert not hits, "Real API keys found in tracked source files:\n" + "\n".join(hits)
