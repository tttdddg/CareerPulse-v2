"""Deterministic user registration and browser-session lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .config import AuthSettings
from .repository import AuthRepository, AuthRepositoryProtocol, AuthUserRecord
from .security import AuthSecurity


class AuthError(RuntimeError):
    pass


class InvalidCredentials(AuthError):
    pass


class InvalidSession(AuthError):
    pass


class LoginRateLimited(AuthError):
    pass


@dataclass(frozen=True, slots=True)
class CreatedSession:
    user: AuthUserRecord
    token: str
    csrf_token: str
    expires_at: datetime


class AuthService:
    def __init__(
        self,
        repository: AuthRepositoryProtocol | None = None,
        *,
        security: AuthSecurity | None = None,
        settings: AuthSettings | None = None,
    ) -> None:
        self.repository = repository or AuthRepository()
        self.security = security or AuthSecurity()
        self.settings = settings or AuthSettings.from_env()

    def register(self, username: str, email: str, password: str) -> AuthUserRecord:
        return self.repository.create_user(
            username.strip(),
            email.strip().lower(),
            self.security.hash_password(password),
        )

    def login(self, identifier: str, password: str, client_host: str) -> CreatedSession:
        now = datetime.now(timezone.utc)
        key = self.security.rate_limit_key(identifier, client_host)
        since = now - timedelta(seconds=self.settings.login_window_seconds)
        if self.repository.is_login_limited(
            key, since, self.settings.login_max_failures
        ):
            raise LoginRateLimited("too many failed login attempts")

        user = self.repository.find_user_by_identifier(identifier)
        if user is None:
            self.security.consume_dummy_verification(password)
            self.repository.record_login_failure(key, now)
            raise InvalidCredentials("invalid username/email or password")
        if user.status != "active" or not self.security.verify_password(
            user.password_hash, password
        ):
            self.repository.record_login_failure(key, now)
            raise InvalidCredentials("invalid username/email or password")

        self.repository.clear_login_failures(key)
        token = self.security.new_session_token()
        expires_at = now + timedelta(seconds=self.settings.session_ttl_seconds)
        self.repository.create_session(
            self.security.hash_token(token), user.id, expires_at
        )
        return CreatedSession(
            user=user,
            token=token,
            csrf_token=self.security.new_csrf_token(),
            expires_at=expires_at,
        )

    def authenticate(self, token: str | None) -> AuthUserRecord:
        if not token:
            raise InvalidSession("authentication required")
        user = self.repository.find_user_by_session(
            self.security.hash_token(token), datetime.now(timezone.utc)
        )
        if user is None:
            raise InvalidSession("authentication required")
        return user

    def logout(self, token: str) -> None:
        self.repository.revoke_session(
            self.security.hash_token(token), datetime.now(timezone.utc)
        )


__all__ = [
    "AuthError",
    "AuthService",
    "CreatedSession",
    "InvalidCredentials",
    "InvalidSession",
    "LoginRateLimited",
]

