"""Job repository parameterization and deterministic context coverage."""

from __future__ import annotations

import re
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator
from unittest.mock import patch

from pydantic import ValidationError

from app.db import BusinessDatabaseUnavailable
from app.repositories import job_repository as job_repository_module
from app.repositories.job_repository import (
    JobRepository,
    JobRepositoryUnavailableError,
)
from app.schemas.job_context_schema import (
    JobCleanRecord,
    JobSearchFilters,
    JobSearchPage,
    JobSkillRequirement,
    JobTypeProfileRecord,
)
from app.services.job_context_service import (
    JobContextMappingError,
    JobContextNotFoundError,
    JobContextService,
)


NOW = datetime(2026, 9, 19, 9, 0, tzinfo=timezone.utc)


def job_record(
    *,
    job_id: int = 100,
    normalized_title: str | None = "后端开发",
    industry: str | None = "企业服务/SaaS",
) -> JobCleanRecord:
    return JobCleanRecord(
        job_id=job_id,
        job_title="Python后端开发工程师",
        normalized_job_title=normalized_title,
        city="杭州",
        salary_range="15-25（K）",
        company_name="匿名展示企业",
        industry=industry,
        job_description="负责后端服务设计与开发。",
        updated_at=NOW,
    )


def type_record(
    *,
    type_key: str = "后端开发",
    exemplar_job_id: int | None = 100,
    industry: str | None = "企业服务/SaaS",
) -> JobTypeProfileRecord:
    return JobTypeProfileRecord(
        type_key=type_key,
        industry=industry,
        sample_size=4,
        salary_desc_p50="12-20（K）",
        exemplar_job_id=exemplar_job_id,
        profile_summary="后端开发岗位类型画像摘要。",
        level_range="junior",
        updated_at=NOW,
        skill_requirements=[
            JobSkillRequirement(
                tag="Python",
                required_level=4,
                weight=0.6,
                importance="critical",
            ),
            JobSkillRequirement(
                tag="沟通表达",
                required_level=3,
                weight=0.4,
                importance="nice_to_have",
            ),
        ],
    )


def job_row(record: JobCleanRecord | None = None) -> tuple[Any, ...]:
    item = record or job_record()
    return (
        item.job_id,
        item.job_title,
        item.normalized_job_title,
        item.city,
        item.salary_range,
        item.company_name,
        item.industry,
        item.job_description,
        item.updated_at,
    )


def type_row(record: JobTypeProfileRecord | None = None) -> tuple[Any, ...]:
    item = record or type_record()
    return (
        item.type_key,
        item.industry,
        item.sample_size,
        item.salary_desc_p50,
        item.exemplar_job_id,
        item.profile_summary,
        item.level_range,
        item.updated_at,
        [value.model_dump(mode="json") for value in item.skill_requirements],
    )


class MemoryJobRepository:
    def __init__(self) -> None:
        self.jobs = {100: job_record()}
        self.types = {"后端开发": type_record()}

    def get_job_by_id(self, job_id: int) -> JobCleanRecord | None:
        return self.jobs.get(job_id)

    def get_job_type_by_key(self, type_key: str) -> JobTypeProfileRecord | None:
        return self.types.get(type_key)

    def get_first_job_by_normalized_title(
        self, normalized_title: str
    ) -> JobCleanRecord | None:
        return next(
            (
                item
                for _, item in sorted(self.jobs.items())
                if item.normalized_job_title == normalized_title
            ),
            None,
        )

    def search_jobs(self, filters: JobSearchFilters) -> JobSearchPage:
        values = list(self.jobs.values())
        if filters.keyword:
            values = [
                item
                for item in values
                if filters.keyword in item.job_title
                or filters.keyword in (item.normalized_job_title or "")
            ]
        if filters.city:
            values = [item for item in values if item.city == filters.city]
        if filters.industry:
            values = [
                item
                for item in values
                if filters.industry in (item.industry or "")
            ]
        start = (filters.page - 1) * filters.page_size
        return JobSearchPage(
            items=values[start : start + filters.page_size],
            page=filters.page,
            page_size=filters.page_size,
            has_more=len(values) > start + filters.page_size,
        )


class FakeCursor:
    def __init__(self, *, one: Any = None, all_rows: list[Any] | None = None) -> None:
        self.one = one
        self.all_rows = all_rows or []
        self.executions: list[tuple[str, tuple[Any, ...]]] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, statement: str, parameters: tuple[Any, ...]) -> None:
        self.executions.append((statement, parameters))

    def fetchone(self) -> Any:
        return self.one

    def fetchall(self) -> list[Any]:
        return self.all_rows


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.cursor_value = cursor

    def cursor(self) -> FakeCursor:
        return self.cursor_value


@contextmanager
def fake_connection(cursor: FakeCursor) -> Iterator[FakeConnection]:
    yield FakeConnection(cursor)


class JobRepositoryTests(unittest.TestCase):
    def test_single_job_query_uses_real_columns_and_parameter(self) -> None:
        cursor = FakeCursor(one=job_row())
        with patch(
            "app.repositories.job_repository.business_connection",
            return_value=fake_connection(cursor),
        ):
            result = JobRepository().get_job_by_id(100)

        self.assertEqual(100, result.job_id if result else None)
        statement, parameters = cursor.executions[0]
        self.assertIn("salary_range", statement)
        self.assertIn("job_description", statement)
        self.assertIn("WHERE job_id = %s", statement)
        self.assertNotIn("100", statement)
        self.assertEqual((100,), parameters)

    def test_job_type_query_preserves_all_skill_requirement_fields(self) -> None:
        cursor = FakeCursor(one=type_row())
        with patch(
            "app.repositories.job_repository.business_connection",
            return_value=fake_connection(cursor),
        ):
            result = JobRepository().get_job_type_by_key("后端开发")

        self.assertIsNotNone(result)
        skill = result.skill_requirements[0]
        self.assertEqual(
            {
                "tag": "Python",
                "required_level": 4,
                "weight": 0.6,
                "importance": "critical",
            },
            skill.model_dump(),
        )

    def test_search_uses_only_whitelist_filters_and_bounded_pagination(self) -> None:
        rows = [job_row(job_record(job_id=value)) for value in (100, 101, 102)]
        cursor = FakeCursor(all_rows=rows)
        filters = JobSearchFilters(
            keyword="后端%开发",
            city="杭州",
            industry="企业服务",
            page=2,
            page_size=2,
        )
        with patch(
            "app.repositories.job_repository.business_connection",
            return_value=fake_connection(cursor),
        ):
            page = JobRepository().search_jobs(filters)

        self.assertEqual([100, 101], [item.job_id for item in page.items])
        self.assertTrue(page.has_more)
        statement, parameters = cursor.executions[0]
        self.assertIn("LIMIT %s OFFSET %s", statement)
        self.assertEqual(3, parameters[-2])
        self.assertEqual(2, parameters[-1])
        self.assertEqual("%后端\\%开发%", parameters[1])

    def test_empty_search_returns_empty_page(self) -> None:
        cursor = FakeCursor(all_rows=[])
        with patch(
            "app.repositories.job_repository.business_connection",
            return_value=fake_connection(cursor),
        ):
            page = JobRepository().search_jobs(JobSearchFilters())
        self.assertEqual([], page.items)
        self.assertFalse(page.has_more)

    def test_illegal_search_parameters_fail_before_database_access(self) -> None:
        with self.assertRaises(ValidationError):
            JobSearchFilters(page_size=51)
        with self.assertRaises(ValidationError):
            JobSearchFilters.model_validate({"sort": "salary"})

    def test_database_unavailable_is_distinct_from_empty_result(self) -> None:
        @contextmanager
        def unavailable() -> Iterator[None]:
            raise BusinessDatabaseUnavailable("private connection details")
            yield

        with patch(
            "app.repositories.job_repository.business_connection",
            return_value=unavailable(),
        ):
            with self.assertRaises(JobRepositoryUnavailableError) as caught:
                JobRepository().get_job_by_id(100)
        self.assertEqual("job database is unavailable", str(caught.exception))

    def test_sql_never_references_removed_legacy_columns(self) -> None:
        sql = "\n".join(
            value
            for name, value in vars(job_repository_module).items()
            if isinstance(value, str)
            and (name.startswith("_SELECT_") or name.startswith("_SEARCH_"))
        )
        for old_name in (
            "location_raw",
            "job_description_clean",
            "core_skills",
            "optional_skills",
            "soft_skills",
        ):
            self.assertNotIn(old_name, sql)
        self.assertIsNone(re.search(r"\bsalary_desc\b", sql))


class JobContextServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = MemoryJobRepository()
        self.service = JobContextService(repository=self.repository)  # type: ignore[arg-type]

    def test_single_job_and_type_profile_can_be_read_independently(self) -> None:
        self.assertEqual(100, self.service.get_job(100).job_id)
        self.assertEqual("后端开发", self.service.get_job_type("后端开发").type_key)

    def test_normalized_title_assembles_two_tables_without_losing_skills(self) -> None:
        context = self.service.get_context_by_normalized_title("后端开发")

        self.assertEqual(100, context.profile.job_id)
        self.assertEqual("Python后端开发工程师", context.profile.title)
        self.assertEqual("后端开发", context.profile.normalized_title)
        self.assertEqual("15-25（K）", context.profile.salary_range)
        self.assertEqual(
            "后端开发岗位类型画像摘要。", context.profile.job_description
        )
        self.assertEqual(["沟通表达"], context.profile.soft_skills)
        self.assertEqual(
            [item.model_dump() for item in context.job_type.skill_requirements],
            [
                {
                    "tag": item.tag,
                    "required_level": item.required_level,
                    "weight": item.weight,
                    "importance": item.importance,
                }
                for item in context.profile.required_abilities
            ],
        )
        self.assertTrue(
            all(item.evidence is None for item in context.profile.required_abilities)
        )

    def test_job_id_assembles_context_using_normalized_type_key(self) -> None:
        context = self.service.get_context_by_job_id(100)
        self.assertEqual("后端开发", context.job_type.type_key)

    def test_missing_data_and_inconsistent_join_have_explicit_errors(self) -> None:
        with self.assertRaises(JobContextNotFoundError):
            self.service.get_job(999)
        with self.assertRaises(JobContextNotFoundError):
            self.service.get_job_type("不存在")

        self.repository.jobs[100] = job_record(normalized_title="数据分析师")
        with self.assertRaises(JobContextMappingError):
            self.service.get_context_by_normalized_title("后端开发")

    def test_type_without_exemplar_uses_first_matching_job(self) -> None:
        self.repository.types["后端开发"] = type_record(exemplar_job_id=None)
        self.repository.jobs[99] = job_record(job_id=99)

        context = self.service.get_context_by_normalized_title("后端开发")

        self.assertEqual(99, context.job.job_id)


if __name__ == "__main__":
    unittest.main()
