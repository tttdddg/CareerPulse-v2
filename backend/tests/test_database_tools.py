"""Strict database Tool schemas, source metadata, ledger and privacy tests."""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pydantic import ValidationError

from app.db_state import StateRepository
from app.mcp.tool_service import CareerMCPToolService
from app.models import CareerGraphEdge
from app.orchestrator import CareerOrchestrator
from app.repositories.career_graph_repository import (
    PostgresCareerGraphProviderError,
)
from app.repositories.job_repository import JobRepositoryUnavailableError
from app.schemas.career_profile_schema import StudentBasicInfo, StudentProfile
from app.schemas.database_tool_schema import (
    ReadCareerGraphEdgesData,
    ReadCareerGraphEdgesRequest,
    ReadJobContextRequest,
    ReadStudentProfileRequest,
    SearchJobsRequest,
)
from app.schemas.job_context_schema import (
    JobCleanRecord,
    JobContext,
    JobSearchPage,
    JobSkillRequirement,
    JobTypeProfileRecord,
)
from app.schemas.job_schema import JobProfile, RequiredJobAbility
from app.schemas.student_persistence_schema import StudentProfilePersistenceResult
from app.services.job_context_service import JobContextNotFoundError
from app.services.student_profile_persistence_service import (
    StudentProfileNotFoundError,
)
from app.tools.database_tools import DatabaseToolError, DatabaseTools


NOW = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)
SESSION_ID = "database-tool-session"
USER_ID = "anonymous-user"


def student_result() -> StudentProfilePersistenceResult:
    return StudentProfilePersistenceResult(
        student_id=101,
        name="匿名学生-101",
        profile=StudentProfile(
            user_id=USER_ID,
            basic_info=StudentBasicInfo(
                name=None,
                education_level="本科",
                major="计算机科学",
                graduation_year=2027,
                city=None,
                target_job="后端开发",
                target_industry="企业服务/SaaS",
                years_of_experience=0.5,
            ),
            ability_dimensions=[],
            ability_tags=[],
            profile_completeness=0.8,
            career_competitiveness_score=8.0,
            missing_fields=[],
            follow_up_questions=[],
            summary="历史画像包含0个能力维度。",
            created_at=NOW,
            updated_at=NOW,
        ),
    )


def job_record() -> JobCleanRecord:
    return JobCleanRecord(
        job_id=100,
        job_title="Python后端开发工程师",
        normalized_job_title="后端开发",
        city="杭州",
        salary_range="15-25（K）",
        company_name="不应进入搜索结果的公司",
        industry="企业服务/SaaS",
        job_description="不应进入搜索结果的完整岗位JD",
        updated_at=NOW,
    )


def job_context() -> JobContext:
    skill = JobSkillRequirement(
        tag="Python",
        required_level=4,
        weight=1.0,
        importance="critical",
    )
    job_type = JobTypeProfileRecord(
        type_key="后端开发",
        industry="企业服务/SaaS",
        sample_size=2,
        salary_desc_p50="12-20（K）",
        exemplar_job_id=100,
        profile_summary="后端开发类型摘要。",
        level_range="junior",
        updated_at=NOW,
        skill_requirements=[skill],
    )
    profile = JobProfile(
        job_id=100,
        title="Python后端开发工程师",
        normalized_title="后端开发",
        industry="企业服务/SaaS",
        required_abilities=[
            RequiredJobAbility(
                tag="Python",
                required_level=4,
                weight=1.0,
                importance="critical",
                evidence=None,
            )
        ],
        soft_skills=[],
        salary_range="15-25（K）",
        job_description="后端开发类型摘要。",
    )
    return JobContext(job=job_record(), job_type=job_type, profile=profile)


def graph_edge() -> CareerGraphEdge:
    return CareerGraphEdge(
        source_key="后端开发",
        target_key="高级后端开发",
        relation_type="vertical",
        reason="提升系统设计能力。",
        transfer_cost=1.2,
        growth_value=2.4,
        source_industry="企业服务/SaaS",
        target_industry="企业服务/SaaS",
        transition_requirements=["API设计"],
        risk_level="medium",
    )


class FakeStudentService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    def get_profile(self, student_id: int, *, user_id: str) -> StudentProfilePersistenceResult:
        self.calls += 1
        if self.error:
            raise self.error
        return student_result()


class FakeJobService:
    def __init__(self) -> None:
        self.search_error: Exception | None = None
        self.context_error: Exception | None = None

    def search_jobs(self, filters: Any) -> JobSearchPage:
        if self.search_error:
            raise self.search_error
        return JobSearchPage(
            items=[job_record()],
            page=filters.page,
            page_size=filters.page_size,
            has_more=False,
        )

    def get_context_by_job_id(self, job_id: int) -> JobContext:
        if self.context_error:
            raise self.context_error
        return job_context()

    def get_context_by_normalized_title(self, title: str) -> JobContext:
        if self.context_error:
            raise self.context_error
        return job_context()


class FakeGraphSelector:
    def __init__(self, *, source: str = "postgresql", error: Exception | None = None) -> None:
        self.source = source
        self.error = error

    def load(self, *_args: Any, **kwargs: Any) -> Any:
        if self.error:
            raise self.error
        return SimpleNamespace(
            edges=[graph_edge()],
            data_source=self.source,
            fallback_used=bool(kwargs.get("fallback_to_demo")),
        )


def make_tools(
    *,
    authorize: bool = True,
    student_service: FakeStudentService | None = None,
    job_service: FakeJobService | None = None,
    graph_selector: FakeGraphSelector | None = None,
    demo_mode: bool = False,
    fallback_to_demo: bool = False,
) -> DatabaseTools:
    return DatabaseTools(
        student_service=student_service or FakeStudentService(),  # type: ignore[arg-type]
        job_service=job_service or FakeJobService(),  # type: ignore[arg-type]
        graph_selector=graph_selector or FakeGraphSelector(),  # type: ignore[arg-type]
        authorize_student=(lambda *_args: authorize),
        demo_mode=demo_mode,
        fallback_to_demo=fallback_to_demo,
    )


class DatabaseToolsTests(unittest.TestCase):
    def test_requests_reject_sql_dynamic_fields_and_invalid_limits(self) -> None:
        common = {"session_id": SESSION_ID, "user_id": USER_ID}
        with self.assertRaises(ValidationError):
            SearchJobsRequest.model_validate({**common, "sql": "SELECT *"})
        with self.assertRaises(ValidationError):
            SearchJobsRequest.model_validate({**common, "table": "job_clean"})
        with self.assertRaises(ValidationError):
            SearchJobsRequest.model_validate({**common, "page_size": 51})
        with self.assertRaises(ValidationError):
            ReadJobContextRequest.model_validate(common)
        with self.assertRaises(ValidationError):
            ReadJobContextRequest.model_validate(
                {**common, "job_id": 100, "normalized_title": "后端开发"}
            )
        with self.assertRaises(ValidationError):
            ReadCareerGraphEdgesRequest.model_validate(
                {**common, "relation_type": "promotion"}
            )

    def test_student_tool_requires_authorization_and_succeeds_when_authorized(self) -> None:
        request = ReadStudentProfileRequest(
            session_id=SESSION_ID,
            user_id=USER_ID,
            student_id=101,
        )
        service = FakeStudentService()
        denied = make_tools(authorize=False, student_service=service)
        with self.assertRaises(DatabaseToolError) as caught:
            denied.read_student_profile(request)
        self.assertEqual("STUDENT_PROFILE_ACCESS_DENIED", caught.exception.error_code)
        self.assertEqual(0, service.calls)

        data = make_tools(student_service=service).read_student_profile(request)
        self.assertEqual(101, data.student_profile.student_id)
        self.assertEqual("postgresql", data.data_source)
        self.assertFalse(data.fallback_used)

    def test_student_not_found_has_fixed_non_retryable_error(self) -> None:
        tools = make_tools(
            student_service=FakeStudentService(StudentProfileNotFoundError("private"))
        )
        request = ReadStudentProfileRequest(
            session_id=SESSION_ID,
            user_id=USER_ID,
            student_id=999,
        )
        with self.assertRaises(DatabaseToolError) as caught:
            tools.read_student_profile(request)
        self.assertEqual("BUSINESS_RECORD_NOT_FOUND", caught.exception.error_code)
        self.assertFalse(caught.exception.retryable)

    def test_job_search_returns_fixed_dto_without_company_or_jd(self) -> None:
        data = make_tools().search_jobs(
            SearchJobsRequest(
                session_id=SESSION_ID,
                user_id=USER_ID,
                keyword="后端",
                page_size=10,
            )
        )
        serialized = data.model_dump_json()
        self.assertEqual(1, len(data.items))
        self.assertNotIn("company_name", serialized)
        self.assertNotIn("job_description", serialized)
        self.assertNotIn("完整岗位JD", serialized)

    def test_job_search_database_failure_is_retryable(self) -> None:
        job_service = FakeJobService()
        job_service.search_error = JobRepositoryUnavailableError("private DSN")
        with self.assertRaises(DatabaseToolError) as caught:
            make_tools(job_service=job_service).search_jobs(
                SearchJobsRequest(session_id=SESSION_ID, user_id=USER_ID)
            )
        self.assertEqual("DATABASE_UNAVAILABLE", caught.exception.error_code)
        self.assertTrue(caught.exception.retryable)

    def test_job_context_supports_fixed_reference_and_not_found(self) -> None:
        request = ReadJobContextRequest(
            session_id=SESSION_ID,
            user_id=USER_ID,
            job_id=100,
        )
        data = make_tools().read_job_context(request)
        self.assertEqual("后端开发", data.context.profile.normalized_title)

        job_service = FakeJobService()
        job_service.context_error = JobContextNotFoundError("private")
        with self.assertRaises(DatabaseToolError) as caught:
            make_tools(job_service=job_service).read_job_context(request)
        self.assertEqual("BUSINESS_RECORD_NOT_FOUND", caught.exception.error_code)

    def test_graph_tool_uses_same_response_model_for_postgres_and_demo(self) -> None:
        request = ReadCareerGraphEdgesRequest(
            session_id=SESSION_ID,
            user_id=USER_ID,
            source_type_key="后端开发",
            relation_type="vertical",
            limit=5,
        )
        postgres = make_tools().read_career_graph_edges(request)
        demo = make_tools(
            graph_selector=FakeGraphSelector(source="demo_json"),
            demo_mode=True,
            fallback_to_demo=True,
        ).read_career_graph_edges(request)

        self.assertIsInstance(postgres, ReadCareerGraphEdgesData)
        self.assertIsInstance(demo, ReadCareerGraphEdgesData)
        self.assertEqual("postgresql", postgres.data_source)
        self.assertEqual("demo_json", demo.data_source)
        self.assertTrue(demo.fallback_used)
        self.assertEqual(
            postgres.edges[0].model_dump(),
            demo.edges[0].model_dump(),
        )

    def test_graph_database_failure_is_not_silently_converted_to_demo(self) -> None:
        tools = make_tools(
            graph_selector=FakeGraphSelector(
                error=PostgresCareerGraphProviderError("private database details")
            )
        )
        request = ReadCareerGraphEdgesRequest(
            session_id=SESSION_ID,
            user_id=USER_ID,
        )
        with self.assertRaises(DatabaseToolError) as caught:
            tools.read_career_graph_edges(request)
        self.assertEqual("DATABASE_UNAVAILABLE", caught.exception.error_code)


class DatabaseToolMCPServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_directory.name) / "state.sqlite3"
        self.repository = StateRepository(sqlite_path=self.db_path)
        self.orchestrator = CareerOrchestrator(agents=[], repository=self.repository)

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    async def test_read_tool_uses_ledger_replay_and_privacy_safe_metadata(self) -> None:
        fake_student = FakeStudentService()
        service = CareerMCPToolService(
            self.orchestrator,
            timeout_seconds=1,
            database_tools=make_tools(student_service=fake_student),
        )
        request = ReadStudentProfileRequest(
            session_id=SESSION_ID,
            user_id=USER_ID,
            student_id=101,
            trace_id="database-read-001",
        )

        first = await service.read_student_profile(request)
        replay = await service.read_student_profile(request)

        self.assertTrue(first.success)
        self.assertTrue(replay.success)
        self.assertEqual(2, fake_student.calls)
        record = self.repository.get_tool_call("database-read-001")
        self.assertEqual("succeeded", record["status"])
        metadata = json.dumps(record["result_data"], ensure_ascii=False)
        self.assertIn('"student_id": 101', metadata)
        for private_value in (
            "匿名学生-101",
            "计算机科学",
            "历史画像",
            "basic_info",
            "evidence",
            "password",
        ):
            self.assertNotIn(private_value, metadata)

    async def test_database_tool_failure_is_converted_and_logged(self) -> None:
        job_service = FakeJobService()
        job_service.search_error = JobRepositoryUnavailableError("private DSN")
        service = CareerMCPToolService(
            self.orchestrator,
            timeout_seconds=1,
            database_tools=make_tools(job_service=job_service),
        )
        request = SearchJobsRequest(
            session_id=SESSION_ID,
            user_id=USER_ID,
            trace_id="database-search-failed",
            keyword="private candidate@example.com",
        )

        result = await service.search_database_jobs(request)

        self.assertFalse(result.success)
        self.assertEqual("DATABASE_UNAVAILABLE", result.error_code)
        record = self.repository.get_tool_call("database-search-failed")
        self.assertEqual("failed", record["status"])
        self.assertNotIn(
            "candidate@example.com",
            json.dumps(record, ensure_ascii=False),
        )

    async def test_database_tool_timeout_uses_existing_timeout_error(self) -> None:
        tools = make_tools()

        def slow_graph(_request: Any) -> ReadCareerGraphEdgesData:
            import time

            time.sleep(0.05)
            return ReadCareerGraphEdgesData(
                edges=[graph_edge()],
                data_source="postgresql",
                fallback_used=False,
            )

        tools.read_career_graph_edges = slow_graph  # type: ignore[method-assign]
        service = CareerMCPToolService(
            self.orchestrator,
            timeout_seconds=0.01,
            database_tools=tools,
        )
        request = ReadCareerGraphEdgesRequest(
            session_id=SESSION_ID,
            user_id=USER_ID,
            trace_id="database-graph-timeout",
        )

        result = await service.read_career_graph_edges(request)

        self.assertFalse(result.success)
        self.assertEqual("MCP_TOOL_TIMEOUT", result.error_code)
        self.assertTrue(result.retryable)
        self.assertEqual(
            "timed_out",
            self.repository.get_tool_call("database-graph-timeout")["status"],
        )


if __name__ == "__main__":
    unittest.main()
