from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.auth.config import AuthSettings
from app.auth.repository import AuthIdentityConflict, AuthUserRecord
from app.auth.security import AuthSecurity
from app.auth.service import AuthService
from app.main import create_app


class MemoryAuthRepository:
    def __init__(self) -> None:
        self.users: dict[str, AuthUserRecord] = {}
        self.sessions: dict[str, tuple[str, datetime, bool]] = {}
        self.failures: dict[str, list[datetime]] = {}

    def create_user(
        self, username: str, email: str, password_hash: str
    ) -> AuthUserRecord:
        normalized_username = username.lower()
        normalized_email = email.lower()
        if any(
            user.username.lower() == normalized_username
            or user.email.lower() == normalized_email
            for user in self.users.values()
        ):
            raise AuthIdentityConflict("username or email already exists")
        user = AuthUserRecord(
            id=f"user-{len(self.users) + 1}",
            username=username,
            email=email,
            password_hash=password_hash,
            role="user",
            status="active",
            created_at=datetime.now(timezone.utc),
        )
        self.users[user.id] = user
        return user

    def find_user_by_identifier(self, identifier: str) -> AuthUserRecord | None:
        normalized = identifier.strip().lower()
        return next(
            (
                user
                for user in self.users.values()
                if user.username.lower() == normalized or user.email.lower() == normalized
            ),
            None,
        )

    def create_session(
        self, token_hash: str, user_id: str, expires_at: datetime
    ) -> None:
        self.sessions[token_hash] = (user_id, expires_at, False)

    def find_user_by_session(
        self, token_hash: str, now: datetime
    ) -> AuthUserRecord | None:
        session = self.sessions.get(token_hash)
        if session is None:
            return None
        user_id, expires_at, revoked = session
        if revoked or expires_at <= now:
            return None
        return self.users.get(user_id)

    def revoke_session(self, token_hash: str, revoked_at: datetime) -> None:
        del revoked_at
        session = self.sessions.get(token_hash)
        if session is not None:
            self.sessions[token_hash] = (session[0], session[1], True)

    def is_login_limited(
        self, rate_key: str, since: datetime, maximum: int
    ) -> bool:
        return sum(moment >= since for moment in self.failures.get(rate_key, [])) >= maximum

    def record_login_failure(self, rate_key: str, attempted_at: datetime) -> None:
        self.failures.setdefault(rate_key, []).append(attempted_at)

    def clear_login_failures(self, rate_key: str) -> None:
        self.failures.pop(rate_key, None)


def build_client(*, max_failures: int = 2) -> tuple[TestClient, MemoryAuthRepository]:
    repository = MemoryAuthRepository()
    settings = AuthSettings(
        session_cookie_name="careerpulse_session",
        csrf_cookie_name="careerpulse_csrf",
        session_ttl_seconds=3600,
        cookie_secure=False,
        login_window_seconds=900,
        login_max_failures=max_failures,
    )
    service = AuthService(repository, security=AuthSecurity(), settings=settings)
    app = create_app(mcp_enabled=False, auth_service=service)
    return TestClient(app), repository


def register(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={
            "username": "career_user",
            "email": "user@example.com",
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 201


def test_register_hashes_password_and_rejects_duplicate() -> None:
    client, repository = build_client()
    register(client)

    user = next(iter(repository.users.values()))
    assert user.password_hash != "StrongPass123!"
    assert user.password_hash.startswith("$argon2id$")

    duplicate = client.post(
        "/api/auth/register",
        json={
            "username": "another_user",
            "email": "user@example.com",
            "password": "AnotherPass123!",
        },
    )
    assert duplicate.status_code == 409


def test_login_me_and_csrf_protected_logout() -> None:
    client, _ = build_client()
    register(client)

    login = client.post(
        "/api/auth/login",
        json={"identifier": "user@example.com", "password": "StrongPass123!"},
    )
    assert login.status_code == 200
    assert "token" not in login.json()
    assert "HttpOnly" in login.headers["set-cookie"]

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "career_user"

    missing_csrf = client.post("/api/auth/logout")
    assert missing_csrf.status_code == 403

    csrf_token = client.cookies.get("careerpulse_csrf")
    assert csrf_token
    logout = client.post(
        "/api/auth/logout", headers={"X-CSRF-Token": csrf_token}
    )
    assert logout.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_invalid_credentials_are_generic_and_rate_limited() -> None:
    client, _ = build_client(max_failures=2)
    register(client)

    for _ in range(2):
        response = client.post(
            "/api/auth/login",
            json={"identifier": "career_user", "password": "WrongPass123!"},
        )
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "INVALID_CREDENTIALS"

    limited = client.post(
        "/api/auth/login",
        json={"identifier": "career_user", "password": "WrongPass123!"},
    )
    assert limited.status_code == 429


def test_me_requires_session() -> None:
    client, _ = build_client()
    assert client.get("/api/auth/me").status_code == 401


def test_cors_does_not_reflect_untrusted_origins() -> None:
    client, _ = build_client()
    response = client.options(
        "/api/auth/login",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
