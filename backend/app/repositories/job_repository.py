"""Parameterized read access for job instances and job-type profiles."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import psycopg2
from pydantic import ValidationError

from ..db import BusinessDatabaseError, business_connection
from ..schemas.job_context_schema import (
    JobCleanRecord,
    JobSearchFilters,
    JobSearchPage,
    JobTypeProfileRecord,
)
from .base import BaseRepository


_JOB_COLUMNS = (
    "job_id",
    "job_title",
    "normalized_job_title",
    "city",
    "salary_range",
    "company_name",
    "industry",
    "job_description",
    "updated_at",
)
_TYPE_COLUMNS = (
    "type_key",
    "industry",
    "sample_size",
    "salary_desc_p50",
    "exemplar_job_id",
    "profile_summary",
    "level_range",
    "updated_at",
    "skill_requirements",
)

_SELECT_JOB_BY_ID = """
SELECT job_id, job_title, normalized_job_title, city, salary_range,
       company_name, industry, job_description, updated_at
FROM public.job_clean
WHERE job_id = %s
"""
_SELECT_FIRST_JOB_BY_NORMALIZED_TITLE = """
SELECT job_id, job_title, normalized_job_title, city, salary_range,
       company_name, industry, job_description, updated_at
FROM public.job_clean
WHERE normalized_job_title = %s
ORDER BY job_id
LIMIT 1
"""
_SELECT_TYPE_BY_KEY = """
SELECT type_key, industry, sample_size, salary_desc_p50, exemplar_job_id,
       profile_summary, level_range, updated_at, skill_requirements
FROM public.job_type_profile
WHERE type_key = %s
"""
_SEARCH_JOBS = """
SELECT job_id, job_title, normalized_job_title, city, salary_range,
       company_name, industry, job_description, updated_at
FROM public.job_clean
WHERE (%s IS NULL OR job_title ILIKE %s ESCAPE '\\'
       OR normalized_job_title ILIKE %s ESCAPE '\\')
  AND (%s IS NULL OR city = %s)
  AND (%s IS NULL OR industry ILIKE %s ESCAPE '\\')
ORDER BY job_id
LIMIT %s OFFSET %s
"""


class JobRepositoryError(RuntimeError):
    """Safe database access error without SQL or parameters."""


class JobRepositoryUnavailableError(JobRepositoryError):
    """The PostgreSQL job data source could not be queried."""


class JobRepositoryDataError(JobRepositoryError):
    """A returned row does not satisfy the frozen job schema."""


class JobRepository(BaseRepository):
    """Read job data through fixed statements and validated parameters."""

    def get_job_by_id(self, job_id: int) -> JobCleanRecord | None:
        if isinstance(job_id, bool) or not isinstance(job_id, int) or job_id < 1:
            raise ValueError("job_id must be a positive integer")
        row = self._fetch_one(_SELECT_JOB_BY_ID, (job_id,))
        return None if row is None else self._job_from_row(row)

    def get_job_type_by_key(self, type_key: str) -> JobTypeProfileRecord | None:
        normalized = self._validated_text(type_key, field="type_key", max_length=300)
        row = self._fetch_one(_SELECT_TYPE_BY_KEY, (normalized,))
        return None if row is None else self._type_from_row(row)

    def get_first_job_by_normalized_title(
        self,
        normalized_title: str,
    ) -> JobCleanRecord | None:
        normalized = self._validated_text(
            normalized_title,
            field="normalized_title",
            max_length=255,
        )
        row = self._fetch_one(_SELECT_FIRST_JOB_BY_NORMALIZED_TITLE, (normalized,))
        return None if row is None else self._job_from_row(row)

    def search_jobs(self, filters: JobSearchFilters) -> JobSearchPage:
        keyword = self._like_pattern(filters.keyword)
        industry = self._like_pattern(filters.industry)
        offset = (filters.page - 1) * filters.page_size
        rows = self._fetch_all(
            _SEARCH_JOBS,
            (
                filters.keyword,
                keyword,
                keyword,
                filters.city,
                filters.city,
                filters.industry,
                industry,
                filters.page_size + 1,
                offset,
            ),
        )
        items = [self._job_from_row(row) for row in rows[: filters.page_size]]
        return JobSearchPage(
            items=items,
            page=filters.page,
            page_size=filters.page_size,
            has_more=len(rows) > filters.page_size,
        )

    @staticmethod
    def _validated_text(value: str, *, field: str, max_length: int) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string")
        normalized = value.strip()
        if not normalized or len(normalized) > max_length:
            raise ValueError(f"{field} is invalid")
        return normalized

    @staticmethod
    def _like_pattern(value: str | None) -> str | None:
        if value is None:
            return None
        escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"

    @staticmethod
    def _fetch_one(statement: str, parameters: Sequence[Any]) -> Any | None:
        try:
            with business_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(statement, parameters)
                    return cursor.fetchone()
        except (psycopg2.Error, BusinessDatabaseError):
            raise JobRepositoryUnavailableError(
                "job database is unavailable"
            ) from None

    @staticmethod
    def _fetch_all(statement: str, parameters: Sequence[Any]) -> list[Any]:
        try:
            with business_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(statement, parameters)
                    return list(cursor.fetchall())
        except (psycopg2.Error, BusinessDatabaseError):
            raise JobRepositoryUnavailableError(
                "job database is unavailable"
            ) from None

    @staticmethod
    def _payload(row: Any, columns: tuple[str, ...]) -> dict[str, Any]:
        if isinstance(row, Mapping):
            return {column: row[column] for column in columns}
        values = tuple(row)
        if len(values) != len(columns):
            raise ValueError("invalid row length")
        return dict(zip(columns, values))

    @classmethod
    def _job_from_row(cls, row: Any) -> JobCleanRecord:
        try:
            return JobCleanRecord.model_validate(cls._payload(row, _JOB_COLUMNS))
        except (ValidationError, TypeError, ValueError, KeyError):
            raise JobRepositoryDataError("job row failed validation") from None

    @classmethod
    def _type_from_row(cls, row: Any) -> JobTypeProfileRecord:
        try:
            return JobTypeProfileRecord.model_validate(
                cls._payload(row, _TYPE_COLUMNS)
            )
        except (ValidationError, TypeError, ValueError, KeyError):
            raise JobRepositoryDataError(
                "job type profile row failed validation"
            ) from None


__all__ = [
    "JobRepository",
    "JobRepositoryDataError",
    "JobRepositoryError",
    "JobRepositoryUnavailableError",
]
