from __future__ import annotations

import base64

from outlook_dashboard import bundled_secrets


def _enc(value: str) -> str:
    key = bundled_secrets._K
    raw = value.encode("utf-8")
    return base64.b64encode(bytes(char ^ key[index % len(key)] for index, char in enumerate(raw))).decode("ascii")


def test_inject_sets_missing_env_vars(monkeypatch) -> None:
    monkeypatch.setattr(bundled_secrets, "_SECRETS", {"REPLYRIGHT_TEST_SECRET": _enc("sealed-value")})
    monkeypatch.delenv("REPLYRIGHT_TEST_SECRET", raising=False)

    bundled_secrets.inject()

    assert bundled_secrets.os.environ["REPLYRIGHT_TEST_SECRET"] == "sealed-value"


def test_inject_does_not_overwrite_existing_env_vars(monkeypatch) -> None:
    monkeypatch.setattr(bundled_secrets, "_SECRETS", {"REPLYRIGHT_TEST_SECRET": _enc("sealed-value")})
    monkeypatch.setenv("REPLYRIGHT_TEST_SECRET", "local-value")

    bundled_secrets.inject()

    assert bundled_secrets.os.environ["REPLYRIGHT_TEST_SECRET"] == "local-value"


def test_decryption_is_deterministic() -> None:
    encoded = _enc("same-input")

    assert bundled_secrets._dec(encoded) == "same-input"
    assert bundled_secrets._dec(encoded) == "same-input"
