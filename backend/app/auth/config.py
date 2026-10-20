"""Validated environment settings for browser authentication."""

from __future__ import annotations

from dataclasses import dataclass
import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    try:
        value = default if raw in (None, "") else int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class AuthSettings:
    session_cookie_name: str = "careerpulse_session"
    csrf_cookie_name: str = "careerpulse_csrf"
    session_ttl_seconds: int = 604_800
    cookie_secure: bool = True
    login_window_seconds: int = 900
    login_max_failures: int = 5

    @classmethod
    def from_env(cls) -> "AuthSettings":
        session_cookie_name = os.getenv(
            "AUTH_SESSION_COOKIE_NAME", "careerpulse_session"
        ).strip()
        csrf_cookie_name = os.getenv(
            "AUTH_CSRF_COOKIE_NAME", "careerpulse_csrf"
        ).strip()
        if not session_cookie_name or not csrf_cookie_name:
            raise ValueError("authentication cookie names must not be empty")
        if session_cookie_name == csrf_cookie_name:
            raise ValueError("session and CSRF cookie names must differ")
        return cls(
            session_cookie_name=session_cookie_name,
            csrf_cookie_name=csrf_cookie_name,
            session_ttl_seconds=_env_int(
                "AUTH_SESSION_TTL_SECONDS",
                604_800,
                minimum=300,
                maximum=2_592_000,
            ),
            cookie_secure=_env_bool("AUTH_COOKIE_SECURE", True),
            login_window_seconds=_env_int(
                "AUTH_LOGIN_WINDOW_SECONDS", 900, minimum=60, maximum=86_400
            ),
            login_max_failures=_env_int(
                "AUTH_LOGIN_MAX_FAILURES", 5, minimum=2, maximum=100
            ),
        )


__all__ = ["AuthSettings"]

