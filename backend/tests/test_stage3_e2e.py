"""Local HTTP end-to-end acceptance tests for A02 stage 3."""

from __future__ import annotations

import copy
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
from app.services.career_graph_repository import CareerGraphRepository
from app.services.match_service import MatchService
from app.services.path_service import PathService
from .stage3_fixtures import OfflineLLMClient, job_profile, student_profile


class NarrativeLLMClient:
    """Return prose plus attempted deterministic-field overrides."""

    async def generate_structured(
        self, messages: Any, response_model: Any, **kwargs: Any
    ) -> Any:
        if response_model.__name__ == "_LLMEnhancement":
            return response_model.model_validate(
                {
                    "suggestions": {"产品规划": "完成匿名产品规划练习"},
                    "strengths_summary": "具备可验证的跨领域基础",
                }
            )
        return response_model.model_validate(
            {
                "stages": [
                    {
                        "stage_index": 1,
                        "target_role": "禁止覆盖的岗位",
                        "duration_months": 99,
                        "score": 999999,
                        "objectives": ["补充自然语言目标"],
                        "suggested_actions": ["补充自然语言行动"],
                        "completion_criteria": "补充自然语言标准",
                    }
                ]
            }
        )


class FailingMatchService:
    def calculate(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("private resume content must never enter logs")


class NoEntryCareerGraphRepository(CareerGraphRepository):
    def entry_roles(
        self, industry: str | None = None, *, include_junior: bool = False
    ):
        return []


class FailingLogRepository(StateRepository):
    """Raise after state upsert so the transaction rollback can be observed."""

    def _upsert_logs(self, connection, session_id, logs):
        if logs:
            raise OSError("simulated database log write failure")
        return super()._upsert_logs(connection, session_id, logs)


def orchestrator_for(
    repository: StateRepository,
    path_service: PathService | None = None,
    match_service: MatchService | None = None,
    llm_client: Any | None = None,
) -> CareerOrchestrator:
    client = llm_client or OfflineLLMClient()
    return CareerOrchestrator(
        agents=[
            MatchAgent(client=client, service=match_service),
            PathAgent(client=client, service=path_service),
        ],
        repository=repository,
    )


class StageThreeEndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime_test_dir = (
            Path(__file__).resolve().parents[1] / ".runtime" / "tests"
        )
        self.runtime_test_dir.mkdir(parents=True, exist_ok=True)
        self.db_files: list[Path] = []
        self.db_path = self._new_db_path("main")
        self.repository = StateRepository(sqlite_path=self.db_path)
        self.client = TestClient(
            create_app(orchestrator_for(self.repository)),
            raise_server_exceptions=False,
        )

    def tearDown(self) -> None:
        self.client.close()
        for db_path in self.db_files:
            db_path.unlink(missing_ok=True)
            Path(f"{db_path}-shm").unlink(missing_ok=True)
            Path(f"{db_path}-wal").unlink(missing_ok=True)

    def _new_db_path(self, label: str) -> Path:
        path = self.runtime_test_dir / f"{label}-{uuid.uuid4().hex}.sqlite3"
        self.db_files.append(path)
        return path

    @staticmethod
    def _prepare_payload(
        session_id: str,
        *,
        student: dict[str, Any] | None = None,
        job: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "session_id": session_id,
            "user_id": "user-e2e-001",
        }
        if student is not None:
            payload["student_profile"] = student
        if job is not None:
            payload["job_profile"] = job
        return payload

    def _prepare_complete(self, session_id: str) -> dict[str, Any]:
        response = self.client.post(
            "/api/career-agent/stage3/prepare",
            json=self._prepare_payload(
                session_id, student=student_profile(), job=job_profile()
            ),
        )
        self.assertEqual(200, response.status_code, response.text)
        return response.json()

    def test_complete_chain_is_service_consistent_logged_and_durable(self) -> None:
        session_id = "stage3-e2e-main"
        prepared = self._prepare_complete(session_id)
        self.assertEqual("INITIALIZED", prepared["status"])

        match_response = self.client.post(
            "/api/career-agent/stage3/match",
            json={"session_id": session_id, "user_id": "user-e2e-001"},
        )
        self.assertEqual(200, match_response.status_code, match_response.text)
        matched_state = match_response.json()
        self.assertEqual("MATCH_COMPLETED", matched_state["status"])

        expected_match = MatchService().calculate(
            MatchAgent._flatten_profile(student_profile()), job_profile()
        )
        actual_match = matched_state["match_result"]
        self.assertEqual(expected_match, actual_match)
        self.assertGreater(actual_match["overall_score"], 0)
        self.assertTrue(actual_match["dimension_matches"])
        self.assertTrue(actual_match["matched_skills"])
        self.assertTrue(actual_match["skill_gaps"])

        student_tags = {
            tag
            for dimension in student_profile()["ability_dimensions"]
            for tag in dimension["tags"]
        }
        job_tags = {
            ability["tag"] for ability in job_profile()["required_abilities"]
        }
        self.assertEqual(student_tags, job_tags)
        for gap in actual_match["skill_gaps"]:
            self.assertIn(gap["dimension"], student_tags)
            self.assertTrue(gap["student_evidence"])
            self.assertTrue(gap["job_evidence"])

        queried_after_match = self.client.get(
            f"/api/career-agent/session/{session_id}"
        )
        self.assertEqual("MATCH_COMPLETED", queried_after_match.json()["status"])

        path_response = self.client.post(
            "/api/career-agent/stage3/path",
            json={"session_id": session_id, "user_id": "user-e2e-001"},
        )
        self.assertEqual(200, path_response.status_code, path_response.text)
        path_state = path_response.json()
        self.assertEqual("PATH_COMPLETED", path_state["status"])

        expected_path = PathService().calculate(
            student_profile=PathAgent._flatten_profile(student_profile()),
            target_job_profile=job_profile(),
            match_result=expected_match,
            user_preferences=PathAgent._extract_preferences(student_profile()),
            horizon_years=3,
        )
        roadmap = path_state["career_roadmap"]
        self.assertEqual(expected_path, roadmap)
        self.assertEqual("success", roadmap["status"])
        self.assertTrue(roadmap["candidate_paths"])
        self.assertIsNotNone(roadmap["recommended_path"])
        self.assertTrue(roadmap["alternative_paths"])
        self.assertEqual(3, len(roadmap["three_year_roadmap"]["stages"]))
        self.assertEqual(5, len(roadmap["five_year_roadmap"]["stages"]))
        self.assertNotEqual(
            roadmap["three_year_roadmap"]["stages"],
            roadmap["five_year_roadmap"]["stages"],
        )
        self.assertEqual(
            roadmap["recommended_path"]["score"],
            roadmap["path_scores"][roadmap["recommended_path"]["path_id"]],
        )

        logs_response = self.client.get(f"/api/agent/logs/{session_id}")
        self.assertEqual(200, logs_response.status_code, logs_response.text)
        logs = logs_response.json()
        self.assertEqual(["MatchAgent", "PathAgent"], [log["agent_name"] for log in logs])
        self.assertEqual(["MatchService", "PathService"], [log["service_name"] for log in logs])
        self.assertTrue(all(log["status"] == "success" for log in logs))
        self.assertTrue(all(log["duration_ms"] >= 0 for log in logs))
        serialized_logs = json.dumps(logs, ensure_ascii=False)
        self.assertNotIn("演示学生C", serialized_logs)
        self.assertNotIn("完成匿名AI产品方案和需求拆解项目", serialized_logs)
        self.assertNotIn("A02_LLM_API_KEY", serialized_logs)

        # Same requests are idempotent and do not add duplicate Agent logs.
        duplicate_match = self.client.post(
            "/api/career-agent/stage3/match", json={"session_id": session_id}
        )
        duplicate_path = self.client.post(
            "/api/career-agent/stage3/path", json={"session_id": session_id}
        )
        self.assertEqual(200, duplicate_match.status_code)
        self.assertEqual(200, duplicate_path.status_code)
        self.assertEqual(2, len(self.client.get(f"/api/agent/logs/{session_id}").json()))

        # A fresh repository, orchestrator, and FastAPI instance must read the file.
        fresh_repository = StateRepository(sqlite_path=self.db_path)
        fresh_client = TestClient(
            create_app(orchestrator_for(fresh_repository)),
            raise_server_exceptions=False,
        )
        try:
            durable_state = fresh_client.get(
                f"/api/career-agent/session/{session_id}"
            )
            durable_logs = fresh_client.get(f"/api/agent/logs/{session_id}")
            self.assertEqual(200, durable_state.status_code, durable_state.text)
            self.assertEqual("PATH_COMPLETED", durable_state.json()["status"])
            self.assertEqual(roadmap, durable_state.json()["career_roadmap"])
            self.assertEqual(2, len(durable_logs.json()))
            self.assertTrue(self.db_path.is_file())
        finally:
            fresh_client.close()

    def test_missing_student_and_job_profiles_are_distinct_failures(self) -> None:
        student_missing = "stage3-missing-student"
        response = self.client.post(
            "/api/career-agent/stage3/prepare",
            json=self._prepare_payload(student_missing, job=job_profile()),
        )
        self.assertEqual(200, response.status_code)
        response = self.client.post(
            "/api/career-agent/stage3/match",
            json={"session_id": student_missing},
        )
        self.assertEqual(404, response.status_code)
        failed = self.client.get(
            f"/api/career-agent/session/{student_missing}"
        ).json()
        self.assertEqual("FAILED", failed["status"])
        self.assertEqual("STUDENT_PROFILE_NOT_FOUND", failed["error_type"])

        job_missing = "stage3-missing-job"
        response = self.client.post(
            "/api/career-agent/stage3/prepare",
            json=self._prepare_payload(job_missing, student=student_profile()),
        )
        self.assertEqual(200, response.status_code)
        response = self.client.post(
            "/api/career-agent/stage3/match",
            json={"session_id": job_missing},
        )
        self.assertEqual(404, response.status_code)
        failed = self.client.get(
            f"/api/career-agent/session/{job_missing}"
        ).json()
        self.assertEqual("JOB_PROFILE_NOT_FOUND", failed["error_type"])

    def test_incomplete_student_and_empty_job_vector_are_rejected(self) -> None:
        incomplete = student_profile()
        incomplete["ability_dimensions"] = []
        incomplete["ability_tags"] = []
        session_id = "stage3-incomplete-student"
        response = self.client.post(
            "/api/career-agent/stage3/prepare",
            json=self._prepare_payload(
                session_id, student=incomplete, job=job_profile()
            ),
        )
        self.assertEqual(200, response.status_code)
        response = self.client.post(
            "/api/career-agent/stage3/match", json={"session_id": session_id}
        )
        self.assertEqual(422, response.status_code)
        failed = self.client.get(f"/api/career-agent/session/{session_id}").json()
        self.assertEqual("STUDENT_PROFILE_INCOMPLETE", failed["error_type"])

        empty_job = job_profile()
        empty_job["required_abilities"] = []
        response = self.client.post(
            "/api/career-agent/stage3/prepare",
            json=self._prepare_payload(
                "stage3-empty-job", student=student_profile(), job=empty_job
            ),
        )
        self.assertEqual(422, response.status_code)

    def test_path_before_match_is_rejected_and_persisted(self) -> None:
        session_id = "stage3-path-too-early"
        self._prepare_complete(session_id)
        response = self.client.post(
            "/api/career-agent/stage3/path", json={"session_id": session_id}
        )
        self.assertEqual(409, response.status_code)
        state_value = self.client.get(
            f"/api/career-agent/session/{session_id}"
        ).json()
        self.assertEqual("FAILED", state_value["status"])
        self.assertEqual("MATCH_NOT_COMPLETED", state_value["error_type"])

    def test_unknown_target_job_uses_explicit_graph_fallback(self) -> None:
        session_id = "stage3-unknown-target"
        response = self.client.post(
            "/api/career-agent/stage3/prepare",
            json=self._prepare_payload(
                session_id,
                student=student_profile(),
                job=job_profile("量子职业导航师"),
            ),
        )
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(
            200,
            self.client.post(
                "/api/career-agent/stage3/match", json={"session_id": session_id}
            ).status_code,
        )
        response = self.client.post(
            "/api/career-agent/stage3/path", json={"session_id": session_id}
        )
        self.assertEqual(200, response.status_code, response.text)
        roadmap = response.json()["career_roadmap"]
        self.assertIn(
            "target_not_in_graph:量子职业导航师", roadmap["data_quality_flags"]
        )
        self.assertTrue(roadmap["recommended_path"]["fallback_target"])

    def test_no_reachable_path_returns_deterministic_empty_result(self) -> None:
        db_path = self._new_db_path("no-path")
        repository = StateRepository(sqlite_path=db_path)
        path_service = PathService(repository=NoEntryCareerGraphRepository())
        client = TestClient(
            create_app(orchestrator_for(repository, path_service=path_service)),
            raise_server_exceptions=False,
        )
        try:
            session_id = "stage3-no-path"
            response = client.post(
                "/api/career-agent/stage3/prepare",
                json=self._prepare_payload(
                    session_id, student=student_profile(), job=job_profile()
                ),
            )
            self.assertEqual(200, response.status_code)
            self.assertEqual(
                200,
                client.post(
                    "/api/career-agent/stage3/match",
                    json={"session_id": session_id},
                ).status_code,
            )
            response = client.post(
                "/api/career-agent/stage3/path",
                json={"session_id": session_id},
            )
            self.assertEqual(200, response.status_code, response.text)
            self.assertEqual("PATH_COMPLETED", response.json()["status"])
            roadmap = response.json()["career_roadmap"]
            self.assertEqual("no_reachable_path", roadmap["status"])
            self.assertEqual([], roadmap["candidate_paths"])
            self.assertIsNone(roadmap["recommended_path"])
        finally:
            client.close()

    def test_database_failure_rolls_back_state_and_logs(self) -> None:
        db_path = self._new_db_path("rollback")
        failing_repository = FailingLogRepository(sqlite_path=db_path)
        client = TestClient(
            create_app(orchestrator_for(failing_repository)),
            raise_server_exceptions=False,
        )
        try:
            session_id = "stage3-db-rollback"
            response = client.post(
                "/api/career-agent/stage3/prepare",
                json=self._prepare_payload(
                    session_id, student=student_profile(), job=job_profile()
                ),
            )
            self.assertEqual(200, response.status_code, response.text)
            response = client.post(
                "/api/career-agent/stage3/match",
                json={"session_id": session_id},
            )
            self.assertEqual(503, response.status_code, response.text)
        finally:
            client.close()

        fresh_repository = StateRepository(sqlite_path=db_path)
        rolled_back = fresh_repository.get_state("stage3-db-rollback")
        self.assertIsNotNone(rolled_back)
        self.assertEqual("INITIALIZED", rolled_back["status"])
        self.assertIsNone(rolled_back["match_result"])
        self.assertEqual([], fresh_repository.list_agent_logs("stage3-db-rollback"))

    def test_llm_narrative_cannot_override_service_values(self) -> None:
        db_path = self._new_db_path("llm-boundary")
        repository = StateRepository(sqlite_path=db_path)
        client = TestClient(
            create_app(
                orchestrator_for(
                    repository,
                    llm_client=NarrativeLLMClient(),
                )
            ),
            raise_server_exceptions=False,
        )
        try:
            session_id = "stage3-llm-boundary"
            response = client.post(
                "/api/career-agent/stage3/prepare",
                json=self._prepare_payload(
                    session_id, student=student_profile(), job=job_profile()
                ),
            )
            self.assertEqual(200, response.status_code, response.text)
            response = client.post(
                "/api/career-agent/stage3/match",
                json={"session_id": session_id},
            )
            self.assertEqual(200, response.status_code, response.text)
            actual_match = response.json()["match_result"]
            service_match = MatchService().calculate(
                MatchAgent._flatten_profile(student_profile()), job_profile()
            )
            for field in (
                "overall_score",
                "match_level",
                "dimension_matches",
                "matched_skills",
                "missing_skills",
                "skill_gaps",
                "hard_constraint_results",
                "confidence",
                "evidence",
                "calculation_version",
            ):
                self.assertEqual(service_match[field], actual_match[field])

            response = client.post(
                "/api/career-agent/stage3/path",
                json={"session_id": session_id},
            )
            self.assertEqual(200, response.status_code, response.text)
            actual_path = response.json()["career_roadmap"]
            service_path = PathService().calculate(
                student_profile=PathAgent._flatten_profile(student_profile()),
                target_job_profile=job_profile(),
                match_result=actual_match,
                user_preferences=PathAgent._extract_preferences(student_profile()),
                horizon_years=3,
            )
            for field in (
                "status",
                "candidate_paths",
                "recommended_path",
                "alternative_paths",
                "path_scores",
                "calculation_version",
            ):
                self.assertEqual(service_path[field], actual_path[field])
            for horizon in ("three_year_roadmap", "five_year_roadmap"):
                expected_stages = service_path[horizon]["stages"]
                actual_stages = actual_path[horizon]["stages"]
                self.assertEqual(len(expected_stages), len(actual_stages))
                for expected, actual in zip(expected_stages, actual_stages):
                    for field in (
                        "stage_index",
                        "year_label",
                        "duration_months",
                        "target_role",
                        "target_node_key",
                        "key_abilities",
                        "current_gaps",
                    ):
                        self.assertEqual(expected[field], actual[field])
                    self.assertNotEqual("禁止覆盖的岗位", actual["target_role"])
                    self.assertNotEqual(99, actual["duration_months"])
        finally:
            client.close()

    def test_agent_failure_has_typed_private_safe_log(self) -> None:
        db_path = self._new_db_path("agent-failure")
        repository = StateRepository(sqlite_path=db_path)
        client = TestClient(
            create_app(
                orchestrator_for(
                    repository,
                    match_service=FailingMatchService(),  # type: ignore[arg-type]
                )
            ),
            raise_server_exceptions=False,
        )
        try:
            session_id = "stage3-agent-failure"
            response = client.post(
                "/api/career-agent/stage3/prepare",
                json=self._prepare_payload(
                    session_id, student=student_profile(), job=job_profile()
                ),
            )
            self.assertEqual(200, response.status_code, response.text)
            response = client.post(
                "/api/career-agent/stage3/match",
                json={"session_id": session_id},
            )
            self.assertEqual(422, response.status_code, response.text)
            state_value = client.get(
                f"/api/career-agent/session/{session_id}"
            ).json()
            self.assertEqual("FAILED", state_value["status"])
            self.assertEqual("RuntimeError", state_value["error_type"])
            logs = client.get(f"/api/agent/logs/{session_id}").json()
            self.assertEqual(1, len(logs))
            self.assertEqual("MatchAgent", logs[0]["agent_name"])
            self.assertEqual("MatchService", logs[0]["service_name"])
            self.assertEqual("failed", logs[0]["status"])
            self.assertTrue(logs[0]["error"])
            self.assertNotIn("private resume content", logs[0]["error"])
        finally:
            client.close()

    def test_duplicate_prepare_conflict_and_invalid_identifiers(self) -> None:
        session_id = "stage3-idempotency"
        original = self._prepare_complete(session_id)
        repeated = self.client.post(
            "/api/career-agent/stage3/prepare",
            json=self._prepare_payload(
                session_id, student=student_profile(), job=job_profile()
            ),
        )
        self.assertEqual(200, repeated.status_code)
        self.assertEqual(original, repeated.json())

        changed_job = job_profile()
        changed_job["job_description"] = "同一会话下的冲突岗位画像"
        conflict = self.client.post(
            "/api/career-agent/stage3/prepare",
            json=self._prepare_payload(
                session_id, student=student_profile(), job=changed_job
            ),
        )
        self.assertEqual(409, conflict.status_code)

        for payload in (
            {"session_id": "../bad"},
            {"session_id": "valid-session", "user_id": "bad user"},
            {"session_id": "valid-session", "unexpected": True},
        ):
            response = self.client.post(
                "/api/career-agent/stage3/match", json=payload
            )
            self.assertEqual(422, response.status_code, response.text)


if __name__ == "__main__":
    unittest.main()
