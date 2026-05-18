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
