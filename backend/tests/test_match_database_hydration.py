"""MatchAgent database hydration and snapshot gate coverage."""

from __future__ import annotations

import copy
import json
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.agents.match_agent import MatchAgent
from app.db_state import StateRepository
from app.mcp.tool_service import CareerMCPToolService
from app.orchestrator import CareerOrchestrator, CareerState
from app.schemas.career_profile_schema import StudentProfile
from app.schemas.job_schema import JobProfile
from app.schemas.mcp_tool_schema import AnalyzeJobMatchMCPRequest
from app.schemas.student_persistence_schema import StudentProfilePersistenceResult
from app.services.match_service import MatchService
from app.tools.database_tools import DatabaseTools


class OfflineClient:
    async def generate_structured(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("offline")


def student_profile() -> StudentProfile:
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    return StudentProfile(
        user_id="match-user",
        basic_info={
            "education_level": "本科",
            "major": "计算机科学",
            "graduation_year": 2027,
            "target_job": "后端开发",
            "target_industry": "企业服务/SaaS",
        },
        ability_dimensions=[
            {
                "dimension": "专业知识",
                "tags": ["Python", "数据库/SQL"],
                "level": 3,
                "confidence": 0.8,
                "evidence": ["匿名课程项目证据"],
                "evidence_source": "history",
            },
            {
                "dimension": "沟通协作",
                "tags": ["沟通表达"],
                "level": 3,
                "confidence": 0.7,
                "evidence": ["匿名协作证据"],
                "evidence_source": "history",
            },
        ],
        ability_tags=["Python", "数据库/SQL", "沟通表达"],
        profile_completeness=0.8,
        career_competitiveness_score=60,
        summary="匿名学生画像摘要",
        created_at=now,
        updated_at=now,
    )


def job_profile() -> JobProfile:
    return JobProfile(
        job_id=8101,
        title="Python后端工程师",
        normalized_title="后端开发",
        industry="企业服务/SaaS",
        required_abilities=[
            {
                "tag": "Python",
                "required_level": 4,
                "weight": 0.6,
                "importance": "critical",
                "evidence": "完整岗位描述中的证据不应进入日志",
            },
            {
                "tag": "沟通表达",
                "required_level": 3,
                "weight": 0.4,
                "importance": "important",
                "evidence": "岗位协作要求",
            },
        ],
        soft_skills=["沟通表达"],
        salary_range="20k-30k",
        job_description="这是完整岗位描述，包含 Python 开发和团队协作要求。",
    )


class FakeStudentService:
    def __init__(self, profile: StudentProfile) -> None:
        self.profile = profile
        self.calls = 0

    def get_profile(self, student_id: int, *, user_id: str):
        self.calls += 1
        return StudentProfilePersistenceResult(
            student_id=student_id,
            name="不进入状态或日志的姓名",
            profile=self.profile.model_copy(update={"user_id": user_id}),
        )


class FakeJobService:
    def __init__(self, profile: JobProfile) -> None:
        self.profile = profile
        self.calls = 0

    def get_context_by_job_id(self, job_id: int):
        self.calls += 1
        return SimpleNamespace(profile=self.profile)

    def get_context_by_type_key(self, type_key: str):
        self.calls += 1
        return SimpleNamespace(profile=self.profile)


class RecordingMatchService(MatchService):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[tuple[dict[str, Any], dict[str, Any]]] = []

    def calculate(self, student_profile: Any, job_profile: Any) -> dict[str, Any]:
        self.requests.append(
            (copy.deepcopy(dict(student_profile)), copy.deepcopy(dict(job_profile)))
        )
        return super().calculate(student_profile, job_profile)


class MatchDatabaseHydrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        runtime = Path(__file__).resolve().parents[1] / ".runtime" / "tests"
        runtime.mkdir(parents=True, exist_ok=True)
        self.db_path = runtime / f"match-hydration-{uuid.uuid4().hex}.sqlite3"
        self.student = student_profile()
        self.job = job_profile()
        self.student_service = FakeStudentService(self.student)
        self.job_service = FakeJobService(self.job)
        self.match_service = RecordingMatchService()
        orchestrator = CareerOrchestrator(
            agents=[
                MatchAgent(client=OfflineClient(), service=self.match_service)
            ],
            repository=StateRepository(sqlite_path=self.db_path),
        )
        self.tools = CareerMCPToolService(
            orchestrator,
            database_tools=DatabaseTools(
                student_service=self.student_service,
                job_service=self.job_service,
            ),
        )

    def tearDown(self) -> None:
        self.db_path.unlink(missing_ok=True)
        Path(f"{self.db_path}-shm").unlink(missing_ok=True)
        Path(f"{self.db_path}-wal").unlink(missing_ok=True)

    def persist(self, state: CareerState) -> None:
        self.tools.orchestrator.persist(state)

    @staticmethod
    def request(session_id: str, trace_id: str) -> AnalyzeJobMatchMCPRequest:
        return AnalyzeJobMatchMCPRequest(
            session_id=session_id,
            user_id="match-user",
            trace_id=trace_id,
        )

    async def test_ids_only_hydrate_before_match_and_log_separately(self) -> None:
        self.persist(
            CareerState(
                session_id="match-ids-only",
                user_id="match-user",
                student_profile_id=701,
                job_record_id=8101,
            )
        )

        result = await self.tools.analyze_job_match(
            self.request("match-ids-only", "match-ids-only-01")
        )

        self.assertTrue(result.success)
        self.assertEqual(1, self.student_service.calls)
        self.assertEqual(1, self.job_service.calls)
        state = self.tools.orchestrator.get_session("match-ids-only")
        self.assertEqual(701, state.student_profile_snapshot_id)
        self.assertEqual(8101, state.job_profile_snapshot_id)
        self.assertEqual("后端开发", state.job_profile_snapshot_type_key)
        self.assertEqual(
            ["MatchContextHydration", "MatchAgent"],
            [item.agent_name for item in state.agent_logs],
        )
        self.assertEqual(
            ["hydrate_student_profile", "hydrate_job_context"],
            [item.tool_name for item in state.agent_logs[0].tool_calls],
        )
        logs = json.dumps(
            [item.model_dump() for item in state.agent_logs],
            ensure_ascii=False,
        )
        self.assertNotIn("不进入状态或日志的姓名", logs)
        self.assertNotIn("匿名课程项目证据", logs)
        self.assertNotIn(self.job.job_description, logs)

    async def test_matching_valid_snapshots_are_reused_without_database_reads(self) -> None:
        self.persist(
            CareerState(
                session_id="match-reuse",
                user_id="match-user",
                student_profile_id=701,
                student_profile_snapshot_id=701,
                student_profile=self.student.model_dump(mode="json"),
                job_record_id=8101,
                job_type_key="后端开发",
                job_profile_snapshot_id=8101,
                job_profile_snapshot_type_key="后端开发",
                job_profile=self.job.model_dump(mode="json"),
            )
        )

        result = await self.tools.analyze_job_match(
            self.request("match-reuse", "match-reuse-01")
        )

        self.assertTrue(result.success)
        self.assertEqual(0, self.student_service.calls)
        self.assertEqual(0, self.job_service.calls)
        state = self.tools.orchestrator.get_session("match-reuse")
        self.assertEqual(["MatchAgent"], [item.agent_name for item in state.agent_logs])

    async def test_snapshot_reference_conflict_is_rejected_without_overwrite(self) -> None:
        original = self.student.model_dump(mode="json")
        self.persist(
            CareerState(
                session_id="match-conflict",
                user_id="match-user",
                student_profile_id=702,
                student_profile_snapshot_id=701,
                student_profile=original,
                job_profile=self.job.model_dump(mode="json"),
            )
        )

        result = await self.tools.analyze_job_match(
            self.request("match-conflict", "match-conflict-01")
        )

        self.assertFalse(result.success)
        self.assertEqual("MATCH_CONTEXT_ID_CONFLICT", result.error_code)
        self.assertEqual(0, self.student_service.calls)
        state = self.tools.orchestrator.get_session("match-conflict")
        self.assertEqual(original, state.student_profile)

    async def test_missing_profiles_return_explicit_missing_fields(self) -> None:
        self.persist(CareerState(session_id="match-missing", user_id="match-user"))

        result = await self.tools.analyze_job_match(
            self.request("match-missing", "match-missing-01")
        )

        self.assertFalse(result.success)
        self.assertEqual("MATCH_PREREQUISITES_NOT_READY", result.error_code)
        self.assertEqual(["student_profile", "job_profile"], result.missing_fields)
        self.assertEqual([], self.match_service.requests)

    async def test_missing_student_abilities_stop_before_match_service(self) -> None:
        empty_student = self.student.model_copy(
            update={"ability_dimensions": [], "ability_tags": []}
        )
        self.persist(
            CareerState(
                session_id="match-no-abilities",
                user_id="match-user",
                student_profile=empty_student.model_dump(mode="json"),
                job_profile=self.job.model_dump(mode="json"),
            )
        )

        result = await self.tools.analyze_job_match(
            self.request("match-no-abilities", "match-no-abilities-01")
        )

        self.assertFalse(result.success)
        self.assertEqual("STUDENT_PROFILE_INCOMPLETE", result.error_code)
        self.assertEqual(
            ["student_profile.ability_dimensions"],
            result.missing_fields,
        )
        self.assertEqual([], self.match_service.requests)

    async def test_missing_job_abilities_stop_before_match_service(self) -> None:
        incomplete_job = self.job.model_dump(mode="json")
        incomplete_job["required_abilities"] = []
        self.persist(
            CareerState(
                session_id="match-no-job-abilities",
                user_id="match-user",
                student_profile=self.student.model_dump(mode="json"),
                job_profile=incomplete_job,
            )
        )

        result = await self.tools.analyze_job_match(
            self.request("match-no-job-abilities", "match-no-job-abilities-01")
        )

        self.assertFalse(result.success)
        self.assertEqual("JOB_ABILITY_DIMENSIONS_EMPTY", result.error_code)
        self.assertEqual(
            ["job_profile.required_abilities"],
            result.missing_fields,
        )
        self.assertEqual([], self.match_service.requests)

    async def test_database_and_json_snapshots_make_identical_service_calls(self) -> None:
        self.persist(
            CareerState(
                session_id="match-database",
                user_id="match-user",
                student_profile_id=701,
                job_record_id=8101,
            )
        )
        database_result = await self.tools.analyze_job_match(
            self.request("match-database", "match-database-01")
        )
        self.persist(
            CareerState(
                session_id="match-json",
                user_id="match-user",
                student_profile=self.student.model_dump(mode="json"),
                job_profile=self.job.model_dump(mode="json"),
            )
        )
        json_result = await self.tools.analyze_job_match(
            self.request("match-json", "match-json-01")
        )

        self.assertTrue(database_result.success)
        self.assertTrue(json_result.success)
        self.assertEqual(self.match_service.requests[0], self.match_service.requests[1])
        self.assertEqual(database_result.data.match_result, json_result.data.match_result)


if __name__ == "__main__":
    unittest.main()
