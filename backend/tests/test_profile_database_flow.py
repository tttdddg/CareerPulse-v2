"""ProfileAgent to PostgreSQL persistence orchestration coverage."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.agents.profile_agent import ProfileAgent
from app.db_state import StateRepository
from app.mcp.tool_service import CareerMCPToolService
from app.orchestrator import CareerOrchestrator
from app.schemas.mcp_tool_schema import BuildStudentProfileRequest, StudentProfileInput
from app.schemas.student_persistence_schema import StudentProfileRecord
from app.services.student_profile_persistence_service import (
    StudentProfilePersistenceService,
)


class OfflineClient:
    async def generate_structured(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("offline")


class MemoryStudentProfileRepository:
    def __init__(self) -> None:
        self.records: dict[int, StudentProfileRecord] = {}
        self.create_count = 0
        self.update_count = 0
        self.get_count = 0

    def create(self, write: Any) -> StudentProfileRecord:
        self.create_count += 1
        student_id = 700 + self.create_count
        now = datetime.now(timezone.utc)
        record = StudentProfileRecord(
            student_id=student_id,
            created_at=now,
            updated_at=now,
            **write.model_dump(),
        )
        self.records[student_id] = record
        return record

    def get_by_id(self, student_id: int) -> StudentProfileRecord | None:
        self.get_count += 1
        return self.records.get(student_id)

    def update_by_id(self, student_id: int, write: Any) -> StudentProfileRecord | None:
        self.update_count += 1
        previous = self.records.get(student_id)
        if previous is None:
            return None
        record = StudentProfileRecord(
            student_id=student_id,
            created_at=previous.created_at,
            updated_at=datetime.now(timezone.utc),
            **write.model_dump(),
        )
        self.records[student_id] = record
        return record


class FailSelectedStateWriteRepository(StateRepository):
    def __init__(self, sqlite_path: Path, *, fail_on_write: int | None = None) -> None:
        super().__init__(sqlite_path=sqlite_path)
        self.state_writes = 0
        self.fail_on_write = fail_on_write

    def save_state_and_logs(self, state: dict[str, Any], logs=None) -> None:
        self.state_writes += 1
        if self.state_writes == self.fail_on_write:
            raise RuntimeError("simulated state snapshot failure")
        super().save_state_and_logs(state, logs)


def profile_input(*, supplement: str = "") -> StudentProfileInput:
    return StudentProfileInput(
        form_fields={
            "education_level": "本科",
            "major": "计算机科学",
            "graduation_year": 2027,
            "target_job": "AI应用开发工程师",
            "target_industry": "人工智能",
            "years_of_experience": 0.5,
        },
        skills=["Python", "数据库/SQL", "版本控制/Git", "沟通表达"],
        projects=["使用 Python、数据库/SQL 和版本控制/Git 完成后端 API 项目。"],
        internships=["参与匿名团队协作和沟通表达。"],
        supplementary_info=supplement or None,
    )


class ProfileDatabaseFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        runtime = Path(__file__).resolve().parents[1] / ".runtime" / "tests"
        runtime.mkdir(parents=True, exist_ok=True)
        self.db_path = runtime / f"profile-db-flow-{uuid.uuid4().hex}.sqlite3"
        self.student_repository = MemoryStudentProfileRepository()
        self.persistence = StudentProfilePersistenceService(self.student_repository)

    def tearDown(self) -> None:
        self.db_path.unlink(missing_ok=True)
        Path(f"{self.db_path}-shm").unlink(missing_ok=True)
        Path(f"{self.db_path}-wal").unlink(missing_ok=True)

    def tools(
        self,
        repository: StateRepository | None = None,
        *,
        demo_mode: bool = False,
    ) -> CareerMCPToolService:
        orchestrator = CareerOrchestrator(
            agents=[ProfileAgent(client=OfflineClient())],
            repository=repository or StateRepository(sqlite_path=self.db_path),
        )
        return CareerMCPToolService(
            orchestrator,
            profile_persistence_service=self.persistence,
            demo_mode=demo_mode,
        )

    async def test_create_replay_and_update_keep_one_database_identity(self) -> None:
        tools = self.tools()
        first_request = BuildStudentProfileRequest(
            session_id="profile-create-update",
            user_id="anonymous-user-01",
            trace_id="profile-create-01",
            student_input=profile_input(),
        )

        created = await tools.build_student_profile(first_request)
        replayed = await tools.build_student_profile(first_request)
        updated = await tools.build_student_profile(
            first_request.model_copy(
                update={
                    "trace_id": "profile-update-01",
                    "student_input": profile_input(
                        supplement="新增使用 MCP 完成工具调用集成。"
                    ),
                }
            )
        )

        self.assertTrue(created.success)
        self.assertTrue(replayed.success)
        self.assertTrue(updated.success)
        self.assertEqual(701, created.data.student_id)
        self.assertEqual(created.data.student_id, replayed.data.student_id)
        self.assertEqual(created.data.student_id, updated.data.student_id)
        self.assertEqual("postgresql", created.data.data_source)
        self.assertEqual(1, self.student_repository.create_count)
        self.assertEqual(1, self.student_repository.update_count)
        state = tools.orchestrator.get_session(first_request.session_id)
        self.assertEqual(701, state.student_profile_id)
        logs = str(state.agent_logs)
        self.assertNotIn("anonymous-user-01", logs)
        self.assertNotIn("匿名学生", logs)

    async def test_history_restore_maps_evidence_to_history(self) -> None:
        tools = self.tools()
        request = BuildStudentProfileRequest(
            session_id="profile-history",
            user_id="anonymous-user-02",
            trace_id="profile-history-create",
            student_input=profile_input(),
        )
        created = await tools.build_student_profile(request)
        state = tools.orchestrator.get_session(request.session_id)
        state.student_profile = None
        tools.orchestrator.persist(state)

        restored = await tools.build_student_profile(
            request.model_copy(update={"trace_id": "profile-history-restore"})
        )

        self.assertTrue(restored.success)
        self.assertEqual(created.data.student_id, restored.data.student_id)
        self.assertTrue(
            all(
                item.evidence_source.value == "history"
                for item in restored.data.student_profile.ability_dimensions
            )
        )

    async def test_state_failure_after_postgres_commit_recovers_without_insert(self) -> None:
        state_repository = FailSelectedStateWriteRepository(
            self.db_path,
            fail_on_write=2,
        )
        tools = self.tools(state_repository)
        request = BuildStudentProfileRequest(
            session_id="profile-two-phase",
            user_id="anonymous-user-03",
            trace_id="profile-two-phase-01",
            student_input=profile_input(),
        )

        uncertain = await tools.build_student_profile(request)
        recovered = await tools.build_student_profile(request)

        self.assertFalse(uncertain.success)
        self.assertTrue(uncertain.retryable)
        self.assertTrue(recovered.success)
        self.assertEqual(701, recovered.data.student_id)
        self.assertEqual("postgresql", recovered.data.data_source)
        self.assertEqual(1, self.student_repository.create_count)
        self.assertGreaterEqual(self.student_repository.get_count, 1)
        restored = tools.orchestrator.get_session(request.session_id)
        self.assertEqual(701, restored.student_profile_id)

    async def test_demo_mode_never_writes_business_database(self) -> None:
        tools = self.tools(demo_mode=True)
        result = await tools.build_student_profile(
            BuildStudentProfileRequest(
                session_id="profile-demo",
                user_id="anonymous-user-04",
                trace_id="profile-demo-01",
                student_input=profile_input(),
            )
        )

        self.assertTrue(result.success)
        self.assertTrue(result.data.demo_mode)
        self.assertEqual("demo_json", result.data.data_source)
        self.assertIsNone(result.data.student_id)
        self.assertEqual(0, self.student_repository.create_count)

    async def test_partial_profile_remains_a_session_snapshot(self) -> None:
        tools = self.tools()
        result = await tools.build_student_profile(
            BuildStudentProfileRequest(
                session_id="profile-partial",
                user_id="anonymous-user-05",
                trace_id="profile-partial-01",
                student_input=StudentProfileInput(skills=["Python"]),
            )
        )

        self.assertTrue(result.success)
        self.assertEqual("session", result.data.data_source)
        self.assertIsNone(result.data.student_id)
        self.assertEqual(0, self.student_repository.create_count)
        state = tools.orchestrator.get_session("profile-partial")
        self.assertIsNotNone(state)
        self.assertIsNone(state.student_profile_id)


if __name__ == "__main__":
    unittest.main()
