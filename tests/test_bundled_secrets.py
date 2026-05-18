from __future__ import annotations

import os

from outlook_dashboard import bundled_secrets


def test_inject_sets_missing_env_vars(monkeypatch) -> None:
    monkeypatch.setattr(bundled_secrets, "_SECRETS", {"REPLYRIGHT_TEST_SECRET": "plain-value"})
    monkeypatch.delenv("REPLYRIGHT_TEST_SECRET", raising=False)

    bundled_secrets.inject()

    assert os.environ["REPLYRIGHT_TEST_SECRET"] == "plain-value"


def test_inject_does_not_overwrite_existing_env_vars(monkeypatch) -> None:
    monkeypatch.setattr(bundled_secrets, "_SECRETS", {"REPLYRIGHT_TEST_SECRET": "plain-value"})
    monkeypatch.setenv("REPLYRIGHT_TEST_SECRET", "local-value")

    bundled_secrets.inject()

    assert os.environ["REPLYRIGHT_TEST_SECRET"] == "local-value"


def test_secrets_dict_contains_no_privileged_keys() -> None:
    forbidden = {
        "SUPABASE_SERVICE_ROLE_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_AI_API_KEY",
        "GEMINI_API_KEY",
        "MICROSOFT_CLIENT_SECRET",
    }
    for key in bundled_secrets._SECRETS:
        assert key not in forbidden, f"Privileged key {key!r} must not appear in bundled_secrets._SECRETS"
