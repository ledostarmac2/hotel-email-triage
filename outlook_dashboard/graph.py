from __future__ import annotations

import secrets
import time
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from .config import Settings
from .database import (
    consume_oauth_state,
    get_oauth_token,
    save_oauth_state,
    save_oauth_token,
)
from .text_utils import graph_email_address, html_to_text


GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_FIELDS = [
    "id",
    "subject",
    "sender",
    "from",
    "receivedDateTime",
    "bodyPreview",
    "body",
    "conversationId",
    "importance",
    "hasAttachments",
]


class GraphConfigurationError(RuntimeError):
    pass


class GraphAuthenticationError(RuntimeError):
    pass


def authorization_url(settings: Settings, mailbox_mode: str) -> str:
    if not settings.graph_configured:
        raise GraphConfigurationError("Microsoft Graph environment variables are not configured.")
    state = secrets.token_urlsafe(32)
    save_oauth_state(state, mailbox_mode)
    params = {
        "client_id": settings.microsoft_client_id,
        "response_type": "code",
        "redirect_uri": settings.microsoft_redirect_uri,
        "response_mode": "query",
        "scope": settings.graph_scope_string,
        "state": state,
        "prompt": "select_account",
    }
    return f"{_login_base(settings)}/oauth2/v2.0/authorize?{urlencode(params)}"


def exchange_callback_code(settings: Settings, code: str, state: str) -> str:
    mailbox_mode = consume_oauth_state(state)
    if not mailbox_mode:
        raise GraphAuthenticationError("OAuth state was not recognized or has expired.")
    token = _token_request(
        settings,
        {
            "client_id": settings.microsoft_client_id,
            "client_secret": settings.microsoft_client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.microsoft_redirect_uri,
            "scope": settings.graph_scope_string,
        },
    )
    _store_token(settings, mailbox_mode, token)
    return mailbox_mode


def fetch_recent_messages(settings: Settings, mailbox_mode: str, top: int = 25) -> list[dict[str, Any]]:
    token = _valid_access_token(settings, mailbox_mode)
    if mailbox_mode == "personal":
        url = f"{GRAPH_BASE}/me/messages"
    else:
        if not settings.shared_mailbox_email:
            raise GraphConfigurationError("SHARED_MAILBOX_EMAIL is required for shared mailbox sync.")
        mailbox = quote(settings.shared_mailbox_email)
        url = f"{GRAPH_BASE}/users/{mailbox}/mailFolders/Inbox/messages"

    response = httpx.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Prefer": 'outlook.body-content-type="text"',
        },
        params={
            "$select": ",".join(GRAPH_FIELDS),
            "$top": max(1, min(top, 50)),
            "$orderby": "receivedDateTime desc",
        },
        timeout=30,
    )
    if response.status_code >= 400:
        raise GraphAuthenticationError(f"Graph request failed {response.status_code}: {response.text[:500]}")
    return [normalize_graph_message(item, mailbox_mode) for item in response.json().get("value", [])]


def normalize_graph_message(message: dict[str, Any], mailbox_mode: str) -> dict[str, Any]:
    sender_name, sender_email = graph_email_address(message.get("sender"))
    from_name, from_email = graph_email_address(message.get("from"))
    body = message.get("body") or {}
    body_content = body.get("content") or ""
    body_content_type = body.get("contentType") or "text"
    body_text = body_content if body_content_type.lower() == "text" else html_to_text(body_content)
    return {
        "graph_message_id": message.get("id"),
        "subject": message.get("subject") or "",
        "sender_name": sender_name,
        "sender_email": sender_email,
        "from_name": from_name,
        "from_email": from_email,
        "received_datetime": message.get("receivedDateTime"),
        "body_preview": message.get("bodyPreview") or "",
        "body_content_type": body_content_type,
        "body_content": body_content,
        "body_text": body_text,
        "conversation_id": message.get("conversationId") or "",
        "importance": message.get("importance") or "normal",
        "has_attachments": bool(message.get("hasAttachments")),
        "source": "outlook",
        "mailbox_mode": mailbox_mode,
    }


def _valid_access_token(settings: Settings, mailbox_mode: str) -> str:
    token = get_oauth_token(mailbox_mode, settings.microsoft_tenant_id)
    if not token:
        raise GraphAuthenticationError("Microsoft account is not connected. Use Connect Microsoft first.")
    if int(token["expires_at"]) > int(time.time()) + 60:
        return token["access_token"]
    if not token.get("refresh_token"):
        raise GraphAuthenticationError("Microsoft token expired and no refresh token is available.")
    refreshed = _token_request(
        settings,
        {
            "client_id": settings.microsoft_client_id,
            "client_secret": settings.microsoft_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
            "redirect_uri": settings.microsoft_redirect_uri,
            "scope": settings.graph_scope_string,
        },
    )
    _store_token(settings, mailbox_mode, refreshed)
    return refreshed["access_token"]


def _token_request(settings: Settings, data: dict[str, str]) -> dict[str, Any]:
    response = httpx.post(f"{_login_base(settings)}/oauth2/v2.0/token", data=data, timeout=30)
    if response.status_code >= 400:
        raise GraphAuthenticationError(f"Token request failed {response.status_code}: {response.text[:500]}")
    return response.json()


def _store_token(settings: Settings, mailbox_mode: str, token: dict[str, Any]) -> None:
    expires_at = int(time.time()) + int(token.get("expires_in", 3600))
    save_oauth_token(
        mailbox_mode=mailbox_mode,
        tenant_id=settings.microsoft_tenant_id,
        access_token=token["access_token"],
        refresh_token=token.get("refresh_token"),
        expires_at=expires_at,
        scopes=token.get("scope", settings.graph_scope_string),
    )


def _login_base(settings: Settings) -> str:
    tenant = quote(settings.microsoft_tenant_id or "common")
    return f"https://login.microsoftonline.com/{tenant}"
