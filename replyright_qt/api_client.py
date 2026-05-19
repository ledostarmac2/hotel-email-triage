from __future__ import annotations

import requests
from PySide6.QtCore import QThread, Signal


class ApiError(Exception):
    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


class ApiClient:
    """Thin synchronous wrapper around the local FastAPI backend.

    Designed to be called from QThread workers — never call from the main thread
    directly (it will block the UI).
    """

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()

    def _url(self, path: str) -> str:
        return f"{self._base_url}/{path.lstrip('/')}"

    def _raise_for(self, resp: requests.Response) -> dict:
        if not resp.ok:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise ApiError(str(detail), resp.status_code)
        try:
            return resp.json()
        except Exception:
            return {}

    # ── Auth ──────────────────────────────────────────────────────────────────

    def login(self, email: str, password: str) -> dict:
        resp = self._session.post(
            self._url("/api/auth/login"),
            json={"email": email, "password": password},
            timeout=10,
        )
        return self._raise_for(resp)

    def logout(self) -> None:
        try:
            self._session.post(self._url("/api/auth/logout"), timeout=5)
        except Exception:
            pass
        self._session.cookies.clear()

    def get_current_user(self) -> dict:
        resp = self._session.get(self._url("/api/auth/me"), timeout=5)
        return self._raise_for(resp)

    # ── Emails ────────────────────────────────────────────────────────────────

    def list_emails(
        self,
        queue: str = "inbox",
        category: str = "",
        status: str = "",
        risk: str = "",
        q: str = "",
    ) -> list[dict]:
        params: dict[str, str] = {}
        if category:
            params["category"] = category
        if status:
            params["status"] = status
        if risk:
            params["risk"] = risk
        if q:
            params["q"] = q
        resp = self._session.get(self._url("/api/emails"), params=params, timeout=15)
        data = self._raise_for(resp)
        if isinstance(data, list):
            return data
        return data.get("emails", [])

    def get_email_detail(self, email_id: str) -> dict:
        resp = self._session.get(self._url(f"/api/emails/{email_id}"), timeout=10)
        return self._raise_for(resp)

    def update_email_status(self, email_id: str, status: str) -> dict:
        resp = self._session.patch(
            self._url(f"/api/emails/{email_id}/status"),
            json={"status": status},
            timeout=10,
        )
        return self._raise_for(resp)

    def analyze_email(self, email_id: str) -> dict:
        resp = self._session.post(
            self._url(f"/api/emails/{email_id}/analyze"), timeout=60
        )
        return self._raise_for(resp)

    def submit_feedback(self, email_id: str, payload: dict) -> dict:
        resp = self._session.post(
            self._url(f"/api/emails/{email_id}/feedback"),
            json=payload,
            timeout=10,
        )
        return self._raise_for(resp)

    # ── Sync ──────────────────────────────────────────────────────────────────

    def sync_outlook(self) -> dict:
        resp = self._session.post(self._url("/api/sync/outlook"), timeout=60)
        return self._raise_for(resp)

    # ── Taxonomy & config ──────────────────────────────────────────────────────

    def get_taxonomy(self) -> dict:
        resp = self._session.get(self._url("/api/taxonomy"), timeout=5)
        return self._raise_for(resp)

    def get_admin_stats(self) -> dict:
        resp = self._session.get(self._url("/api/admin/stats"), timeout=15)
        return self._raise_for(resp)

    def get_startup_state(self) -> dict:
        resp = self._session.get(self._url("/api/auth/startup-state"), timeout=5)
        return self._raise_for(resp)

    def credentials_setup(
        self,
        supabase_url: str,
        supabase_key: str,
        supabase_service_role_key: str,
        anthropic_api_key: str = "",
    ) -> dict:
        resp = self._session.post(
            self._url("/api/auth/credentials-setup"),
            json={
                "supabase_url": supabase_url,
                "supabase_key": supabase_key,
                "supabase_service_role_key": supabase_service_role_key,
                "anthropic_api_key": anthropic_api_key,
            },
            timeout=10,
        )
        return self._raise_for(resp)

    def forgot_password(self, email: str) -> dict:
        resp = self._session.post(
            self._url("/api/auth/forgot-password"),
            json={"email": email},
            timeout=10,
        )
        return self._raise_for(resp)

    def setup_admin(self, email: str, password: str) -> dict:
        resp = self._session.post(
            self._url("/api/auth/setup"),
            json={"email": email, "password": password},
            timeout=10,
        )
        return self._raise_for(resp)

    # ── User management ────────────────────────────────────────────────────────

    def list_users(self) -> list[dict]:
        resp = self._session.get(self._url("/api/auth/users"), timeout=10)
        data = self._raise_for(resp)
        return data.get("users", [])

    def delete_user(self, user_id: str) -> dict:
        resp = self._session.delete(self._url(f"/api/auth/users/{user_id}"), timeout=10)
        return self._raise_for(resp)

    def invite_user(self, email: str) -> dict:
        resp = self._session.post(
            self._url("/api/auth/invite"),
            json={"email": email},
            timeout=10,
        )
        return self._raise_for(resp)

    # ── KYC Inspections ───────────────────────────────────────────────────────

    def kyc_get_status(self) -> dict:
        """GET /api/kyc/status → {"status": KycStatus}"""
        resp = self._session.get(self._url("/api/kyc/status"), timeout=5)
        data = self._raise_for(resp)
        return data.get("status", data)

    def kyc_get_config(self) -> dict:
        """GET /api/kyc/config → {"settings": KycSettings}"""
        resp = self._session.get(self._url("/api/kyc/config"), timeout=5)
        data = self._raise_for(resp)
        return data.get("settings", data)

    def kyc_update_config(self, update: dict) -> dict:
        """PUT /api/kyc/config → {"settings": KycSettings}"""
        resp = self._session.put(self._url("/api/kyc/config"), json=update, timeout=5)
        data = self._raise_for(resp)
        return data.get("settings", data)

    def kyc_create_reminder(self, due_at: str | None = None, source: str = "manual", note: str | None = None) -> dict:
        """POST /api/kyc/reminders → {"event": KycEvent}"""
        payload: dict = {"source": source}
        if due_at:
            payload["due_at"] = due_at
        if note:
            payload["note"] = note
        resp = self._session.post(self._url("/api/kyc/reminders"), json=payload, timeout=5)
        data = self._raise_for(resp)
        return data.get("event", data)

    def kyc_get_history(self, limit: int = 50) -> list:
        """GET /api/kyc/history → {"events": [KycEvent]}"""
        resp = self._session.get(self._url("/api/kyc/history"), params={"limit": limit}, timeout=5)
        data = self._raise_for(resp)
        if isinstance(data, list):
            return data
        return data.get("events", [])

    def kyc_acknowledge(self, event_id: int, reason: str | None = None) -> dict:
        resp = self._session.post(
            self._url(f"/api/kyc/events/{event_id}/acknowledge"),
            json={"reason": reason},
            timeout=5,
        )
        data = self._raise_for(resp)
        return data.get("event", data)

    def kyc_snooze(self, event_id: int, snooze_minutes: int | None = None, reason: str | None = None) -> dict:
        payload: dict = {}
        if snooze_minutes:
            payload["snooze_minutes"] = snooze_minutes
        if reason:
            payload["reason"] = reason
        resp = self._session.post(
            self._url(f"/api/kyc/events/{event_id}/snooze"),
            json=payload,
            timeout=5,
        )
        data = self._raise_for(resp)
        return data.get("event", data)

    def kyc_complete(self, event_id: int, team_member: str | None = None) -> dict:
        resp = self._session.post(
            self._url(f"/api/kyc/events/{event_id}/complete"),
            json={"team_member": team_member},
            timeout=5,
        )
        data = self._raise_for(resp)
        return data.get("event", data)

    def kyc_skip(self, event_id: int, reason: str | None = None) -> dict:
        resp = self._session.post(
            self._url(f"/api/kyc/events/{event_id}/skip"),
            json={"reason": reason},
            timeout=5,
        )
        data = self._raise_for(resp)
        return data.get("event", data)

    # ── Training ───────────────────────────────────────────────────────────────

    def get_training_status(self) -> dict:
        resp = self._session.get(self._url("/api/admin/training/status"), timeout=10)
        return self._raise_for(resp)

    def run_training_pipeline(self, batch_size: int = 10, refine: bool = False) -> dict:
        resp = self._session.post(
            self._url("/api/admin/training/run"),
            params={"batch_size": batch_size, "refine": str(refine).lower()},
            timeout=120,
        )
        return self._raise_for(resp)

    def run_classifier_train(self) -> dict:
        resp = self._session.post(self._url("/api/admin/classifier/train"), timeout=120)
        return self._raise_for(resp)


class ApiWorker(QThread):
    """Generic QThread that runs a single ApiClient call and emits the result."""

    success = Signal(object)
    failure = Signal(str)

    def __init__(self, fn, *args, **kwargs) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.success.emit(result)
        except ApiError as exc:
            self.failure.emit(str(exc))
        except Exception as exc:
            self.failure.emit(f"Unexpected error: {exc}")
