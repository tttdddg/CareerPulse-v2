"""JobAgent PostgreSQL context integration coverage."""

from __future__ import annotations

import unittest
import uuid
from pathlib import Path
from typing import Any

from app.agents.job_agent import JobAgent
from app.db_state import StateRepository
from app.mcp.tool_service import CareerMCPToolService
from app.orchestrator import CareerOrchestrator
from app.repositories.job_repository import JobRepositoryUnavailableError
from app.schemas.job_context_schema import JobCleanRecord, JobTypeProfileRecord
from app.schemas.mcp_tool_schema import AnalyzeTargetJobRequest, TargetJobInput
from app.services.job_context_service import JobContextService
from app.tools.database_tools import DatabaseTools


class CountingOfflineClient:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_structured(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        raise RuntimeError("offline")


class MemoryJobRepository:
    def __init__(self) -> None:
        self.jobs = {
            8101: JobCleanRecord(
                job_id=8101,
                job_title="Python后端工程师",
                normalized_job_title="后端开发",
                city="上海",
                salary_range="20k-30k",
                company_name="不进入Agent的公司",
                industry="企业服务/SaaS",
                job_description="负责 Python 后端开发并进行跨团队沟通表达。",
            )
        }
        self.types = {
            "后端开发": JobTypeProfileRecord(
                type_key="后端开发",
                industry="企业服务/SaaS",
                sample_size=12,
                salary_desc_p50="18k-28k",
                exemplar_job_id=8101,
                profile_summary="后端开发类型画像",
                level_range="mid",
                skill_requirements=[
                    {
                        "tag": "Python",
                        "required_level": 4,
                        "weight": 0.65,
                        "importance": "critical",
                    },
                    {
                        "tag": "沟通表达",
                        "required_level": 3,
                        "weight": 0.35,
                        "importance": "important",
                    },
                ],
            )
        }
        self.job_reads = 0
        self.type_reads = 0
        self.failure: Exception | None = None

    def _raise_failure(self) -> None:
        if self.failure is not None:
            raise self.failure

    def get_job_by_id(self, job_id: int):
        self._raise_failure()
        self.job_reads += 1
        return self.jobs.get(job_id)

    def get_job_type_by_key(self, type_key: str):
        self._raise_failure()
        self.type_reads += 1
        return self.types.get(type_key)

    def get_first_job_by_normalized_title(self, normalized_title: str):
        self._raise_failure()
        self.job_reads += 1
        return next(
            (
                item
                for item in self.jobs.values()
                if item.normalized_job_title == normalized_title
            ),
            None,
        )


class JobDatabaseFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        runtime = Path(__file__).resolve().parents[1] / ".runtime" / "tests"
        runtime.mkdir(parents=True, exist_ok=True)
        self.db_path = runtime / f"job-db-flow-{uuid.uuid4().hex}.sqlite3"
        self.job_repository = MemoryJobRepository()
        self.client = CountingOfflineClient()

    def tearDown(self) -> None:
        self.db_path.unlink(missing_ok=True)
        Path(f"{self.db_path}-shm").unlink(missing_ok=True)
        Path(f"{self.db_path}-wal").unlink(missing_ok=True)

    def tools(self, *, demo_mode: bool = False) -> CareerMCPToolService:
        orchestrator = CareerOrchestrator(
            agents=[JobAgent(client=self.client)],
            repository=StateRepository(sqlite_path=self.db_path),
        )
        database_tools = DatabaseTools(
            job_service=JobContextService(self.job_repository),
            demo_mode=demo_mode,
        )
        return CareerMCPToolService(
            orchestrator,
            database_tools=database_tools,
        )

    @staticmethod
    def request(target: TargetJobInput, trace_id: str) -> AnalyzeTargetJobRequest:
        return AnalyzeTargetJobRequest(
            session_id=f"session-{trace_id}",
            user_id="anonymous-user-job",
            trace_id=trace_id,
            target_job_input=target,
        )

    async def test_job_id_preserves_database_skill_vector_without_llm(self) -> None:
        tools = self.tools()
        result = await tools.analyze_target_job(
            self.request(TargetJobInput(job_id=8101), "job-id-01")
        )

        self.assertTrue(result.success)
        self.assertEqual("postgresql", result.data.data_source)
        self.assertFalse(result.data.fallback_used)
        self.assertEqual(8101, result.data.job_id)
        self.assertEqual("后端开发", result.data.type_key)
        self.assertEqual(
            [
                ("Python", 4, 0.65, "critical"),
                ("沟通表达", 3, 0.35, "important"),
            ],
            [
                (item.tag, item.required_level, item.weight, item.importance)
                for item in result.data.job_profile.required_abilities
            ],
        )
        self.assertEqual(0, self.client.calls)
        state = tools.orchestrator.get_session("session-job-id-01")
        self.assertEqual(8101, state.job_record_id)
        self.assertEqual("后端开发", state.job_type_key)
        self.assertNotIn("不进入Agent的公司", str(state.agent_logs))

    async def test_type_key_reads_exact_type_and_representative_job(self) -> None:
        tools = self.tools()
        result = await tools.analyze_target_job(
            self.request(TargetJobInput(type_key="后端开发"), "type-key-01")
        )

        self.assertTrue(result.success)
        self.assertEqual("postgresql", result.data.data_source)
        self.assertEqual("后端开发", result.data.job_profile.normalized_title)
        self.assertEqual(1, self.job_repository.type_reads)
        self.assertEqual(1, self.job_repository.job_reads)
        self.assertEqual(0, self.client.calls)

    async def test_raw_jd_does_not_query_database(self) -> None:
        tools = self.tools()
        result = await tools.analyze_target_job(
            self.request(
                TargetJobInput(
                    job_title="Python工程师",
                    job_description="岗位要求 Python、数据库/SQL 和沟通表达。",
                    industry="人工智能",
                ),
                "raw-jd-01",
            )
        )

        self.assertTrue(result.success)
        self.assertEqual("session", result.data.data_source)
        self.assertEqual(0, self.job_repository.job_reads)
        self.assertEqual(0, self.job_repository.type_reads)
        self.assertEqual(1, self.client.calls)

    async def test_missing_database_record_returns_explicit_error(self) -> None:
        result = await self.tools().analyze_target_job(
            self.request(TargetJobInput(job_id=9999), "missing-job-01")
        )

        self.assertFalse(result.success)
        self.assertEqual("JOB_CONTEXT_NOT_FOUND", result.error_code)
        self.assertFalse(result.retryable)

    async def test_database_failure_is_retryable_without_demo_fallback(self) -> None:
        self.job_repository.failure = JobRepositoryUnavailableError("unavailable")
        result = await self.tools().analyze_target_job(
            self.request(TargetJobInput(type_key="后端开发"), "job-db-fail-01")
        )

        self.assertFalse(result.success)
        self.assertEqual("JOB_DATABASE_UNAVAILABLE", result.error_code)
        self.assertTrue(result.retryable)
        self.assertEqual(0, self.client.calls)

    async def test_explicit_demo_mode_skips_database_and_marks_fallback(self) -> None:
        result = await self.tools(demo_mode=True).analyze_target_job(
            self.request(
                TargetJobInput(job_id=8101, job_title="AI产品经理"),
                "job-demo-01",
            )
        )

        self.assertTrue(result.success)
        self.assertEqual("demo_json", result.data.data_source)
        self.assertTrue(result.data.demo_mode)
        self.assertTrue(result.data.fallback_used)
        self.assertEqual(0, self.job_repository.job_reads)
        self.assertEqual(0, self.job_repository.type_reads)
        self.assertEqual(0, self.client.calls)


if __name__ == "__main__":
    unittest.main()
