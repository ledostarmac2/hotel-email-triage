from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional until dependencies are installed
    load_dotenv = None


ROOT_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent.parent
)
DATA_DIR = ROOT_DIR / "data"


def _load_env() -> None:
    if load_dotenv is not None:
        load_dotenv(ROOT_DIR / ".env")


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    microsoft_client_id: str
    microsoft_client_secret: str
    microsoft_tenant_id: str
    microsoft_redirect_uri: str
    shared_mailbox_email: str
    openai_api_key: str
    openai_model: str
    database_path: Path
    app_host: str
    app_port: int
    auto_seed_mock: bool

    @property
    def graph_scopes(self) -> tuple[str, ...]:
        return ("offline_access", "User.Read", "Mail.Read", "Mail.Read.Shared")

    @property
    def graph_scope_string(self) -> str:
        return " ".join(self.graph_scopes)

    @property
    def graph_configured(self) -> bool:
        return all(
            [
                self.microsoft_client_id,
                self.microsoft_client_secret,
                self.microsoft_tenant_id,
                self.microsoft_redirect_uri,
            ]
        )

    @property
    def openai_configured(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_env()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    database_path = Path(os.getenv("SQLITE_DB_PATH", str(DATA_DIR / "hotel_email_triage.sqlite3")))
    if not database_path.is_absolute():
        database_path = ROOT_DIR / database_path
    return Settings(
        microsoft_client_id=os.getenv("MICROSOFT_CLIENT_ID", "").strip(),
        microsoft_client_secret=os.getenv("MICROSOFT_CLIENT_SECRET", "").strip(),
        microsoft_tenant_id=os.getenv("MICROSOFT_TENANT_ID", "common").strip(),
        microsoft_redirect_uri=os.getenv(
            "MICROSOFT_REDIRECT_URI", "http://localhost:8000/auth/callback"
        ).strip(),
        shared_mailbox_email=os.getenv("SHARED_MAILBOX_EMAIL", "").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
        database_path=database_path,
        app_host=os.getenv("APP_HOST", "127.0.0.1").strip(),
        app_port=int(os.getenv("APP_PORT", "8000")),
        auto_seed_mock=_bool_env("AUTO_SEED_MOCK", True),
    )
