"""Browser authentication API using opaque PostgreSQL-backed sessions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from ..auth.dependencies import (
    AuthenticatedRequest,
    get_auth_service,
    require_authenticated_request,
    require_csrf,
)
from ..auth.repository import AuthIdentityConflict, AuthRepositoryUnavailable, AuthUserRecord
from ..auth.schemas import AuthResponse, AuthUser, LoginRequest, RegisterRequest
from ..auth.service import AuthService, InvalidCredentials, LoginRateLimited


router = APIRouter(prefix="/api/auth", tags=["web-auth"])


def _public_user(user: AuthUserRecord) -> AuthUser:
    return AuthUser(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
    )


def _service_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"code": "AUTH_DATABASE_UNAVAILABLE", "message": "authentication service unavailable"},
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, service: AuthService = Depends(get_auth_service)) -> AuthResponse:
    try:
        user = service.register(
            payload.username,
            payload.email,
            payload.password.get_secret_value(),
        )
    except AuthIdentityConflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "IDENTITY_ALREADY_EXISTS", "message": "username or email already exists"},
        ) from None
    except AuthRepositoryUnavailable:
        raise _service_unavailable() from None
    return AuthResponse(user=_public_user(user))


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    client_host = request.client.host if request.client is not None else "unknown"
    try:
        created = service.login(
            payload.identifier,
            payload.password.get_secret_value(),
            client_host,
        )
    except InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "invalid username/email or password"},
        ) from None
    except LoginRateLimited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "LOGIN_RATE_LIMITED", "message": "too many failed login attempts"},
            headers={"Retry-After": str(service.settings.login_window_seconds)},
        ) from None
    except AuthRepositoryUnavailable:
        raise _service_unavailable() from None

    max_age = service.settings.session_ttl_seconds
    response.set_cookie(
        service.settings.session_cookie_name,
        created.token,
        max_age=max_age,
        expires=created.expires_at,
        path="/",
        secure=service.settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        service.settings.csrf_cookie_name,
        created.csrf_token,
        max_age=max_age,
        expires=created.expires_at,
        path="/",
        secure=service.settings.cookie_secure,
        httponly=False,
        samesite="lax",
    )
    return AuthResponse(user=_public_user(created.user))


@router.get("/me", response_model=AuthResponse)
def me(authenticated: AuthenticatedRequest = Depends(require_authenticated_request)) -> AuthResponse:
    return AuthResponse(user=_public_user(authenticated.user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    request: Request,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    _csrf: None = Depends(require_csrf),
) -> Response:
    service = get_auth_service(request)
    try:
        service.logout(authenticated.session_token)
    except AuthRepositoryUnavailable:
        raise _service_unavailable() from None
    response.delete_cookie(service.settings.session_cookie_name, path="/")
    response.delete_cookie(service.settings.csrf_cookie_name, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


__all__ = ["router"]

