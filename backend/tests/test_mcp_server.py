"""Protocol and business integration tests for the remote MCP server."""

from __future__ import annotations

import json
import unittest
import uuid
from pathlib import Path
from typing import Any

import httpx2
from fastapi.testclient import TestClient
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from app.agents.job_agent import JobAgent
from app.agents.match_agent import MatchAgent
from app.agents.path_agent import PathAgent
from app.agents.profile_agent import ProfileAgent
from app.db_state import StateRepository
from app.main import create_app
from app.mcp.server import create_career_mcp_server
from app.orchestrator import CareerOrchestrator
from app.schemas.career_profile_schema import StudentProfile
from app.schemas.job_schema import JobProfile
from app.schemas.match_schema import MatchResult
from app.schemas.path_schema import PathResult


TOKEN = "test-only-mcp-token"
USER_ID = "anonymous-user-001"


class OfflineLLMClient:
    """Fail every model call so tests prove the Service/fallback path is local."""

    async def generate_structured(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("simulated offline LLM")


def student_input() -> dict[str, Any]:
    return {
        "resume_text": (
            "匿名候选人使用产品规划、需求分析和数据驱动决策完成AI产品项目。"
            "联络信息 candidate@example.com 13800138000 仅用于脱敏日志测试。"
        ),
        "form_fields": {
            "education_level": "硕士",
            "major": "统计学（演示）",
            "graduation_year": 2026,
            "city": "上海",
            "target_job": "AI产品经理",
            "target_industry": "人工智能",
            "years_of_experience": 0.5,
        },
        "parsed_data": {
            "skills": [
                "产品规划",
                "需求分析",
                "数据驱动决策",
                "大模型应用",
                "用户研究",
                "项目管理",
                "沟通表达",
            ],
            "projects": [
                "完成匿名AI产品方案、用户研究、需求拆解和大模型应用原型。"
            ],
            "internships": ["参与匿名项目管理和跨团队沟通表达。"],
        },
    }


def target_job_input() -> dict[str, Any]:
    return {
        "job_id": 91001,
        "job_title": "AI产品经理",
        "industry": "人工智能",
        "city": "上海",
        "job_description": "匿名演示岗位，要求产品规划、需求分析和沟通表达。",
    }


def real_orchestrator(repository: StateRepository) -> CareerOrchestrator:
    offline = OfflineLLMClient()
    return CareerOrchestrator(
        agents=[
            ProfileAgent(client=offline),
            JobAgent(client=offline),
            MatchAgent(client=offline),
            PathAgent(client=offline),
        ],
        repository=repository,
    )


class CareerPulseMCPTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        runtime_dir = Path(__file__).resolve().parents[1] / ".runtime" / "tests"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = runtime_dir / f"mcp-{uuid.uuid4().hex}.sqlite3"
        self.repository = StateRepository(sqlite_path=self.db_path)
        self.orchestrator = real_orchestrator(self.repository)
        self.server = create_career_mcp_server(
            self.orchestrator,
            timeout_seconds=2,
        )

    def tearDown(self) -> None:
        self.db_path.unlink(missing_ok=True)
        Path(f"{self.db_path}-shm").unlink(missing_ok=True)
        Path(f"{self.db_path}-wal").unlink(missing_ok=True)

    def test_mcp_configuration_requires_token_when_auth_is_enabled(self) -> None:
        with self.assertRaisesRegex(ValueError, "MCP_API_TOKEN"):
            create_app(
                self.orchestrator,
                mcp_enabled=True,
                mcp_auth_enabled=True,
                mcp_api_token="",
            )
        disabled = create_app(
            self.orchestrator,
            mcp_enabled=False,
            mcp_auth_enabled=True,
            mcp_api_token="",
        )
        self.assertFalse(disabled.state.mcp_enabled)

    async def _run_chain(
        self, client: Client, session_id: str
    ) -> tuple[dict[str, Any], ...]:
        common = {"session_id": session_id, "user_id": USER_ID}
        profile = await client.call_tool(
            "build_student_profile",
            {
                **common,
                "trace_id": f"tool-{session_id}-profile",
                "student_input": student_input(),
            },
        )
        job = await client.call_tool(
            "analyze_target_job",
            {
                **common,
                "trace_id": f"tool-{session_id}-job",
                "target_job_input": target_job_input(),
            },
        )
        match = await client.call_tool(
            "analyze_job_match",
            {**common, "trace_id": f"tool-{session_id}-match"},
        )
        path = await client.call_tool(
            "generate_career_path",
            {**common, "trace_id": f"tool-{session_id}-path"},
        )
        for result in (profile, job, match, path):
            self.assertFalse(result.is_error, result)
            self.assertIsNotNone(result.structured_content)
        return tuple(
            result.structured_content for result in (profile, job, match, path)
        )

    async def test_initialize_tools_list_and_input_schemas(self) -> None:
        async with Client(self.server, mode="legacy") as client:
            self.assertIsNotNone(client.session.initialize_result)
            self.assertEqual("CareerPulse-A02", client.server_info.name)
            listed = await client.list_tools()

        expected = {
            "build_student_profile",
            "analyze_target_job",
            "analyze_job_match",
            "generate_career_path",
        }
        self.assertEqual(expected, {tool.name for tool in listed.tools})
        schemas = {tool.name: tool.input_schema for tool in listed.tools}
        for name, schema in schemas.items():
            self.assertEqual(False, schema.get("additionalProperties"), name)
            self.assertTrue({"session_id", "user_id"}.issubset(schema["required"]))
            self.assertIn("trace_id", schema["properties"])
        self.assertIn("student_input", schemas["build_student_profile"]["required"])
        self.assertIn("target_job_input", schemas["analyze_target_job"]["required"])
        self.assertNotIn("student_profile", schemas["analyze_job_match"]["properties"])
        self.assertNotIn("match_result", schemas["generate_career_path"]["properties"])

    async def test_four_real_tools_chain_state_fallback_and_private_logs(self) -> None:
        session_id = "mcp-chain-001"
        async with Client(self.server, mode="legacy") as client:
            profile, job, match, path = await self._run_chain(client, session_id)

        self.assertEqual("PROFILE_COMPLETED", profile["status"])
        self.assertTrue(profile["data"]["fallback_used"])
        StudentProfile.model_validate(profile["data"]["student_profile"])
        self.assertEqual("JOB_COMPLETED", job["status"])
        self.assertTrue(job["data"]["fallback_used"])
        JobProfile.model_validate(job["data"]["job_profile"])
        self.assertEqual("MATCH_COMPLETED", match["status"])
        MatchResult.model_validate(match["data"]["match_result"])
        self.assertEqual("PATH_COMPLETED", path["status"])
        PathResult.model_validate(path["data"]["career_roadmap"])

        state = self.orchestrator.get_session(session_id)
        assert state is not None
        self.assertEqual("PATH_COMPLETED", state.status)
        self.assertEqual(
            ["ProfileAgent", "JobAgent", "MatchAgent", "PathAgent"],
            [log.agent_name for log in state.agent_logs],
        )
        for suffix, agent_name in (
            ("profile", "ProfileAgent"),
            ("job", "JobAgent"),
            ("match", "MatchAgent"),
            ("path", "PathAgent"),
        ):
            trace_id = f"tool-{session_id}-{suffix}"
            record = self.repository.get_tool_call(trace_id)
            assert record is not None
            self.assertEqual(trace_id, record["tool_call_id"])
            self.assertEqual(session_id, record["session_id"])
            self.assertEqual("succeeded", record["status"])
            self.assertEqual(f"{session_id}:{agent_name}", record["agent_run_key"])
        serialized_logs = json.dumps(
            self.repository.list_agent_logs(session_id), ensure_ascii=False
        )
        self.assertIn(session_id, serialized_logs)
        self.assertNotIn("candidate@example.com", serialized_logs)
        self.assertNotIn("13800138000", serialized_logs)
        self.assertNotIn(TOKEN, serialized_logs)

    async def test_mcp_match_and_path_equal_existing_http_tools(self) -> None:
        mcp_session = "mcp-consistency-001"
        async with Client(self.server, mode="legacy") as client:
            profile, job, mcp_match, mcp_path = await self._run_chain(
                client, mcp_session
            )

        http_db = self.db_path.with_name(f"http-{uuid.uuid4().hex}.sqlite3")
        http_repository = StateRepository(sqlite_path=http_db)
        http_orchestrator = real_orchestrator(http_repository)
        http_app = create_app(
            http_orchestrator,
            tbox_api_token=TOKEN,
            tbox_tool_timeout_seconds=2,
        )
        http_session = "http-consistency-001"
        headers = {"Authorization": f"Bearer {TOKEN}"}
        with TestClient(http_app) as http_client:
            match_response = http_client.post(
                "/api/platform/v1/tools/analyze_job_match",
                headers=headers,
                json={
                    "schema_version": "stage3-tool-v1",
                    "idempotency_key": "http-match-consistency-001",
                    "session_id": http_session,
                    "user_id": USER_ID,
                    "student_profile": profile["data"]["student_profile"],
                    "job_profile": job["data"]["job_profile"],
                },
            )
            self.assertEqual(200, match_response.status_code, match_response.text)
            path_response = http_client.post(
                "/api/platform/v1/tools/generate_career_path",
                headers=headers,
                json={
                    "schema_version": "stage3-tool-v1",
                    "idempotency_key": "http-path-consistency-001",
                    "session_id": http_session,
                    "user_id": USER_ID,
                },
            )
            self.assertEqual(200, path_response.status_code, path_response.text)

        self.assertEqual(
            mcp_match["data"]["match_result"],
            match_response.json()["data"]["match_result"],
        )
        self.assertEqual(
            mcp_path["data"]["career_roadmap"],
            path_response.json()["data"]["career_roadmap"],
        )
        http_db.unlink(missing_ok=True)
        Path(f"{http_db}-shm").unlink(missing_ok=True)
        Path(f"{http_db}-wal").unlink(missing_ok=True)

    async def test_prerequisites_and_schema_rejection_are_explicit(self) -> None:
        async with Client(self.server, mode="legacy") as client:
            missing = await client.call_tool(
                "analyze_job_match",
                {"session_id": "mcp-missing", "user_id": USER_ID},
            )
            missing_body = missing.structured_content
            self.assertFalse(missing_body["success"])
            self.assertEqual("SESSION_NOT_FOUND", missing_body["error_code"])
            self.assertEqual(
                ["student_profile", "job_profile"], missing_body["missing_fields"]
            )

            job_only = {"session_id": "mcp-job-only", "user_id": USER_ID}
            await client.call_tool(
                "analyze_target_job",
                {**job_only, "target_job_input": target_job_input()},
            )
            missing_profile = await client.call_tool(
                "analyze_job_match", job_only
            )
            missing_profile_body = missing_profile.structured_content
            self.assertFalse(missing_profile_body["success"])
            self.assertEqual(
                "MATCH_PREREQUISITES_NOT_READY",
                missing_profile_body["error_code"],
            )
            self.assertEqual(
                ["student_profile"], missing_profile_body["missing_fields"]
            )

            common = {"session_id": "mcp-path-early", "user_id": USER_ID}
            await client.call_tool(
                "build_student_profile",
                {**common, "student_input": student_input()},
            )
            await client.call_tool(
                "analyze_target_job",
                {**common, "target_job_input": target_job_input()},
            )
            early_path = await client.call_tool("generate_career_path", common)
            early_body = early_path.structured_content
            self.assertFalse(early_body["success"])
            self.assertEqual("MATCH_NOT_COMPLETED", early_body["error_code"])
            self.assertEqual(["match_result"], early_body["missing_fields"])

            invalid = await client.call_tool(
                "analyze_job_match", {"session_id": "missing-user-id"}
            )
            self.assertTrue(invalid.is_error)
            extra = await client.call_tool(
                "analyze_job_match",
                {
                    "session_id": "unexpected-field",
                    "user_id": USER_ID,
                    "invented_score": 100,
                },
            )
            self.assertTrue(extra.is_error)

    async def test_streamable_http_authorization_and_remote_call(self) -> None:
        app = create_app(
            self.orchestrator,
            mcp_enabled=True,
            mcp_auth_enabled=True,
            mcp_api_token=TOKEN,
            mcp_host="127.0.0.1",
            mcp_path="/mcp",
            mcp_allowed_hosts=["testserver"],
            mcp_allowed_origins=["http://testserver"],
        )
        transport = httpx2.ASGITransport(app=app)
        async with app.router.lifespan_context(app):
            async with httpx2.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as unauthorized:
                response = await unauthorized.post(
                    "/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-11-25",
                            "capabilities": {},
                            "clientInfo": {"name": "test", "version": "1"},
                        },
                    },
                    headers={"Accept": "application/json, text/event-stream"},
                )
                self.assertEqual(401, response.status_code)
                self.assertNotIn(TOKEN, response.text)

            async with httpx2.AsyncClient(
                transport=transport,
                base_url="http://testserver",
                headers={"Authorization": f"Bearer {TOKEN}"},
                follow_redirects=True,
            ) as authorized_http:
                remote_transport = streamable_http_client(
                    "http://testserver/mcp",
                    http_client=authorized_http,
                )
                async with Client(remote_transport, mode="legacy") as client:
                    self.assertIsNotNone(client.session.initialize_result)
                    listed = await client.list_tools()
                    self.assertEqual(4, len(listed.tools))
                    result = await client.call_tool(
                        "analyze_job_match",
                        {"session_id": "remote-missing", "user_id": USER_ID},
                    )
                    self.assertFalse(result.structured_content["success"])
                    self.assertEqual(
                        "SESSION_NOT_FOUND",
                        result.structured_content["error_code"],
                    )


if __name__ == "__main__":
    unittest.main()
