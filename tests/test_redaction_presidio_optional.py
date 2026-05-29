from __future__ import annotations

import logging
from io import StringIO

from outlook_dashboard.config import get_settings
from outlook_dashboard.redaction import redact_sensitive_text


def test_presidio_redaction_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("REPLYRIGHT_ENABLE_PRESIDIO_REDACTION", raising=False)
    get_settings.cache_clear()

    redacted, counts = redact_sensitive_text("Guest Jane Smith called 212-555-0199.")

    assert "212-555-0199" not in redacted
    assert counts["phones"] == 1
    assert "presidio_entities" not in counts


def test_presidio_unavailable_falls_back_safely(monkeypatch) -> None:
    import outlook_dashboard.redaction as redaction

    monkeypatch.setenv("REPLYRIGHT_ENABLE_PRESIDIO_REDACTION", "1")
    get_settings.cache_clear()
    redaction._get_presidio_engines.cache_clear()

    def _missing():
        raise ImportError("missing presidio for guest@example.com")

    monkeypatch.setattr(redaction, "_get_presidio_engines", _missing)

    logger = logging.getLogger("replyright.redaction")
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    try:
        redacted, counts = redact_sensitive_text("Email guest@example.com and call 212-555-0199.")
    finally:
        logger.removeHandler(handler)

    output = stream.getvalue()
    assert "guest@example.com" not in redacted
    assert "212-555-0199" not in redacted
    assert counts["emails"] == 1
    assert counts["phones"] == 1
    assert "guest@example.com" not in output
    assert "event=redaction.presidio_unavailable" in output


def test_presidio_failure_falls_back_safely(monkeypatch) -> None:
    import outlook_dashboard.redaction as redaction

    class FailingAnalyzer:
        def analyze(self, **kwargs):
            raise RuntimeError("failed on 212-555-0199")

    class DummyAnonymizer:
        pass

    monkeypatch.setenv("REPLYRIGHT_ENABLE_PRESIDIO_REDACTION", "1")
    get_settings.cache_clear()
    monkeypatch.setattr(redaction, "_get_presidio_engines", lambda: (FailingAnalyzer(), DummyAnonymizer()))

    logger = logging.getLogger("replyright.redaction")
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    try:
        redacted, counts = redact_sensitive_text("Call 212-555-0199 for confirmation number RES-ABC123.")
    finally:
        logger.removeHandler(handler)

    output = stream.getvalue()
    assert "212-555-0199" not in redacted
    assert "RES-ABC123" not in redacted
    assert counts["phones"] == 1
    assert "212-555-0199" not in output
    assert "RES-ABC123" not in output
    assert "event=redaction.presidio_failed" in output


def test_presidio_success_adds_flat_counts(monkeypatch) -> None:
    import outlook_dashboard.redaction as redaction

    class Result:
        entity_type = "PERSON"

    class Analyzer:
        def analyze(self, **kwargs):
            return [Result()]

    class Anonymized:
        text = "Guest <PERSON> needs assistance."

    class Anonymizer:
        def anonymize(self, **kwargs):
            return Anonymized()

    monkeypatch.setenv("REPLYRIGHT_ENABLE_PRESIDIO_REDACTION", "1")
    get_settings.cache_clear()
    monkeypatch.setattr(redaction, "_get_presidio_engines", lambda: (Analyzer(), Anonymizer()))

    redacted, counts = redact_sensitive_text("Guest Jane Smith needs assistance.")

    assert redacted == "Guest <PERSON> needs assistance."
    assert counts["presidio_entities"] == 1
    assert counts["presidio_person"] == 1
