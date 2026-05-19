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
    Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
)
DATA_DIR = ROOT_DIR / "data"


def _load_env() -> None:
    if load_dotenv is not None:
        load_dotenv(ROOT_DIR / ".env")
    try:
        from .bundled_secrets import inject as _inject_bundled

        _inject_bundled()
    except Exception:
        pass


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    microsoft_client_id: str
    microsoft_client_secret: str
    microsoft_tenant_id: str
    microsoft_redirect_uri: str
    shared_mailbox_email: str
    openai_api_key: str
    openai_model: str
    google_ai_api_key: str
    google_ai_model: str
    anthropic_api_key: str
    anthropic_model: str
    database_path: Path
    outlook_export_mailbox: str
    outlook_export_folder: str
    outlook_export_dir: Path
    outlook_export_macro: str
    app_host: str
    app_port: int
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    replyright_admin_email: str
    replyright_admin_password: str
    rate_limit_per_minute: int
    supabase_url: str
    supabase_key: str
    supabase_service_role_key: str

    @property
    def graph_scopes(self) -> tuple[str, ...]:
        return ("offline_access", "User.Read", "Mail.Read", "Mail.Read.Shared")

    @property
    def graph_scope_string(self) -> str:
        return " ".join(self.graph_scopes)

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)

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

    @property
    def google_ai_configured(self) -> bool:
        return bool(self.google_ai_api_key)

    @property
    def anthropic_configured(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def ai_configured(self) -> bool:
        return self.anthropic_configured or self.openai_configured or self.google_ai_configured

    @property
    def refresh_ai_configured(self) -> bool:
        return self.openai_configured or self.google_ai_configured

    @property
    def runtime_warnings(self) -> list[str]:
        warnings: list[str] = []
        if not self.replyright_admin_email or not self.replyright_admin_password:
            warnings.append("Local admin seed is not configured.")
        if not self.refresh_ai_configured:
            warnings.append("Refresh classification will use local deterministic fallback only.")
        graph_values = [
            self.microsoft_client_id,
            self.microsoft_client_secret,
            self.microsoft_tenant_id,
            self.microsoft_redirect_uri,
        ]
        if any(graph_values) and not self.graph_configured:
            warnings.append("Microsoft Graph configuration is incomplete.")
        smtp_values = [self.smtp_host, self.smtp_user, self.smtp_password, self.smtp_from]
        if any(smtp_values) and not self.smtp_configured:
            warnings.append("SMTP configuration is incomplete; invite/reset email may fail.")
        if self.rate_limit_per_minute <= 0:
            warnings.append("Auth rate limiting is disabled.")
        return warnings


def write_local_env(values: dict[str, str]) -> Path:
    """Merge key=value pairs into ROOT_DIR/.env and set them in os.environ.

    Existing keys in .env are preserved; the supplied values overwrite their
    entries.  Values are never logged.  Writes atomically (temp-then-rename).
    Returns the path of the written .env file.
    """
    import tempfile

    env_path = ROOT_DIR / ".env"
    existing: dict[str, str] = {}
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, _, v = stripped.partition("=")
                existing[k.strip()] = v
    existing.update(values)
    lines = [f"{k}={v}" for k, v in existing.items()]
    tmp_fd, tmp_path = tempfile.mkstemp(dir=ROOT_DIR, prefix=".env.tmp.", suffix="")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        os.replace(tmp_path, env_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    for k, v in values.items():
        os.environ[k] = v
    return env_path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_env()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _db_env = os.getenv("SQLITE_DB_PATH", "").strip()
    database_path = Path(_db_env) if _db_env else DATA_DIR / "hotel_email_triage.sqlite3"
    if not database_path.is_absolute():
        database_path = ROOT_DIR / database_path
    _export_env = os.getenv("OUTLOOK_EXPORT_DIR", "").strip()
    outlook_export_dir = Path(_export_env) if _export_env else DATA_DIR / "outlook_exports"
    if not outlook_export_dir.is_absolute():
        outlook_export_dir = ROOT_DIR / outlook_export_dir
    outlook_export_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        microsoft_client_id=os.getenv("MICROSOFT_CLIENT_ID", "").strip(),
        microsoft_client_secret=os.getenv("MICROSOFT_CLIENT_SECRET", "").strip(),
        microsoft_tenant_id=os.getenv("MICROSOFT_TENANT_ID", "common").strip(),
        microsoft_redirect_uri=os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:8000/auth/callback").strip(),
        shared_mailbox_email=os.getenv("SHARED_MAILBOX_EMAIL", "").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-nano").strip(),
        google_ai_api_key=(os.getenv("GOOGLE_AI_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip(),
        google_ai_model=os.getenv("GOOGLE_AI_MODEL", "gemini-3-flash-preview").strip(),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-opus-4-7").strip(),
        database_path=database_path,
        outlook_export_mailbox=os.getenv("OUTLOOK_EXPORT_MAILBOX", "NYCWA_Reservations").strip(),
        outlook_export_folder=os.getenv("OUTLOOK_EXPORT_FOLDER", "Inbox").strip(),
        outlook_export_dir=outlook_export_dir,
        outlook_export_macro=os.getenv("OUTLOOK_EXPORT_MACRO", "ExportNYCWAReservationsInboxOnly").strip(),
        app_host=os.getenv("APP_HOST", "127.0.0.1").strip(),
        app_port=_int_env("APP_PORT", 8000),
        smtp_host=os.getenv("SMTP_HOST", "smtp.office365.com").strip(),
        smtp_port=_int_env("SMTP_PORT", 587),
        smtp_user=os.getenv("SMTP_USER", "").strip(),
        smtp_password=os.getenv("SMTP_PASSWORD", "").strip(),
        smtp_from=os.getenv("SMTP_FROM", "").strip(),
        replyright_admin_email=os.getenv("REPLYRIGHT_ADMIN_EMAIL", "").strip(),
        replyright_admin_password=os.getenv("REPLYRIGHT_ADMIN_PASSWORD", "").strip(),
        rate_limit_per_minute=_int_env("RATE_LIMIT_PER_MINUTE", 30),
        supabase_url=os.getenv("SUPABASE_URL", "").strip(),
        supabase_key=os.getenv("SUPABASE_KEY", "").strip(),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
    )
