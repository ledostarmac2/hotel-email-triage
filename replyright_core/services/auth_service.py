from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models.user_models import Session, User


@runtime_checkable
class AuthServiceProtocol(Protocol):
    def authenticate(self, email: str, password: str) -> Session | None:
        """Sign in with email and password. Returns Session or None on failure."""
        ...

    def refresh_session(self, refresh_token: str) -> Session | None:
        """Refresh an expired access token. Returns updated Session or None."""
        ...

    def get_current_user(self, access_token: str) -> User | None:
        """Validate access token and return the associated User, or None."""
        ...

    def logout(self, access_token: str) -> None:
        """Invalidate the session on the auth backend."""
        ...

    def needs_first_admin(self) -> bool:
        """Return True when no admin user exists yet (first-run state)."""
        ...

    def create_first_admin(self, email: str, password: str) -> str:
        """Create the first admin user. Raises if one already exists."""
        ...
