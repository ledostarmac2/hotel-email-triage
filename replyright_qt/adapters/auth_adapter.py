from __future__ import annotations

from replyright_core.models.user_models import Session, User


class SupabaseAuthAdapter:
    """AuthServiceProtocol backed by outlook_dashboard.auth (Supabase)."""

    def authenticate(self, email: str, password: str) -> Session | None:
        from outlook_dashboard import auth as _auth

        result = _auth.authenticate_user(email.lower().strip(), password)
        if not result:
            return None
        user = User(
            id=result["id"],
            email=result["email"],
            role=result.get("role", "user"),
        )
        return Session(
            user=user,
            access_token=result["_access_token"],
            refresh_token=result["_refresh_token"],
        )

    def refresh_session(self, refresh_token: str) -> Session | None:
        from outlook_dashboard import auth as _auth

        # encode_session requires both tokens non-empty; use a placeholder for access
        cookie = _auth.encode_session("placeholder", refresh_token)
        result = _auth.get_session_user(cookie)
        if not result:
            return None
        new_access = result.get("_new_access_token", "")
        new_refresh = result.get("_new_refresh_token", refresh_token)
        if not new_access:
            return None
        user = User(
            id=result["id"],
            email=result["email"],
            role=result.get("role", "user"),
        )
        return Session(user=user, access_token=new_access, refresh_token=new_refresh)

    def get_current_user(self, access_token: str) -> User | None:
        from outlook_dashboard import auth as _auth

        # Use a non-empty placeholder refresh so _decode_session passes;
        # get_session_user tries the access token first and returns on success.
        cookie = _auth.encode_session(access_token, "placeholder_refresh")
        result = _auth.get_session_user(cookie)
        if not result:
            return None
        return User(
            id=result["id"],
            email=result["email"],
            role=result.get("role", "user"),
        )

    def logout(self, access_token: str) -> None:
        from outlook_dashboard import auth as _auth

        cookie = _auth.encode_session(access_token, "placeholder_refresh")
        _auth.delete_session(cookie)

    def needs_first_admin(self) -> bool:
        from outlook_dashboard import auth as _auth

        return not _auth.admin_user_exists()

    def create_first_admin(self, email: str, password: str) -> str:
        from outlook_dashboard import auth as _auth

        return _auth.create_first_admin(email, password)
