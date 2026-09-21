"""Cross-provider parity and final database-boundary acceptance tests."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.db_state import StateRepository
from app.mcp.tool_service import CareerMCPToolService
from app.models import CareerGraph
from app.orchestrator import CareerOrchestrator
from app.orchestrator.career_state import CareerState
from app.repositories.career_graph_repository import (
    CareerGraphProviderError,
    CareerGraphProviderResult,
)
from app.schemas.job_schema import JobProfile
from app.schemas.profile_schema import StudentProfile
from app.schemas.database_tool_schema import (
    ReadCareerGraphEdgesRequest,
    ReadJobContextRequest,
    ReadStudentProfileRequest,
    SearchJobsRequest,
)
from app.services.career_graph_repository import (
    CareerGraphProviderSelector,
    JsonCareerGraphProvider,
)
from app.services.feedback_service import FeedbackService
from app.services.match_service import MatchService
from app.services.path_service import PathService
from app.services.resource_service import ResourceService
from app.services.training_service import TrainingService

from .test_database_tools import make_tools


DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data"
STUDENTS_FILE = DATA_DIR / "students_demo.json"
JOBS_FILE = DATA_DIR / "jobs_demo.json"
GRAPH_FILE = DATA_DIR / "career_graph.json"
TRAINING_FILE = DATA_DIR / "training_tasks.json"
RESOURCES_FILE = DATA_DIR / "resources.json"


class StaticGraphProvider:
    def __init__(self, result: CareerGraphProviderResult) -> None:
        self.result = result

    def load(self, *_args: Any, **_kwargs: Any) -> CareerGraphProviderResult:
        return self.result.model_copy(deep=True)


class UnavailableGraphProvider:
    def load(self, *_args: Any, **_kwargs: Any) -> CareerGraphProviderResult:
        raise CareerGraphProviderError("database details must stay private")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DatabaseProviderParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        students = load_json(STUDENTS_FILE)
        jobs = load_json(JOBS_FILE)
        cls.student = next(item for item in students if item["student_id"] == 90003)
        cls.job = next(item for item in jobs if item["job_id"] == 91002)

        demo_result = JsonCareerGraphProvider(
            GRAPH_FILE,
            demo_mode=True,
        ).load()
        cls.demo_graph = demo_result
        cls.postgres_graph = demo_result.model_copy(
            update={
                "data_source": "postgresql",
                "fallback_used": False,
                "demo_mode": False,
            },
            deep=True,
        )

    def _run_business_chain(
        self,
        graph_result: CareerGraphProviderResult,
    ) -> dict[str, Any]:
        profile = StudentProfile.model_validate(self.student).model_dump(mode="json")
        job = JobProfile.model_validate(self.job).model_dump(mode="json")
        match = MatchService().calculate(profile, job)
        path, metadata = PathService(
            provider=StaticGraphProvider(graph_result)
        ).calculate_with_metadata(
            student_profile=profile,
            target_job_profile=job,
            match_result=match,
            user_preferences={},
            horizon_years=3,
        )
        gaps = [item["dimension"] for item in match["skill_gaps"]]
        training_service = TrainingService()
        training_task = training_service.generate("ai_office_task", gaps)
        training_score = training_service.score(
            training_task["training_id"],
            "先统一事实口径，再说明限制、校验步骤、负责人和完成期限。",
            None,
        )
        resources = ResourceService().recommend_resources(gaps, job["title"])
        feedback = FeedbackService().save_feedback(
            session_id="provider-parity",
            user_id="anonymous-parity-user",
            satisfaction=4,
            training_rating=3,
            skill_gaps=match["skill_gaps"],
            abilities=profile["abilities"],
            completed_trainings=1,
            completed_phases=len(path.get("roadmap", {}).get("phases", [])),
            training_target_abilities=training_task["target_abilities"],
            overall_score=match["overall_score"],
        )
        return {
            "profile": profile,
            "job": job,
            "match": match,
            "path": path,
            "training_task": training_task,
            "training_score": training_score,
            "resources": resources,
            "feedback": feedback,
            "source_metadata": {
                "data_source": metadata.data_source,
                "fallback_used": metadata.fallback_used,
                "demo_mode": metadata.demo_mode,
            },
        }

    def test_same_pydantic_business_graph_differs_only_by_source_metadata(self) -> None:
        self.assertEqual(
            [item.model_dump(mode="json") for item in self.postgres_graph.nodes],
            [item.model_dump(mode="json") for item in self.demo_graph.nodes],
        )
        self.assertEqual(
            [item.model_dump(mode="json") for item in self.postgres_graph.edges],
            [item.model_dump(mode="json") for item in self.demo_graph.edges],
        )
        self.assertEqual("postgresql", self.postgres_graph.data_source)
        self.assertEqual("demo_json", self.demo_graph.data_source)
        self.assertFalse(self.postgres_graph.demo_mode)
        self.assertTrue(self.demo_graph.demo_mode)

    def test_profile_job_match_path_training_feedback_chain_is_source_neutral(self) -> None:
        postgres = self._run_business_chain(self.postgres_graph)
        demo = self._run_business_chain(self.demo_graph)

        postgres_source = postgres.pop("source_metadata")
        demo_source = demo.pop("source_metadata")
        self.assertEqual(postgres, demo)
        self.assertEqual(
            {"data_source": "postgresql", "fallback_used": False, "demo_mode": False},
            postgres_source,
        )
        self.assertEqual(
            {"data_source": "demo_json", "fallback_used": False, "demo_mode": True},
            demo_source,
        )
        self.assertEqual(
            postgres["match"]["overall_score"],
            demo["match"]["overall_score"],
        )
        self.assertEqual(postgres["path"], demo["path"])

    def test_production_fails_closed_and_demo_fallback_is_explicit(self) -> None:
        production = CareerGraphProviderSelector(UnavailableGraphProvider())
        with self.assertRaises(CareerGraphProviderError):
            production.load(demo_mode=False, fallback_to_demo=False)

        demo = CareerGraphProviderSelector(
            UnavailableGraphProvider(),
            JsonCareerGraphProvider(GRAPH_FILE, demo_mode=True),
        ).load(demo_mode=True, fallback_to_demo=True)
        self.assertEqual("demo_json", demo.data_source)
        self.assertTrue(demo.fallback_used)
        self.assertTrue(demo.demo_mode)

    def test_training_and_resource_json_remain_authoritative_and_unchanged(self) -> None:
        before = {TRAINING_FILE: sha256(TRAINING_FILE), RESOURCES_FILE: sha256(RESOURCES_FILE)}
        gaps = ["数据分析", "数据库/SQL"]

        first_task = TrainingService().generate("ai_office_task", gaps)
        second_task = TrainingService().generate("ai_office_task", gaps)
        first_resources = ResourceService().recommend_resources(gaps, "数据分析师")
        second_resources = ResourceService().recommend_resources(gaps, "数据分析师")

        self.assertEqual(first_task, second_task)
        self.assertEqual(first_resources, second_resources)
        self.assertEqual(
            before,
            {TRAINING_FILE: sha256(TRAINING_FILE), RESOURCES_FILE: sha256(RESOURCES_FILE)},
        )

    def test_demo_files_validate_at_the_business_boundary(self) -> None:
        StudentProfile.model_validate(self.student)
        JobProfile.model_validate(self.job)
        CareerGraph.model_validate(load_json(GRAPH_FILE))


class StateRepositoryBoundaryTests(unittest.TestCase):
    def test_state_repository_contains_only_snapshots_logs_and_idempotency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "career-state.sqlite3"
            repository = StateRepository(sqlite_path=database)
            state = CareerState(
                session_id="state-boundary",
                user_id="anonymous-user",
                student_profile={"competitiveness_score": 66.0},
                job_profile={"job_id": 91002},
            )
            repository.save_state(state.model_dump(mode="json"))
            repository.create_tool_call(
                tool_call_id="state-boundary-call",
                tool_name="read_job_context",
                idempotency_key="state-boundary-call",
                request_fingerprint="fixed-test-fingerprint",
                session_id=state.session_id,
                platform_session_id=None,
                user_id_hash="anonymous-hash",
            )

            connection = sqlite3.connect(database)
            try:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                    if not row[0].startswith("sqlite_")
                }
            finally:
                connection.close()

        self.assertEqual(
            {"career_state", "agent_logs", "platform_tool_calls"},
            tables,
        )
        self.assertTrue(
            {"student_profile", "job_clean", "job_type_profile", "job_type_graph_edge"}.isdisjoint(tables)
        )

    def test_feedback_result_does_not_mutate_profile_competitiveness(self) -> None:
        profile = deepcopy(DatabaseProviderParityTests.student)
        before = profile["competitiveness_score"]
        match = MatchService().calculate(profile, DatabaseProviderParityTests.job)
        state = CareerState(
            session_id="feedback-boundary",
            user_id="anonymous-feedback-user",
            student_profile=profile,
            job_profile=deepcopy(DatabaseProviderParityTests.job),
            match_result=match,
        )

        result = FeedbackService().save_feedback(
            session_id=state.session_id,
            user_id=state.user_id,
            satisfaction=4,
            training_rating=3,
            overall_score=state.get_match_overall_score(),
        )
        state.feedback_result = result

        self.assertEqual(before, state.student_profile["competitiveness_score"])
        self.assertEqual(match["overall_score"], result["growth_snapshot"]["competitiveness_score"])
        if before != match["overall_score"]:
            self.assertNotEqual(
                state.student_profile["competitiveness_score"],
                result["growth_snapshot"]["competitiveness_score"],
            )


class DatabaseToolSharedBoundaryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.repository = StateRepository(
            sqlite_path=Path(self.temp_directory.name) / "database-tools.sqlite3"
        )
        self.orchestrator = CareerOrchestrator(
            agents=[],
            repository=self.repository,
        )

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def test_all_database_requests_reject_invalid_parameters(self) -> None:
        common = {"session_id": "invalid-database-request", "user_id": "anonymous-user"}
        invalid_payloads = (
            (ReadStudentProfileRequest, {**common, "student_id": 0}),
            (SearchJobsRequest, {**common, "page_size": 51}),
            (ReadJobContextRequest, common),
            (
                ReadCareerGraphEdgesRequest,
                {**common, "relation_type": "promotion"},
            ),
        )
        for schema, payload in invalid_payloads:
            with self.subTest(schema=schema.__name__):
                with self.assertRaises(ValidationError):
                    schema.model_validate(payload)

    async def test_all_database_tools_share_timeout_conversion(self) -> None:
        cases = (
            (
                "read_student_profile",
                ReadStudentProfileRequest(
                    session_id="timeout-student",
                    user_id="anonymous-user",
                    student_id=101,
                    trace_id="timeout-student-call",
                ),
            ),
            (
                "search_database_jobs",
                SearchJobsRequest(
                    session_id="timeout-search",
                    user_id="anonymous-user",
                    trace_id="timeout-search-call",
                ),
            ),
            (
                "read_job_context",
                ReadJobContextRequest(
                    session_id="timeout-context",
                    user_id="anonymous-user",
                    job_id=100,
                    trace_id="timeout-context-call",
                ),
            ),
            (
                "read_career_graph_edges",
                ReadCareerGraphEdgesRequest(
                    session_id="timeout-graph",
                    user_id="anonymous-user",
                    trace_id="timeout-graph-call",
                ),
            ),
        )
        operation_names = {
            "read_student_profile": "read_student_profile",
            "search_database_jobs": "search_jobs",
            "read_job_context": "read_job_context",
            "read_career_graph_edges": "read_career_graph_edges",
        }

        def slow_operation(_request: Any) -> None:
            import time

            time.sleep(0.05)

        for method_name, request in cases:
            with self.subTest(tool=method_name):
                database_tools = make_tools()
                setattr(database_tools, operation_names[method_name], slow_operation)
                service = CareerMCPToolService(
                    self.orchestrator,
                    timeout_seconds=0.01,
                    database_tools=database_tools,
                )
                result = await getattr(service, method_name)(request)
                self.assertFalse(result.success)
                self.assertEqual("MCP_TOOL_TIMEOUT", result.error_code)
                self.assertTrue(result.retryable)
                self.assertEqual(
                    "timed_out",
                    self.repository.get_tool_call(request.trace_id)["status"],
                )
        await asyncio.sleep(0.06)

    async def test_all_database_tools_write_privacy_safe_success_metadata(self) -> None:
        service = CareerMCPToolService(
            self.orchestrator,
            timeout_seconds=1,
            database_tools=make_tools(),
        )
        calls = (
            (
                "read_student_profile",
                ReadStudentProfileRequest(
                    session_id="privacy-student",
                    user_id="anonymous-user",
                    student_id=101,
                    trace_id="privacy-student-call",
                ),
            ),
            (
                "search_database_jobs",
                SearchJobsRequest(
                    session_id="privacy-search",
                    user_id="anonymous-user",
                    keyword="candidate@example.com",
                    trace_id="privacy-search-call",
                ),
            ),
            (
                "read_job_context",
                ReadJobContextRequest(
                    session_id="privacy-context",
                    user_id="anonymous-user",
                    normalized_title="后端开发",
                    trace_id="privacy-context-call",
                ),
            ),
            (
                "read_career_graph_edges",
                ReadCareerGraphEdgesRequest(
                    session_id="privacy-graph",
                    user_id="anonymous-user",
                    source_type_key="后端开发",
                    trace_id="privacy-graph-call",
                ),
            ),
        )
        for method_name, request in calls:
            result = await getattr(service, method_name)(request)
            self.assertTrue(result.success)
            record = self.repository.get_tool_call(request.trace_id)
            self.assertEqual("succeeded", record["status"])
            serialized = json.dumps(record, ensure_ascii=False)
            for private_value in (
                "candidate@example.com",
                "匿名学生-101",
                "计算机科学",
                "不应进入搜索结果的公司",
                "完整岗位JD",
            ):
                self.assertNotIn(private_value, serialized)


if __name__ == "__main__":
    unittest.main()
