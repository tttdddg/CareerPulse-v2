"""Parameter-safe base class for future PostgreSQL business repositories."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

import psycopg2

from ..db import (
    BusinessDatabaseTransactionError,
    business_connection,
    business_transaction,
)


Parameters = Sequence[Any] | Mapping[str, Any]
FetchMode = Literal["none", "one", "all"]


class BusinessDatabaseQueryError(RuntimeError):
    """Content-free database error safe for logs and API translation."""


class BaseRepository:
    """Provide shared execution mechanics without defining a domain query."""

    @staticmethod
    def _validate_statement(statement: str) -> str:
        if not isinstance(statement, str) or not statement.strip():
            raise ValueError("statement must be a non-empty string")
        return statement

    def fetch_one(
        self,
        statement: str,
        parameters: Parameters = (),
    ) -> Any | None:
        return self._execute(
            statement,
            parameters,
            fetch="one",
            transactional=False,
        )

    def fetch_all(
        self,
        statement: str,
        parameters: Parameters = (),
    ) -> list[Any]:
        result = self._execute(
            statement,
            parameters,
            fetch="all",
            transactional=False,
        )
        return list(result)

    def execute(
        self,
        statement: str,
        parameters: Parameters = (),
    ) -> int:
        return int(
            self._execute(
                statement,
                parameters,
                fetch="none",
                transactional=True,
            )
        )

    def _execute(
        self,
        statement: str,
        parameters: Parameters,
        *,
        fetch: FetchMode,
        transactional: bool,
    ) -> Any:
        sql = self._validate_statement(statement)
        connection_context = (
            business_transaction() if transactional else business_connection()
        )
        try:
            with connection_context as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, parameters)
                    if fetch == "one":
                        return cursor.fetchone()
                    if fetch == "all":
                        return cursor.fetchall()
                    return cursor.rowcount
        except (psycopg2.Error, BusinessDatabaseTransactionError):
            raise BusinessDatabaseQueryError(
                "business database operation failed"
            ) from None


__all__ = ["BaseRepository", "BusinessDatabaseQueryError"]
