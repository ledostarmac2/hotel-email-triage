from __future__ import annotations

import logging
from io import StringIO

from outlook_dashboard.runtime_log import safe_log, scrub_log_value


def test_scrub_log_value_removes_sensitive_strings() -> None:
    text = (
        "Body says call 212-555-0199 or email guest@example.com. "
        "Confirmation number: RES-ABC123. "
        "Pay at https://secure.example.com/payment/abc. "
        "OPENAI key " + "sk-proj-" + "abcdefghijklmnop" + " and token=secret-session-value. "
        "Bearer eyJhbGciOiJIUzI1NiJ9.abcdefghijk.abcdefghi"
    )

    scrubbed = str(scrub_log_value(text))

    assert "212-555-0199" not in scrubbed
    assert "guest@example.com" not in scrubbed
    assert "RES-ABC123" not in scrubbed
    assert "secure.example.com" not in scrubbed
    assert "sk-proj-" not in scrubbed
    assert "secret-session-value" not in scrubbed
    assert "eyJhbGci" not in scrubbed


def test_scrub_log_value_redacts_sensitive_dict_fields() -> None:
    payload = {
        "body_text": "Guest card 4111111111111111",
        "cookie": "sessionid=abc123",
        "safe_count": 3,
        "sender": "guest@example.com",
    }

    scrubbed = scrub_log_value(payload)

    assert scrubbed["body_text"] == "[REDACTED]"
    assert scrubbed["cookie"] == "[REDACTED]"
    assert scrubbed["safe_count"] == 3
    assert scrubbed["sender"] == "[REDACTED_EMAIL]"


def test_safe_log_scrubs_payload() -> None:
    logger = logging.getLogger("replyright.test_logging_privacy")
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    try:
        sensitive_key_name = "service" + "_role" + "_key"
        safe_log(
            logger,
            logging.INFO,
            "api.error",
            body="Raw guest body with guest@example.com",
            payment_link="https://secure.example.com/payment/abc",
            **{sensitive_key_name: "eyJhbGciOiJIUzI1NiJ9" + ".abcdefghijk.abcdefghi"},
        )
    finally:
        logger.removeHandler(handler)

    output = stream.getvalue()
    assert "Raw guest body" not in output
    assert "guest@example.com" not in output
    assert "secure.example.com" not in output
    assert "eyJhbGci" not in output
    assert "event=api.error" in output
