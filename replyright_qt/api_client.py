from __future__ import annotations

import json

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
        # Map sidebar queues to server-side filter params
        if queue == "urgent":
            params["priority"] = "Immediate"
        elif queue == "vip":
            params["risk"] = "VIP"
        elif queue == "missing":
            params["risk"] = "Missing information"
        elif queue == "review":
            params["needs_review"] = "true"
        # Operational queues — passed directly to server-side queue filter
        elif queue == "immediate":
            params["queue"] = "Immediate"
        elif queue == "today":
            params["queue"] = "Today"
        elif queue == "waiting_guest":
            params["queue"] = "waiting on guest"
        elif queue == "waiting_internal":
            params["queue"] = "waiting on internal team"
        elif queue == "billing_risk":
            params["queue"] = "billing risk"
        elif queue == "vip_travel":
            params["queue"] = "vip / travel advisor"
        elif queue == "complaints":
            params["queue"] = "complaints"
        elif queue == "low_confidence":
            params["queue"] = "low confidence"
        elif queue == "no_action":
            params["queue"] = "no action likely"
        # Explicit filter overrides queue defaults
        if category:
            params["category"] = category
        if status:
            params["status"] = status
        if risk:
            params["risk"] = risk
        if q:
            params["q"] = q
        params["limit"] = "500"
        resp = self._session.get(self._url("/api/emails"), params=params, timeout=15)
        data = self._raise_for(resp)
        if isinstance(data, list):
            emails = data
        else:
            emails = data.get("emails", [])
        return self._filter_queue(emails, queue)

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
            self._url(f"/api/emails/{email_id}/analyze"), timeout=120
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
        resp = self._session.post(self._url("/api/outlook-desktop/export-inbox"), timeout=180)
        return self._raise_for(resp)

    def _filter_queue(self, emails: list[dict], queue: str) -> list[dict]:
        if queue == "urgent":
            return [email for email in emails if self._urgency(email) >= 4]
        if queue == "vip":
            return [
                email
                for email in emails
                if str(email.get("importance", "")).lower() == "high"
                or "VIP" in self._as_list(email.get("risk_flags"))
            ]
        if queue == "missing":
            return [email for email in emails if self._as_list(email.get("missing_information"))]
        # Operational queues — server already filtered; client-side is a safety fallback
        if queue == "immediate":
            return [e for e in emails if self._urgency(e) >= 5]
        if queue == "today":
            return [e for e in emails if self._urgency(e) >= 4]
        if queue == "waiting_guest":
            return [e for e in emails if e.get("recommended_action") == "wait_for_guest"]
        if queue == "waiting_internal":
            return [e for e in emails if e.get("recommended_action") == "wait_for_internal_team"]
        if queue == "billing_risk":
            return [
                e for e in emails
                if str(e.get("category") or "").startswith("Billing")
                or any(f in self._as_list(e.get("risk_flags")) for f in ("Billing", "Chargeback"))
            ]
        if queue == "vip_travel":
            return [
                e for e in emails
                if e.get("contact_type") in ("Travel agent", "Travel agency")
                or "VIP" in self._as_list(e.get("risk_flags"))
            ]
        if queue == "complaints":
            return [e for e in emails if e.get("category") == "Complaint"]
        if queue == "low_confidence":
            return [e for e in emails if (e.get("confidence_score") or 100) <= 50]
        if queue == "no_action":
            return [e for e in emails if e.get("recommended_action") == "no_action_likely"]
        return emails

    @staticmethod
    def _urgency(email: dict) -> int:
        value = (
            email.get("urgency_score")
            or email.get("priority_level")
            or (email.get("analysis") or {}).get("priority_level")
            or 0
        )
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _as_list(value: object) -> list:
        if isinstance(value, list):
            return value
        if not value:
            return []
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
            return [part.strip() for part in value.split(",") if part.strip()]
        return [value]

    # ── Taxonomy & config ──────────────────────────────────────────────────────

    def get_queues(self) -> dict:
        resp = self._session.get(self._url("/api/queues"), timeout=5)
        return self._raise_for(resp)

    def get_taxonomy(self) -> dict:
        resp = self._session.get(self._url("/api/taxonomy"), timeout=5)
        return self._raise_for(resp)

    def get_admin_stats(self) -> dict:
        resp = self._session.get(self._url("/api/admin/stats"), timeout=15)
        return self._raise_for(resp)

    def get_email_signals(self, email_id: str) -> dict:
        resp = self._session.get(
            self._url("/api/admin/intelligence/signals"),
            params={"email_id": email_id},
            timeout=10,
        )
        return self._raise_for(resp)

    def get_deployment_diagnostics(self) -> dict:
        resp = self._session.get(self._url("/api/admin/deployment/diagnostics"), timeout=10)
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

    def purge_email_bodies(
        self,
        min_age_days: int = 0,
        require_analyzed: bool = True,
        dry_run: bool = False,
    ) -> dict:
        """POST /api/admin/training/purge-bodies — free storage after import+train."""
        resp = self._session.post(
            self._url("/api/admin/training/purge-bodies"),
            params={
                "min_age_days": min_age_days,
                "require_analyzed": str(require_analyzed).lower(),
                "dry_run": str(dry_run).lower(),
            },
            timeout=30,
        )
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
        except requests.ConnectionError:
            self.failure.emit(
                "Cannot connect to the ReplyRight server. "
                "Make sure the app backend is running."
            )
        except requests.Timeout:
            self.failure.emit(
                "The server took too long to respond. "
                "It may be busy. Please try again in a moment."
            )
        except Exception as exc:
            self.failure.emit(f"Something went wrong. {exc}")
