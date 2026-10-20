from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth.config import AuthSettings
from app.auth.identity import web_owner_id
from app.auth.security import AuthSecurity
from app.auth.service import AuthService
from app.db_state import SessionOwnershipConflict, StateRepository
from app.main import create_app
from app.orchestrator import CareerOrchestrator, CareerState
from app.platform.tbox.schemas import (
    TBoxChatData,
    TBoxChatRequest,
    TBoxChatResponse,
)
from tests.stage3_fixtures import job_profile, student_profile
from tests.test_auth_api import MemoryAuthRepository


@pytest.fixture
def state_db_path() -> Path:
    runtime_dir = Path(__file__).resolve().parents[1] / ".runtime" / "tests"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    path = runtime_dir / f"m2-{uuid4().hex}.sqlite3"
    yield path
    path.unlink(missing_ok=True)
    Path(f"{path}-shm").unlink(missing_ok=True)
    Path(f"{path}-wal").unlink(missing_ok=True)


class CapturingTBoxService:
    def __init__(self) -> None:
        self.payload: TBoxChatRequest | None = None

    async def chat(self, payload: TBoxChatRequest) -> TBoxChatResponse:
        self.payload = payload
        return TBoxChatResponse(
            request_id="chat-test-request",
            data=TBoxChatData(
                session_id=payload.session_id,
                conversation_id="conversation-test",
                content="ok",
            ),
        )

    def ensure_configured(self) -> None:
        return None


def auth_service() -> AuthService:
    settings = AuthSettings(
        session_cookie_name="careerpulse_session",
        csrf_cookie_name="careerpulse_csrf",
        session_ttl_seconds=3600,
        cookie_secure=False,
        login_window_seconds=900,
        login_max_failures=5,
    )
    return AuthService(
        MemoryAuthRepository(),
        security=AuthSecurity(),
        settings=settings,
    )


def register_and_login(
    client: TestClient,
    *,
    username: str,
    email: str,
) -> str:
    password = "StrongPass123!"
    registered = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert registered.status_code == 201
    logged_in = client.post(
        "/api/auth/login",
        json={"identifier": username, "password": password},
    )
    assert logged_in.status_code == 200
    csrf_token = client.cookies.get("careerpulse_csrf")
    assert csrf_token
    return csrf_token


def prepare_payload(session_id: str) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "user_id": "web:user-controlled-value",
        "student_profile": student_profile(),
        "job_profile": job_profile(),
    }


def test_two_web_users_cannot_read_or_mutate_each_others_session(
    state_db_path: Path,
) -> None:
    state_repository = StateRepository(sqlite_path=state_db_path)
    orchestrator = CareerOrchestrator(agents=[], repository=state_repository)
    application = create_app(
        orchestrator,
        auth_service=auth_service(),
        mcp_enabled=False,
    )
    owner_client = TestClient(application)
    attacker_client = TestClient(application)
    owner_csrf = register_and_login(
        owner_client,
        username="owner_user",
        email="owner@example.com",
    )
    attacker_csrf = register_and_login(
        attacker_client,
        username="attacker_user",
        email="attacker@example.com",
    )

    created = owner_client.post(
        "/api/career-agent/stage3/prepare",
        json=prepare_payload("owned-session"),
        headers={"X-CSRF-Token": owner_csrf},
    )
    assert created.status_code == 200
    assert created.json()["user_id"] == web_owner_id("user-1")

    assert attacker_client.get(
        "/api/career-agent/session/owned-session"
    ).status_code == 404
    assert attacker_client.get(
        "/api/agent/logs/owned-session"
    ).status_code == 404
    denied = attacker_client.post(
        "/api/career-agent/stage3/prepare",
        json=prepare_payload("owned-session"),
        headers={"X-CSRF-Token": attacker_csrf},
    )
    assert denied.status_code == 404

    visible = owner_client.get("/api/career-agent/session/owned-session")
    assert visible.status_code == 200
    assert visible.json()["user_id"] == web_owner_id("user-1")


def test_web_writes_require_session_and_csrf(state_db_path: Path) -> None:
    repository = StateRepository(sqlite_path=state_db_path)
    application = create_app(
        CareerOrchestrator(agents=[], repository=repository),
        auth_service=auth_service(),
        mcp_enabled=False,
    )
    anonymous = TestClient(application)
    assert anonymous.post(
        "/api/career-agent/stage3/prepare",
        json=prepare_payload("anonymous-session"),
    ).status_code == 401

    authenticated = TestClient(application)
    register_and_login(
        authenticated,
        username="csrf_user",
        email="csrf@example.com",
    )
    assert authenticated.post(
        "/api/career-agent/stage3/prepare",
        json=prepare_payload("csrf-session"),
    ).status_code == 403


def test_tbox_uses_authenticated_owner_instead_of_payload(
    state_db_path: Path,
) -> None:
    repository = StateRepository(sqlite_path=state_db_path)
    capture = CapturingTBoxService()
    application = create_app(
        CareerOrchestrator(agents=[], repository=repository),
        auth_service=auth_service(),
        tbox_chat_service=capture,  # type: ignore[arg-type]
        mcp_enabled=False,
    )
    client = TestClient(application)
    csrf_token = register_and_login(
        client,
        username="chat_user",
        email="chat@example.com",
    )
    response = client.post(
        "/api/tbox/chat",
        json={
            "session_id": "chat-owned-session",
            "user_id": "web:attacker-controlled",
            "message": "hello",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200
    assert capture.payload is not None
    assert capture.payload.user_id == web_owner_id("user-1")


def test_repository_rejects_cross_owner_overwrite(state_db_path: Path) -> None:
    repository = StateRepository(sqlite_path=state_db_path)
    repository.save_state(
        CareerState(
            session_id="race-session",
            user_id=web_owner_id("owner-a"),
        ).model_dump(mode="json")
    )

    with pytest.raises(SessionOwnershipConflict):
        repository.save_state(
            CareerState(
                session_id="race-session",
                user_id=web_owner_id("owner-b"),
            ).model_dump(mode="json")
        )

    persisted = repository.get_state("race-session")
    assert persisted is not None
    assert persisted["user_id"] == web_owner_id("owner-a")
