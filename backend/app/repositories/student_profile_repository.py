"""Parameterized PostgreSQL access for the nine-column student profile."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import psycopg2
from psycopg2.extras import Json
from pydantic import ValidationError

from ..db import BusinessDatabaseError, business_transaction
from ..schemas.student_persistence_schema import (
    StudentProfileRecord,
    StudentProfileWrite,
)
from .base import BaseRepository


_COLUMNS = (
    "student_id",
    "created_at",
    "updated_at",
    "name",
    "basic_info",
    "abilities",
    "competitiveness_score",
    "completeness",
    "missing_fields",
)
_SELECT_BY_ID = """
SELECT student_id, created_at, updated_at, name, basic_info, abilities,
       competitiveness_score, completeness, missing_fields
FROM public.student_profile
WHERE student_id = %s
"""
_INSERT = """
INSERT INTO public.student_profile
  (name, basic_info, abilities, competitiveness_score, completeness,
   missing_fields)
VALUES (%s, %s, %s, %s, %s, %s)
RETURNING student_id, created_at, updated_at, name, basic_info, abilities,
          competitiveness_score, completeness, missing_fields
"""
_UPDATE_BY_ID = """
UPDATE public.student_profile
SET name = %s,
    basic_info = %s,
    abilities = %s,
    competitiveness_score = %s,
    completeness = %s,
    missing_fields = %s,
    updated_at = CURRENT_TIMESTAMP
WHERE student_id = %s
RETURNING student_id, created_at, updated_at, name, basic_info, abilities,
          competitiveness_score, completeness, missing_fields
"""


class StudentProfileRepositoryError(RuntimeError):
    """Safe repository error without SQL, parameters, or identity data."""


class StudentProfileDataError(StudentProfileRepositoryError):
    """The database returned a row outside the frozen persistence schema."""


class StudentProfileRepository(BaseRepository):
    """Create, read, and update one student profile using fixed SQL only."""

    def create(self, profile: StudentProfileWrite) -> StudentProfileRecord:
        row = self._execute_one(_INSERT, self._write_parameters(profile))
        if row is None:
            raise StudentProfileRepositoryError(
                "student profile create returned no record"
            )
        return self._record_from_row(row)

    def get_by_id(self, student_id: int) -> StudentProfileRecord | None:
        if (
            isinstance(student_id, bool)
            or not isinstance(student_id, int)
            or student_id < 1
        ):
            raise ValueError("student_id must be a positive integer")
        row = self._execute_one(_SELECT_BY_ID, (student_id,))
        return None if row is None else self._record_from_row(row)

    def update_by_id(
        self,
        student_id: int,
        profile: StudentProfileWrite,
    ) -> StudentProfileRecord | None:
        if (
            isinstance(student_id, bool)
            or not isinstance(student_id, int)
            or student_id < 1
        ):
            raise ValueError("student_id must be a positive integer")
        row = self._execute_one(
            _UPDATE_BY_ID,
            (*self._write_parameters(profile), student_id),
        )
        return None if row is None else self._record_from_row(row)

    @staticmethod
    def _write_parameters(profile: StudentProfileWrite) -> tuple[Any, ...]:
        return (
            profile.name,
            Json(profile.basic_info.model_dump(mode="json")),
            Json(
                [
                    item.model_dump(mode="json")
                    for item in profile.abilities
                ]
            ),
            profile.competitiveness_score,
            profile.completeness,
            Json(profile.missing_fields),
        )

    @staticmethod
    def _execute_one(statement: str, parameters: Sequence[Any]) -> Any | None:
        try:
            with business_transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(statement, parameters)
                    return cursor.fetchone()
        except (psycopg2.Error, BusinessDatabaseError):
            raise StudentProfileRepositoryError(
                "student profile database operation failed"
            ) from None

    @staticmethod
    def _record_from_row(row: Any) -> StudentProfileRecord:
        try:
            if isinstance(row, Mapping):
                payload = {column: row[column] for column in _COLUMNS}
            else:
                values = tuple(row)
                if len(values) != len(_COLUMNS):
                    raise ValueError("invalid row length")
                payload = dict(zip(_COLUMNS, values))
            return StudentProfileRecord.model_validate(payload)
        except (ValidationError, TypeError, ValueError, KeyError):
            raise StudentProfileDataError(
                "student profile row failed validation"
            ) from None


__all__ = [
    "StudentProfileDataError",
    "StudentProfileRepository",
    "StudentProfileRepositoryError",
]
