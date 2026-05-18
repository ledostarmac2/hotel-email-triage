from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppState:
    """Minimal native-shell state container for future service extraction."""

    current_user_email: str = ""
    current_user_role: str = ""
    selected_conversation_id: str = ""
    active_queue: str = "inbox"
    offline_mode: bool = False

