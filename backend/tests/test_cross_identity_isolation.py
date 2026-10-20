"""End-to-end isolation tests between Web and external (Platform/MCP) identities.

These tests prove the M2B trust boundary:
- A Web session owned by ``web:<user_id>`` cannot be read or mutated through the
  Platform Tool bearer channel or the MCP external channel.
- An ``external:<sha256>`` session created by Platform/MCP cannot be read through
  the Web session-cookie channel.
- Two different external logical subjects cannot share one MCP session.
"""

from __future__ import annotations

import unittest
import uuid
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from mcp import Client

from app.auth.config import AuthSettings
from app.auth.identity import external_owner_id, web_owner_id
from app.auth.security import AuthSecurity
from app.auth.service import AuthService
from app.db_state import StateRepository
from app.main import create_app
from app.mcp.server import create_career_mcp_server
from app.orchestrator import CareerOrchestrator
from app.services.career_graph_repository import CareerGraphProviderSelector
from app.services.student_profile_persistence_service import (
    StudentProfilePersistenceService,
)
from app.tools.database_tools import DatabaseTools
from tests.stage3_fixtures import job_profile, student_profile
from tests.test_auth_api import MemoryAuthRepository
from tests.test_mcp_server import (
    MemoryStudentProfileRepository,
    OfflineCareerGraphProvider,
    OfflineJobContextService,
    real_orchestrator,
    student_tool_arguments,
    target_job_tool_arguments,
)

PLATFORM_TOKEN = "test-only-cross-identity-token"
PLATFORM_AUTH = {"Authorization": f"Bearer {PLATFORM_TOKEN}"}


def build_auth_service() -> AuthService:
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


def register_and_login(client: TestClient, *, username: str, email: str) -> str:
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
        "user_id": "client-controlled-value",
        "student_profile": student_profile(),
        "job_profile": job_profile(),
    }


def platform_match_payload(session_id: str) -> dict[str, Any]:
    return {
        "schema_version": "stage3-tool-v1",
        "idempotency_key": f"cross-{session_id}",
        "session_id": session_id,
        "platform_session_id": f"tbox-{session_id}",
        "user_id": "platform-logical-user",
        "student_profile": student_profile(),
        "job_profile": job_profile(),
    }


def platform_path_payload(session_id: str) -> dict[str, Any]:
    return {
        "schema_version": "stage3-tool-v1",
        "idempotency_key": f"cross-path-{session_id}",
        "session_id": session_id,
        "platform_session_id": f"tbox-{session_id}",
        "user_id": "platform-logical-user",
    }


class WebVsPlatformIsolationTests(unittest.TestCase):
    """Web cookie sessions and Platform bearer sessions cannot cross."""

    def setUp(self) -> None:
        runtime_dir = Path(__file__).resolve().parents[1] / ".runtime" / "tests"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = runtime_dir / f"cross-platform-{uuid.uuid4().hex}.sqlite3"
        self.repository = StateRepository(sqlite_path=self.db_path)
        self.orchestrator = real_orchestrator(self.repository)
        self.client = TestClient(
            create_app(
                self.orchestrator,
                auth_service=build_auth_service(),
                tbox_api_token=PLATFORM_TOKEN,
                mcp_enabled=False,
            ),
            raise_server_exceptions=False,
        )

    def tearDown(self) -> None:
        self.client.close()
        self.db_path.unlink(missing_ok=True)
        Path(f"{self.db_path}-shm").unlink(missing_ok=True)
        Path(f"{self.db_path}-wal").unlink(missing_ok=True)

    def test_platform_tool_cannot_take_over_web_session(self) -> None:
        """A platform bearer call cannot mutate a session owned by a Web user."""

        web_client = TestClient(self.client.app)
        csrf_token = register_and_login(
            web_client,
            username="web_owner_platform",
            email="web-owner-platform@example.com",
        )
        created = web_client.post(
            "/api/career-agent/stage3/prepare",
            json=prepare_payload("cross-web-owned"),
            headers={"X-CSRF-Token": csrf_token},
        )
        assert created.status_code == 200, created.text
        assert created.json()["user_id"] == web_owner_id("user-1")

        response = self.client.post(
            "/api/platform/v1/tools/generate_career_path",
            headers=PLATFORM_AUTH,
            json=platform_path_payload("cross-web-owned"),
        )
        assert response.status_code == 409, response.text
        body = response.json()
        assert body["error"]["type"] == "SESSION_USER_MISMATCH"

        persisted = self.repository.get_state("cross-web-owned")
        assert persisted is not None
        assert persisted["user_id"] == web_owner_id("user-1")

    def test_web_user_cannot_read_platform_session(self) -> None:
        """A Web session-cookie user cannot read a Platform-owned session."""

        created = self.client.post(
            "/api/platform/v1/tools/analyze_job_match",
            headers=PLATFORM_AUTH,
            json=platform_match_payload("cross-platform-owned"),
        )
        assert created.status_code == 200, created.text
        persisted = self.repository.get_state("cross-platform-owned")
        assert persisted is not None
        assert persisted["user_id"] == external_owner_id("platform-logical-user")

        web_client = TestClient(self.client.app)
        register_and_login(
            web_client,
            username="web_reader_platform",
            email="web-reader-platform@example.com",
        )
        response = web_client.get("/api/career-agent/session/cross-platform-owned")
        assert response.status_code == 404, response.text


class WebVsMCPIdentityTests(unittest.IsolatedAsyncioTestCase):
    """Web cookie sessions and MCP external subjects cannot cross."""

    def setUp(self) -> None:
        runtime_dir = Path(__file__).resolve().parents[1] / ".runtime" / "tests"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = runtime_dir / f"cross-mcp-{uuid.uuid4().hex}.sqlite3"
        self.repository = StateRepository(sqlite_path=self.db_path)
        self.orchestrator = real_orchestrator(self.repository)
        self.student_repository = MemoryStudentProfileRepository()
        self.student_service = StudentProfilePersistenceService(
            self.student_repository
        )
        self.server = create_career_mcp_server(
            self.orchestrator,
            timeout_seconds=2,
            expose_database_tools=True,
            database_tools=DatabaseTools(
                student_service=self.student_service,
                job_service=OfflineJobContextService(),
                graph_selector=CareerGraphProviderSelector(
                    OfflineCareerGraphProvider()
                ),
            ),
        )
        self.http_app = create_app(
            self.orchestrator,
            auth_service=build_auth_service(),
            mcp_enabled=False,
        )

    def tearDown(self) -> None:
        self.db_path.unlink(missing_ok=True)
        Path(f"{self.db_path}-shm").unlink(missing_ok=True)
        Path(f"{self.db_path}-wal").unlink(missing_ok=True)

    async def test_mcp_external_user_cannot_access_web_session(self) -> None:
        """An MCP external subject cannot reuse a Web-owned session."""

        web_client = TestClient(self.http_app)
        csrf_token = register_and_login(
            web_client,
            username="web_owner_mcp",
            email="web-owner-mcp@example.com",
        )
        created = web_client.post(
            "/api/career-agent/stage3/prepare",
            json=prepare_payload("cross-mcp-web-owned"),
            headers={"X-CSRF-Token": csrf_token},
        )
        assert created.status_code == 200, created.text
        assert created.json()["user_id"] == web_owner_id("user-1")

        async with Client(self.server, mode="legacy") as mcp_client:
            result = await mcp_client.call_tool(
                "analyze_job_match",
                {
                    "session_id": "cross-mcp-web-owned",
                    "user_id": "mcp-external-attacker",
                },
            )
        self.assertFalse(result.is_error, result)
        body = result.structured_content
        self.assertFalse(body["success"])
        self.assertEqual("SESSION_USER_MISMATCH", body["error_code"])

        persisted = self.repository.get_state("cross-mcp-web-owned")
        self.assertIsNotNone(persisted)
        self.assertEqual(web_owner_id("user-1"), persisted["user_id"])

    async def test_web_user_cannot_read_mcp_session(self) -> None:
        """A Web session-cookie user cannot read an MCP external session."""

        async with Client(self.server, mode="legacy") as mcp_client:
            profile = await mcp_client.call_tool(
                "build_student_profile",
                {
                    "session_id": "cross-mcp-external-owned",
                    "user_id": "mcp-external-owner",
                    **student_tool_arguments(),
                },
            )
            job = await mcp_client.call_tool(
                "analyze_target_job",
                {
                    "session_id": "cross-mcp-external-owned",
                    "user_id": "mcp-external-owner",
                    **target_job_tool_arguments(),
                },
            )
        self.assertFalse(profile.is_error, profile)
        self.assertFalse(job.is_error, job)

        persisted = self.repository.get_state("cross-mcp-external-owned")
        self.assertIsNotNone(persisted)
        self.assertEqual(
            external_owner_id("mcp-external-owner"), persisted["user_id"]
        )

        web_client = TestClient(self.http_app)
        register_and_login(
            web_client,
            username="web_reader_mcp",
            email="web-reader-mcp@example.com",
        )
        response = web_client.get("/api/career-agent/session/cross-mcp-external-owned")
        self.assertEqual(404, response.status_code, response.text)

    async def test_two_external_users_cannot_share_mcp_session(self) -> None:
        """Two different MCP logical subjects cannot share one session."""

        async with Client(self.server, mode="legacy") as mcp_client:
            profile = await mcp_client.call_tool(
                "build_student_profile",
                {
                    "session_id": "cross-mcp-shared",
                    "user_id": "mcp-user-a",
                    **student_tool_arguments(),
                },
            )
            self.assertFalse(profile.is_error, profile)

            takeover = await mcp_client.call_tool(
                "analyze_job_match",
                {
                    "session_id": "cross-mcp-shared",
                    "user_id": "mcp-user-b",
                },
            )
        self.assertFalse(takeover.is_error, takeover)
        self.assertFalse(takeover.structured_content["success"])
        self.assertEqual(
            "SESSION_USER_MISMATCH", takeover.structured_content["error_code"]
        )

        persisted = self.repository.get_state("cross-mcp-shared")
        self.assertIsNotNone(persisted)
        self.assertEqual(external_owner_id("mcp-user-a"), persisted["user_id"])
