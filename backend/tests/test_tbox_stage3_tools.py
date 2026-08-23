"""HTTP contract tests for the minimal Ant TBox stage-3 tool adapter."""

from __future__ import annotations

import asyncio
import json
import unittest
import uuid
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.agents.match_agent import MatchAgent
from app.agents.path_agent import PathAgent
from app.db_state import StateRepository
from app.main import create_app
from app.orchestrator import CareerOrchestrator
from app.services.match_service import MatchService
from app.schemas.platform_tool_schema import (
    AnalyzeJobMatchRequest,
    AnalyzeJobMatchResponse,
)
from .stage3_fixtures import OfflineLLMClient, job_profile, student_profile


TOKEN = "test-only-tbox-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class SlowMatchAgent(MatchAgent):
    async def _execute(self, state: Any) -> dict[str, Any]:
        await asyncio.sleep(0.1)
        return await super()._execute(state)


def platform_orchestrator(
    repository: StateRepository,
    *,
    slow_match: bool = False,
) -> CareerOrchestrator:
    client = OfflineLLMClient()
    match_agent = SlowMatchAgent(client=client) if slow_match else MatchAgent(client=client)
    return CareerOrchestrator(
        agents=[match_agent, PathAgent(client=client)],
        repository=repository,
    )


def match_request(
    session_id: str,
    idempotency_key: str = "match-call-0001",
) -> dict[str, Any]:
    return {
        "schema_version": "stage3-tool-v1",
        "idempotency_key": idempotency_key,
        "session_id": session_id,
        "platform_session_id": f"tbox-{session_id}",
        "user_id": "anonymous-user-001",
        "student_profile": student_profile(),
        "job_profile": job_profile(),
    }


def path_request(
    session_id: str,
    idempotency_key: str = "path-call-0001",
) -> dict[str, Any]:
    return {
        "schema_version": "stage3-tool-v1",
        "idempotency_key": idempotency_key,
        "session_id": session_id,
        "platform_session_id": f"tbox-{session_id}",
        "user_id": "anonymous-user-001",
    }


class TBoxStageThreeToolTests(unittest.TestCase):
    def setUp(self) -> None:
        runtime_dir = Path(__file__).resolve().parents[1] / ".runtime" / "tests"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = runtime_dir / f"tbox-tools-{uuid.uuid4().hex}.sqlite3"
        self.repository = StateRepository(sqlite_path=self.db_path)
        self.client = TestClient(
            create_app(
                platform_orchestrator(self.repository),
                tbox_api_token=TOKEN,
                tbox_tool_timeout_seconds=2,
            ),
            raise_server_exceptions=False,
        )

    def tearDown(self) -> None:
        self.client.close()
        self.db_path.unlink(missing_ok=True)
        Path(f"{self.db_path}-shm").unlink(missing_ok=True)
        Path(f"{self.db_path}-wal").unlink(missing_ok=True)

    def test_match_path_queries_are_deterministic_logged_and_durable(self) -> None:
        session_id = "tbox-stage3-complete"
        match_payload = match_request(session_id)
        response = self.client.post(
            "/api/platform/v1/tools/analyze_job_match",
            headers=AUTH,
            json=match_payload,
        )
        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertEqual(0, body["code"])
        self.assertEqual("analyze_job_match", body["data"]["tool_name"])
        self.assertFalse(body["data"]["idempotent_replay"])
        expected_match = MatchService().calculate(
            MatchAgent._flatten_profile(student_profile()), job_profile()
        )
        self.assertEqual(expected_match, body["data"]["match_result"])
        match_call_id = body["request_id"]

        replay = self.client.post(
            "/api/platform/v1/tools/analyze_job_match",
            headers=AUTH,
            json=match_payload,
        )
        self.assertEqual(200, replay.status_code, replay.text)
        self.assertEqual(match_call_id, replay.json()["request_id"])
        self.assertTrue(replay.json()["data"]["idempotent_replay"])
        self.assertEqual(
            1,
            len(self.repository.list_agent_logs(session_id, "MatchAgent")),
        )

        path_response = self.client.post(
            "/api/platform/v1/tools/generate_career_path",
            headers=AUTH,
            json=path_request(session_id),
        )
        self.assertEqual(200, path_response.status_code, path_response.text)
        path_body = path_response.json()
        roadmap = path_body["data"]["career_roadmap"]
        self.assertEqual("success", roadmap["status"])
        self.assertEqual(3, len(roadmap["three_year_roadmap"]["stages"]))
        self.assertEqual(5, len(roadmap["five_year_roadmap"]["stages"]))
        self.assertTrue(roadmap["recommended_path"])
        path_call_id = path_body["request_id"]

        for call_id, expected_agent in (
            (match_call_id, f"{session_id}:MatchAgent"),
            (path_call_id, f"{session_id}:PathAgent"),
        ):
            status_response = self.client.get(
                f"/api/platform/v1/tools/calls/{call_id}/status", headers=AUTH
            )
            self.assertEqual(200, status_response.status_code, status_response.text)
            self.assertEqual("succeeded", status_response.json()["data"]["status"])
            self.assertTrue(status_response.json()["data"]["result_available"])
            self.assertEqual(expected_agent, status_response.json()["data"]["agent_run_id"])

            result_response = self.client.get(
                f"/api/platform/v1/tools/calls/{call_id}/result", headers=AUTH
            )
            self.assertEqual(200, result_response.status_code, result_response.text)
            self.assertEqual(expected_agent, result_response.json()["data"]["agent_run_id"])

        fresh_client = TestClient(
            create_app(
                platform_orchestrator(StateRepository(sqlite_path=self.db_path)),
                tbox_api_token=TOKEN,
            )
        )
        try:
            durable = fresh_client.get(
                f"/api/platform/v1/tools/calls/{path_call_id}/result", headers=AUTH
            )
            self.assertEqual(200, durable.status_code, durable.text)
            self.assertEqual(roadmap, durable.json()["data"]["career_roadmap"])
        finally:
            fresh_client.close()

        record = self.repository.get_tool_call(match_call_id)
        assert record is not None
        self.assertEqual(f"{session_id}:MatchAgent", record["agent_run_key"])
        self.assertEqual(64, len(record["user_id_hash"]))
        self.assertEqual({"result_field": "match_result"}, record["result_data"])
        serialized_record = json.dumps(record, ensure_ascii=False, default=str)
        self.assertNotIn("anonymous-user-001", serialized_record)
        self.assertNotIn("test-only-tbox-token", serialized_record)
        self.assertNotIn("演示学生C", serialized_record)
        self.assertNotIn("完成匿名AI产品方案和需求拆解项目", serialized_record)

    def test_auth_fixed_schema_idempotency_and_prerequisites(self) -> None:
        session_id = "tbox-stage3-errors"
        payload = match_request(session_id, "shared-key-0001")

        unconfigured_client = TestClient(
            create_app(
                platform_orchestrator(StateRepository(sqlite_path=self.db_path)),
                tbox_api_token="",
            ),
            raise_server_exceptions=False,
        )
        try:
            unconfigured = unconfigured_client.post(
                "/api/platform/v1/tools/analyze_job_match",
                headers=AUTH,
                json=payload,
            )
            self.assertEqual(503, unconfigured.status_code)
            self.assertEqual("TOOL_AUTH_NOT_CONFIGURED", unconfigured.json()["error"]["type"])
        finally:
            unconfigured_client.close()

        missing_auth = self.client.post(
            "/api/platform/v1/tools/analyze_job_match", json=payload
        )
        self.assertEqual(401, missing_auth.status_code)
        self.assertEqual(-7, missing_auth.json()["code"])
        self.assertEqual("AUTHENTICATION_FAILED", missing_auth.json()["error"]["type"])

        invalid = dict(payload)
        invalid["overall_score"] = 100
        invalid_response = self.client.post(
            "/api/platform/v1/tools/analyze_job_match", headers=AUTH, json=invalid
        )
        self.assertEqual(422, invalid_response.status_code)
        self.assertEqual(-2, invalid_response.json()["code"])

        missing_version = dict(payload)
        missing_version.pop("schema_version")
        missing_version_response = self.client.post(
            "/api/platform/v1/tools/analyze_job_match",
            headers=AUTH,
            json=missing_version,
        )
        self.assertEqual(422, missing_version_response.status_code)
        self.assertEqual(-2, missing_version_response.json()["code"])

        success = self.client.post(
            "/api/platform/v1/tools/analyze_job_match", headers=AUTH, json=payload
        )
        self.assertEqual(200, success.status_code, success.text)

        conflict_payload = match_request("different-session", "shared-key-0001")
        conflict = self.client.post(
            "/api/platform/v1/tools/analyze_job_match",
            headers=AUTH,
            json=conflict_payload,
        )
        self.assertEqual(409, conflict.status_code, conflict.text)
        self.assertEqual(-8, conflict.json()["code"])
        self.assertEqual("IDEMPOTENCY_KEY_CONFLICT", conflict.json()["error"]["type"])

        path_with_score = path_request(session_id, "path-extra-0001")
        path_with_score["match_result"] = {"overall_score": 100}
        rejected_override = self.client.post(
            "/api/platform/v1/tools/generate_career_path",
            headers=AUTH,
            json=path_with_score,
        )
        self.assertEqual(422, rejected_override.status_code)
        self.assertEqual(-2, rejected_override.json()["code"])

        too_early = self.client.post(
            "/api/platform/v1/tools/generate_career_path",
            headers=AUTH,
            json=path_request("session-without-match", "path-early-0001"),
        )
        self.assertEqual(404, too_early.status_code, too_early.text)
        self.assertEqual(-3, too_early.json()["code"])
        rejected_call_id = too_early.json()["request_id"]
        rejected_record = self.repository.get_tool_call(rejected_call_id)
        assert rejected_record is not None
        self.assertIsNone(rejected_record["agent_run_key"])
        unavailable = self.client.get(
            f"/api/platform/v1/tools/calls/{rejected_call_id}/result",
            headers=AUTH,
        )
        self.assertEqual(409, unavailable.status_code, unavailable.text)
        self.assertEqual(-9, unavailable.json()["code"])

    def test_timeout_is_persisted_and_linked_to_failed_agent_run(self) -> None:
        timeout_client = TestClient(
            create_app(
                platform_orchestrator(self.repository, slow_match=True),
                tbox_api_token=TOKEN,
                tbox_tool_timeout_seconds=0.01,
            ),
            raise_server_exceptions=False,
        )
        try:
            session_id = "tbox-stage3-timeout"
            response = timeout_client.post(
                "/api/platform/v1/tools/analyze_job_match",
                headers=AUTH,
                json=match_request(session_id, "timeout-key-0001"),
            )
            self.assertEqual(504, response.status_code, response.text)
            self.assertEqual(-6, response.json()["code"])
            call_id = response.json()["request_id"]
            record = self.repository.get_tool_call(call_id)
            assert record is not None
            self.assertEqual("timed_out", record["status"])
            self.assertEqual(f"{session_id}:MatchAgent", record["agent_run_key"])
            logs = self.repository.list_agent_logs(session_id, "MatchAgent")
            self.assertEqual(1, len(logs))
            self.assertEqual("failed", logs[0]["status"])
            self.assertNotIn("student_profile", logs[0]["tool_calls"][0]["input_summary"])
        finally:
            timeout_client.close()

    def test_openapi_exposes_only_stage3_tool_operations_and_bearer_security(self) -> None:
        schema = self.client.get("/openapi.json").json()
        paths = schema["paths"]
        self.assertIn("/api/platform/v1/tools/analyze_job_match", paths)
        self.assertIn("/api/platform/v1/tools/generate_career_path", paths)
        self.assertIn("/api/platform/v1/tools/calls/{tool_call_id}/status", paths)
        self.assertIn("/api/platform/v1/tools/calls/{tool_call_id}/result", paths)
        operation_ids = {
            operation["operationId"]
            for path, methods in paths.items()
            if path.startswith("/api/platform/v1/tools")
            for operation in methods.values()
        }
        self.assertEqual(
            {
                "analyze_job_match",
                "generate_career_path",
                "get_stage3_tool_call_status",
                "get_stage3_tool_call_result",
            },
            operation_ids,
        )
        security = schema["components"]["securitySchemes"]["TBoxBearerAuth"]
        self.assertEqual("http", security["type"])
        self.assertEqual("bearer", security["scheme"])

    def test_documented_complete_mock_validates_against_frozen_schemas(self) -> None:
        mock_path = (
            Path(__file__).resolve().parents[2]
            / "docs"
            / "a02"
            / "examples"
            / "tbox_stage3_match_mock.json"
        )
        documented = json.loads(mock_path.read_text(encoding="utf-8"))
        AnalyzeJobMatchRequest.model_validate(documented["request"])
        AnalyzeJobMatchResponse.model_validate(documented["response"])
        self.assertEqual(
            "/api/platform/v1/tools/analyze_job_match",
            documented["http"]["path"],
        )


if __name__ == "__main__":
    unittest.main()
