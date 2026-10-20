"""M3.1 Web business API tests: auth, CSRF, ownership and the core flow."""

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
from app.agents.job_agent import JobAgent
from app.agents.match_agent import MatchAgent
from app.agents.path_agent import PathAgent
from app.agents.profile_agent import ProfileAgent
from app.db_state import StateRepository
from app.main import create_app
from app.mcp.tool_service import CareerMCPToolService
from app.orchestrator import CareerOrchestrator
from app.tools.database_tools import DatabaseTools
from tests.test_auth_api import MemoryAuthRepository
from tests.test_database_tools import FakeJobService


@pytest.fixture
def state_db_path() -> Path:
    runtime_dir = Path(__file__).resolve().parents[1] / ".runtime" / "tests"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    path = runtime_dir / f"m3-{uuid4().hex}.sqlite3"
    yield path
    path.unlink(missing_ok=True)
    Path(f"{path}-shm").unlink(missing_ok=True)
    Path(f"{path}-wal").unlink(missing_ok=True)


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


def build_app(state_db_path: Path) -> Any:
    repository = StateRepository(sqlite_path=state_db_path)
    orchestrator = CareerOrchestrator(agents=[], repository=repository)
    return create_app(orchestrator, auth_service=auth_service(), mcp_enabled=False)


class OfflineClient:
    """Structured LLM output is unavailable: agents use their offline fallbacks."""

    async def generate_structured(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("offline")


def build_flow_app(state_db_path: Path) -> Any:
    """Full agent chain plus fake business reads (no external database needed)."""

    repository = StateRepository(sqlite_path=state_db_path)
    orchestrator = CareerOrchestrator(
        agents=[
            ProfileAgent(client=OfflineClient()),
            JobAgent(client=OfflineClient()),
            MatchAgent(client=OfflineClient()),
            PathAgent(client=OfflineClient()),
        ],
        repository=repository,
    )
    application = create_app(
        orchestrator, auth_service=auth_service(), mcp_enabled=False
    )
    application.state.career_web_tool_service = CareerMCPToolService(
        orchestrator,
        database_tools=DatabaseTools(job_service=FakeJobService(), demo_mode=True),
        demo_mode=True,
        # Bind the graph source lazily inside the Web path endpoint.
        bind_runtime_graph_provider=False,
    )
    return application


def register_and_login(
    client: TestClient, *, username: str, email: str
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


def create_workflow(client: TestClient, csrf: str, session_id: str) -> Any:
    return client.post(
        "/api/web/v1/workflows",
        json={"session_id": session_id},
        headers={"X-CSRF-Token": csrf},
    )


def test_anonymous_cannot_use_web_business_api(state_db_path: Path) -> None:
    application = build_app(state_db_path)
    anonymous = TestClient(application)
    assert anonymous.get("/api/web/v1/workflows").status_code == 401
    assert (
        anonymous.get("/api/web/v1/jobs", params={"keyword": "AI"}).status_code
        == 401
    )
    assert (
        anonymous.post(
            "/api/web/v1/workflows",
            json={"session_id": "anon"},
        ).status_code
        == 401
    )
    assert (
        anonymous.get("/api/web/v1/workflows/some-session").status_code == 401
    )


def test_writes_require_csrf(state_db_path: Path) -> None:
    application = build_app(state_db_path)
    client = TestClient(application)
    register_and_login(client, username="csrf_user", email="csrf@example.com")

    missing = client.post(
        "/api/web/v1/workflows", json={"session_id": "csrf-missing"}
    )
    assert missing.status_code == 403

    forged = client.post(
        "/api/web/v1/workflows",
        json={"session_id": "csrf-forged"},
        headers={"X-CSRF-Token": "not-the-real-token"},
    )
    assert forged.status_code == 403


def test_two_users_cannot_see_each_others_workflows(state_db_path: Path) -> None:
    application = build_app(state_db_path)
    owner = TestClient(application)
    attacker = TestClient(application)
    owner_csrf = register_and_login(
        owner, username="owner_m3", email="owner-m3@example.com"
    )
    register_and_login(
        attacker, username="attacker_m3", email="attacker-m3@example.com"
    )

    created = create_workflow(owner, owner_csrf, "m3-owned-session")
    assert created.status_code == 201
    assert created.json()["created"] is True

    assert (
        attacker.get("/api/web/v1/workflows/m3-owned-session").status_code == 404
    )
    # CSRF is checked before ownership, so a forged token never reaches the
    # ownership check.
    forged = attacker.put(
        "/api/web/v1/workflows/m3-owned-session/profile",
        json={"resume_text": "attacker takeover"},
        headers={"X-CSRF-Token": "unused"},
    )
    assert forged.status_code == 403
    attacker_list = attacker.get("/api/web/v1/workflows").json()
    assert attacker_list["total"] == 0
    assert attacker_list["items"] == []

    owner_list = owner.get("/api/web/v1/workflows").json()
    assert owner_list["total"] == 1
    assert owner_list["items"][0]["session_id"] == "m3-owned-session"

    visible = owner.get("/api/web/v1/workflows/m3-owned-session")
    assert visible.status_code == 200


def test_forged_user_id_does_not_change_owner(state_db_path: Path) -> None:
    application = build_app(state_db_path)
    client = TestClient(application)
    csrf = register_and_login(
        client, username="forger_m3", email="forger-m3@example.com"
    )

    # The request schema forbids unknown fields, so a client-supplied
    # ``user_id`` is rejected outright and can never influence the owner.
    rejected = client.post(
        "/api/web/v1/workflows",
        json={"session_id": "m3-forged-owner", "user_id": "web:victim"},
        headers={"X-CSRF-Token": csrf},
    )
    assert rejected.status_code == 422

    created = client.post(
        "/api/web/v1/workflows",
        json={"session_id": "m3-forged-owner"},
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 201

    stored = application.state.career_state_repository.get_state(
        "m3-forged-owner"
    )
    assert stored is not None
    assert stored["user_id"] == web_owner_id("user-1")


def test_repository_rejects_cross_owner_concurrent_write(
    state_db_path: Path,
) -> None:
    repository = StateRepository(sqlite_path=state_db_path)
    repository.save_state(
        {
            "session_id": "m3-race",
            "user_id": web_owner_id("user-1"),
            "status": "INITIALIZED",
        }
    )
    with pytest.raises(Exception):
        repository.save_state(
            {
                "session_id": "m3-race",
                "user_id": web_owner_id("user-2"),
                "status": "INITIALIZED",
            }
        )
    stored = repository.get_state("m3-race")
    assert stored is not None
    assert stored["user_id"] == web_owner_id("user-1")


def test_list_pagination_only_returns_own_rows(state_db_path: Path) -> None:
    repository = StateRepository(sqlite_path=state_db_path)
    for index in range(3):
        repository.save_state(
            {
                "session_id": f"m3-page-{index}",
                "user_id": web_owner_id("user-1"),
                "status": "INITIALIZED",
            }
        )
    repository.save_state(
        {
            "session_id": "m3-page-other",
            "user_id": web_owner_id("user-2"),
            "status": "INITIALIZED",
        }
    )

    application = build_app(state_db_path)
    client = TestClient(application)
    register_and_login(client, username="pager_m3", email="pager-m3@example.com")
    page = client.get(
        "/api/web/v1/workflows", params={"page": 1, "page_size": 2}
    ).json()
    assert page["total"] == 3
    assert len(page["items"]) == 2
    assert page["has_more"] is True
    assert all(
        item["session_id"].startswith("m3-page-")
        and item["session_id"] != "m3-page-other"
        for item in page["items"]
    )


def test_full_workflow_happy_path(state_db_path: Path) -> None:
    application = build_flow_app(state_db_path)
    client = TestClient(application)
    csrf = register_and_login(client, username="flow_m3", email="flow-m3@example.com")

    jobs = client.get("/api/web/v1/jobs", params={"keyword": "后端"})
    assert jobs.status_code == 200, jobs.text
    jobs_body = jobs.json()
    assert jobs_body["items"], jobs_body
    job_id = jobs_body["items"][0]["job_id"]

    job_detail = client.get(f"/api/web/v1/jobs/{job_id}")
    assert job_detail.status_code == 200, job_detail.text
    assert job_detail.json()["context"]

    graph = client.get(f"/api/web/v1/jobs/{job_id}/graph")
    assert graph.status_code == 200, graph.text
    assert "edges" in graph.json()

    created = create_workflow(client, csrf, "m3-happy-path")
    assert created.status_code == 201, created.text

    profile = client.put(
        "/api/web/v1/workflows/m3-happy-path/profile",
        json={
            "form_fields": {
                "education_level": "本科",
                "major": "计算机科学",
                "target_job": "后端开发工程师",
            },
            "skills": [
                "Python",
                "后端开发",
                "数据库/SQL",
                "版本控制/Git",
                "API设计",
                "运维/Linux",
                "团队协作",
            ],
            "projects": ["完成匿名后端 API 项目与自动化测试。"],
            "internships": ["参与匿名团队的接口联调工作。"],
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert profile.status_code == 200, profile.text
    assert profile.json()["has_student_profile"] is True

    target = client.put(
        "/api/web/v1/workflows/m3-happy-path/target-job",
        json={"job_id": job_id, "job_title": "后端开发工程师"},
        headers={"X-CSRF-Token": csrf},
    )
    assert target.status_code == 200, target.text
    assert target.json()["has_job_profile"] is True

    match = client.post(
        "/api/web/v1/workflows/m3-happy-path/match",
        headers={"X-CSRF-Token": csrf},
    )
    assert match.status_code == 200, match.text
    match_result = match.json()["match_result"]
    assert 0.0 <= float(match_result["overall_score"]) <= 100.0

    path = client.post(
        "/api/web/v1/workflows/m3-happy-path/path",
        headers={"X-CSRF-Token": csrf},
    )
    assert path.status_code == 200, path.text
    assert path.json()["career_roadmap"]

    listed = client.get("/api/web/v1/workflows").json()
    assert listed["total"] == 1, listed
    assert listed["items"][0]["session_id"] == "m3-happy-path"

    detail = client.get("/api/web/v1/workflows/m3-happy-path")
    assert detail.status_code == 200
    body = detail.json()
    assert body["student_profile"]
    assert body["job_profile"]
    assert body["match_result"]
    assert body["career_roadmap"]
    assert body["agent_logs"]


def test_demo_domain_sessions_never_enter_a_real_users_history(
    state_db_path: Path,
) -> None:
    # Demo/offline rows live in their own owner domain and must never show up
    # in, or be reachable from, a registered user's workflow history.
    StateRepository(sqlite_path=state_db_path).save_state(
        {
            "session_id": "demo-offline-session",
            "user_id": "web:demo-profile",
            "status": "MATCH_COMPLETED",
        }
    )

    application = build_app(state_db_path)
    client = TestClient(application)
    register_and_login(
        client, username="real_demo_m3", email="real-demo-m3@example.com"
    )

    listed = client.get(
        "/api/web/v1/workflows", params={"page": 1, "page_size": 50}
    ).json()
    assert listed["total"] == 0
    assert listed["items"] == []
    assert (
        client.get("/api/web/v1/workflows/demo-offline-session").status_code == 404
    )
