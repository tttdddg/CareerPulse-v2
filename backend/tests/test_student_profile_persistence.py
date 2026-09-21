"""Student-profile Repository and deterministic mapping coverage."""

from __future__ import annotations

import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch

import psycopg2

from app import db
from app.repositories.student_profile_repository import (
    StudentProfileDataError,
    StudentProfileRepository,
    StudentProfileRepositoryError,
)
from app.schemas.ability_dimension import AbilityDimension
from app.schemas.career_profile_schema import (
    AbilityDimensionProfile,
    EvidenceSource,
    StudentBasicInfo,
    StudentProfile,
)
from app.schemas.profile_schema import active_ability_tags
from app.schemas.student_persistence_schema import (
    StoredStudentAbility,
    StoredStudentBasicInfo,
    StudentProfileRecord,
    StudentProfileWrite,
)
from app.services.profile_service import ProfileService, _TAG_DIMENSIONS
from app.services.student_profile_persistence_service import (
    StudentProfileMappingError,
    StudentProfileNotFoundError,
    StudentProfilePersistenceService,
    StudentProfileScoreMismatchError,
)


NOW = datetime(2026, 9, 19, 8, 0, tzinfo=timezone.utc)


def unified_profile(
    *,
    user_id: str = "user-001",
    nullable_basic: bool = False,
    evidence: str = "完成匿名课程项目",
) -> StudentProfile:
    dimensions = [
        AbilityDimensionProfile(
            dimension=AbilityDimension.PROFESSIONAL_KNOWLEDGE,
            tags=["数据分析"],
            level=4,
            confidence=0.9,
            evidence=[evidence],
            evidence_source=EvidenceSource.PROJECT,
        ),
        AbilityDimensionProfile(
            dimension=AbilityDimension.TECHNOLOGY_AND_TOOLS,
            tags=["Python", "数据库/SQL"],
            level=3,
            confidence=0.8,
            evidence=["完成匿名数据工具练习"],
            evidence_source=EvidenceSource.PROJECT,
        ),
    ]
    completeness = 0.8
    score = ProfileService.calculate_competitiveness(dimensions, completeness)
    return StudentProfile(
        user_id=user_id,
        basic_info=StudentBasicInfo(
            name="不应进入数据库推理画像",
            education_level="本科",
            major="计算机科学与技术",
            graduation_year=None if nullable_basic else 2027,
            city="杭州",
            target_job="数据分析师",
            target_industry=None if nullable_basic else "电子商务",
            years_of_experience=None if nullable_basic else 0.5,
        ),
        ability_dimensions=dimensions,
        ability_tags=["Python", "数据库/SQL", "数据分析"],
        profile_completeness=completeness,
        career_competitiveness_score=score,
        missing_fields=["internship_or_work_experience"],
        follow_up_questions=["已有问题不会持久化"],
        summary="输入摘要不会持久化",
        created_at=NOW,
        updated_at=NOW,
    )


def stored_write(name: str = "匿名学生-测试") -> StudentProfileWrite:
    return StudentProfileWrite(
        name=name,
        basic_info=StoredStudentBasicInfo(
            education_level="本科",
            major="计算机科学与技术",
            graduation_year=2027,
            target_job="数据分析师",
            target_industry="电子商务",
            years_of_experience=0.5,
        ),
        abilities=[
            StoredStudentAbility(
                tag="Python", level=3, confidence=0.8,
                evidence="完成匿名数据工具练习",
            ),
            StoredStudentAbility(
                tag="数据库/SQL", level=3, confidence=0.8,
                evidence="完成匿名数据工具练习",
            ),
            StoredStudentAbility(
                tag="数据分析", level=4, confidence=0.9,
                evidence="完成匿名课程项目",
            ),
        ],
        competitiveness_score=25.71,
        completeness=0.8,
        missing_fields=["internship_or_work_experience"],
    )


def record_from_write(
    write: StudentProfileWrite,
    *,
    student_id: int = 101,
    updated_at: datetime = NOW,
) -> StudentProfileRecord:
    return StudentProfileRecord(
        student_id=student_id,
        created_at=NOW,
        updated_at=updated_at,
        **write.model_dump(mode="python"),
    )


class MemoryStudentProfileRepository:
    def __init__(self) -> None:
        self.records: dict[int, StudentProfileRecord] = {}
        self.next_id = 101
        self.updates = 0

    def create(self, profile: StudentProfileWrite) -> StudentProfileRecord:
        record = record_from_write(profile, student_id=self.next_id)
        self.records[self.next_id] = record
        self.next_id += 1
        return record

    def get_by_id(self, student_id: int) -> StudentProfileRecord | None:
        return self.records.get(student_id)

    def update_by_id(
        self,
        student_id: int,
        profile: StudentProfileWrite,
    ) -> StudentProfileRecord | None:
        existing = self.records.get(student_id)
        if existing is None:
            return None
        self.updates += 1
        record = StudentProfileRecord(
            student_id=student_id,
            created_at=existing.created_at,
            updated_at=NOW + timedelta(seconds=self.updates),
            **profile.model_dump(mode="python"),
        )
        self.records[student_id] = record
        return record


class FakeCursor:
    def __init__(self, row: Any = None) -> None:
        self.row = row
        self.executions: list[tuple[str, tuple[Any, ...]]] = []
        self.execute_error: Exception | None = None

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, statement: str, parameters: tuple[Any, ...]) -> None:
        self.executions.append((statement, parameters))
        if self.execute_error is not None:
            raise self.execute_error

    def fetchone(self) -> Any:
        return self.row


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.closed = False
        self.cursor_value = cursor
        self.commits = 0
        self.rollbacks = 0

    def cursor(self) -> FakeCursor:
        return self.cursor_value

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.put_calls: list[tuple[FakeConnection, bool]] = []

    def getconn(self) -> FakeConnection:
        return self.connection

    def putconn(self, connection: FakeConnection, *, close: bool = False) -> None:
        self.put_calls.append((connection, close))


class StudentProfilePersistenceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = MemoryStudentProfileRepository()
        self.service = StudentProfilePersistenceService(
            repository=self.repository  # type: ignore[arg-type]
        )

    def test_create_and_read_map_flat_profile_to_unified_dimensions(self) -> None:
        created = self.service.create_profile(
            unified_profile(),
            name="匿名学生-101",
        )
        loaded = self.service.get_profile(101, user_id="user-001")

        self.assertEqual(101, created.student_id)
        self.assertEqual("匿名学生-101", created.name)
        self.assertEqual(created, loaded)
        self.assertIsNone(loaded.profile.basic_info.name)
        self.assertIsNone(loaded.profile.basic_info.city)
        self.assertEqual(
            ["专业知识", "技术与工具"],
            [item.dimension.value for item in loaded.profile.ability_dimensions],
        )
        self.assertTrue(
            all(
                item.evidence_source == EvidenceSource.HISTORY
                for item in loaded.profile.ability_dimensions
            )
        )
        self.assertEqual(
            ["Python", "数据分析", "数据库/SQL"],
            loaded.profile.ability_tags,
        )
        self.assertEqual(
            unified_profile().career_competitiveness_score,
            loaded.profile.career_competitiveness_score,
        )

    def test_nullable_database_basic_fields_are_preserved(self) -> None:
        created = self.service.create_profile(
            unified_profile(nullable_basic=True),
            name="匿名学生-空值",
        )

        basic = created.profile.basic_info
        self.assertIsNone(basic.graduation_year)
        self.assertIsNone(basic.target_industry)
        self.assertIsNone(basic.years_of_experience)

    def test_score_must_equal_profile_service_deterministic_result(self) -> None:
        profile = unified_profile().model_copy(
            update={"career_competitiveness_score": 99.0}
        )

        with self.assertRaises(StudentProfileScoreMismatchError):
            self.service.create_profile(profile, name="匿名学生-错误分数")

        self.assertEqual({}, self.repository.records)

    def test_private_evidence_and_name_do_not_leak_in_errors_or_agent_profile(self) -> None:
        private_email = "private.student@example.com"
        private_name = "真实姓名不进入推理"
        profile = unified_profile(evidence=f"联系 {private_email}")

        with self.assertRaises(StudentProfileMappingError) as caught:
            self.service.create_profile(profile, name=private_name)

        message = str(caught.exception)
        self.assertNotIn(private_email, message)
        self.assertNotIn(private_name, message)

        safe = self.service.create_profile(
            unified_profile(),
            name=private_name,
        )
        serialized_profile = safe.profile.model_dump_json()
        self.assertNotIn(private_name, serialized_profile)
        self.assertNotIn("不应进入数据库推理画像", serialized_profile)

    def test_every_active_ability_has_one_profile_dimension(self) -> None:
        active_tags = active_ability_tags()
        self.assertEqual(active_tags, set(_TAG_DIMENSIONS))

        abilities = [
            StoredStudentAbility(
                tag=tag,
                level=3,
                confidence=0.8,
                evidence="完成匿名能力验证",
            )
            for tag in sorted(active_tags)
        ]
        dimensions = self.service._group_abilities(abilities)
        grouped_tags = {
            tag
            for dimension in dimensions
            for tag in dimension.tags
        }

        self.assertEqual(active_tags, grouped_tags)

    def test_missing_read_and_update_return_explicit_domain_error(self) -> None:
        with self.assertRaises(StudentProfileNotFoundError):
            self.service.get_profile(999, user_id="user-999")
        with self.assertRaises(StudentProfileNotFoundError):
            self.service.update_profile(
                999,
                unified_profile(user_id="user-999"),
                name="匿名学生-999",
            )

    def test_repeated_update_is_safe_and_keeps_one_record(self) -> None:
        self.service.create_profile(unified_profile(), name="匿名学生-101")
        profile = unified_profile().model_copy(
            update={"missing_fields": []}
        )

        first = self.service.update_profile(101, profile, name="匿名学生-101A")
        second = self.service.update_profile(101, profile, name="匿名学生-101A")

        self.assertEqual(2, self.repository.updates)
        self.assertEqual(1, len(self.repository.records))
        self.assertEqual(101, first.student_id)
        self.assertEqual(101, second.student_id)
        self.assertGreater(second.profile.updated_at, first.profile.updated_at)


class StudentProfileRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        db._business_pool = None

    def tearDown(self) -> None:
        db._business_pool = None

    @staticmethod
    def _row(write: StudentProfileWrite | None = None) -> tuple[Any, ...]:
        value = write or stored_write()
        return (
            101,
            NOW,
            NOW,
            value.name,
            value.basic_info.model_dump(mode="json"),
            [item.model_dump(mode="json") for item in value.abilities],
            value.competitiveness_score,
            value.completeness,
            value.missing_fields,
        )

    def test_read_uses_fixed_nine_column_parameterized_transaction(self) -> None:
        cursor = FakeCursor(self._row())
        connection = FakeConnection(cursor)
        pool = FakePool(connection)
        repository = StudentProfileRepository()

        with patch.object(db, "get_business_database_pool", return_value=pool):
            record = repository.get_by_id(101)

        self.assertIsNotNone(record)
        statement, parameters = cursor.executions[0]
        self.assertIn("student_id, created_at, updated_at, name", statement)
        self.assertIn("WHERE student_id = %s", statement)
        self.assertNotIn("101", statement)
        self.assertEqual((101,), parameters)
        self.assertEqual(1, connection.commits)
        self.assertEqual(0, connection.rollbacks)
        self.assertEqual([(connection, False)], pool.put_calls)

    def test_create_and_update_use_fixed_returning_sql(self) -> None:
        write = stored_write()
        cursor = FakeCursor(self._row(write))
        connection = FakeConnection(cursor)
        pool = FakePool(connection)
        repository = StudentProfileRepository()

        with patch.object(db, "get_business_database_pool", return_value=pool):
            created = repository.create(write)
            updated = repository.update_by_id(101, write)

        self.assertEqual(101, created.student_id)
        self.assertIsNotNone(updated)
        insert_sql, insert_params = cursor.executions[0]
        update_sql, update_params = cursor.executions[1]
        self.assertIn("INSERT INTO public.student_profile", insert_sql)
        self.assertIn("RETURNING student_id, created_at, updated_at", insert_sql)
        self.assertIn("UPDATE public.student_profile", update_sql)
        self.assertIn("WHERE student_id = %s", update_sql)
        self.assertEqual("匿名学生-测试", insert_params[0])
        self.assertEqual(101, update_params[-1])
        self.assertEqual(2, connection.commits)
        self.assertEqual(2, len(pool.put_calls))

    def test_database_error_rolls_back_returns_connection_and_is_private(self) -> None:
        cursor = FakeCursor()
        cursor.execute_error = psycopg2.DatabaseError(
            "name=真实姓名; evidence=private@example.com"
        )
        connection = FakeConnection(cursor)
        pool = FakePool(connection)
        repository = StudentProfileRepository()

        with patch.object(db, "get_business_database_pool", return_value=pool):
            with self.assertRaises(StudentProfileRepositoryError) as caught:
                repository.create(stored_write())

        message = str(caught.exception)
        self.assertNotIn("真实姓名", message)
        self.assertNotIn("private@example.com", message)
        self.assertEqual(0, connection.commits)
        self.assertEqual(1, connection.rollbacks)
        self.assertEqual([(connection, False)], pool.put_calls)

    def test_invalid_database_ability_is_rejected_without_raw_value(self) -> None:
        row = list(self._row())
        row[5] = deepcopy(row[5])
        row[5][0]["tag"] = "不存在的私人能力"

        with self.assertRaises(StudentProfileDataError) as caught:
            StudentProfileRepository._record_from_row(tuple(row))

        self.assertNotIn("不存在的私人能力", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
