"""FastAPI dependencies that expose a trusted authenticated user."""

from __future__ import annotations

from dataclasses import dataclass
import secrets

from fastapi import HTTPException, Request, status

from .repository import AuthRepositoryUnavailable, AuthUserRecord
from .service import AuthService, InvalidSession


@dataclass(frozen=True, slots=True)
class AuthenticatedRequest:
    user: AuthUserRecord
    session_token: str


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


def require_authenticated_request(request: Request) -> AuthenticatedRequest:
    service = get_auth_service(request)
    token = request.cookies.get(service.settings.session_cookie_name)
    try:
        user = service.authenticate(token)
    except InvalidSession:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTHENTICATION_REQUIRED", "message": "authentication required"},
        ) from None
    except AuthRepositoryUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AUTH_DATABASE_UNAVAILABLE", "message": "authentication service unavailable"},
        ) from None
    return AuthenticatedRequest(user=user, session_token=token or "")


def require_current_user(request: Request) -> AuthUserRecord:
    return require_authenticated_request(request).user


def require_web_authenticated_request(
    request: Request,
) -> AuthenticatedRequest | None:
    """Require Web auth unless a test/compatibility app disabled it explicitly."""

    if not getattr(request.app.state, "web_auth_enabled", True):
        return None
    return require_authenticated_request(request)


def require_csrf(request: Request) -> None:
    service = get_auth_service(request)
    cookie_token = request.cookies.get(service.settings.csrf_cookie_name, "")
    header_token = request.headers.get("X-CSRF-Token", "")
    if not cookie_token or not header_token or not secrets.compare_digest(
        cookie_token, header_token
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "CSRF_VALIDATION_FAILED", "message": "CSRF validation failed"},
        )


def require_web_csrf(request: Request) -> None:
    """Require CSRF for cookie-authenticated writes in Web-auth mode."""

    if not getattr(request.app.state, "web_auth_enabled", True):
        return
    require_csrf(request)


__all__ = [
    "AuthenticatedRequest",
    "get_auth_service",
    "require_authenticated_request",
    "require_csrf",
    "require_current_user",
    "require_web_authenticated_request",
    "require_web_csrf",
]

